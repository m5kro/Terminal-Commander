"""
m5kro - 2025

Licensed under GNU AFFERO GENERAL PUBLIC LICENSE v3 license.
More info at: https://www.gnu.org/licenses/agpl-3.0.en.html

Terminal Commander

This script gives a (chat-completions–style) OpenAI and Cohere compatible LLM controlled access to your local tmux pane.

Key features
- Uses libtmux to send keystrokes and capture output from a tmux pane.
- Wraps your system message exactly as given.
- Sends the LLM: [task], [context], [notes], [thistory], [toutput].
- Processes the LLM output: [tinput], [tspecial], [notes] (and strips/ignores <think>). 
- Optional user confirmation before each command.
- Persists history, rolling "MORE" output expansion (+10 lines per consecutive MORE).
- Calls the LLM again every ~10 seconds.
- Appends every LLM response (with <think> removed) to llmout.txt.
- LLM can judge if user intervention is needed or if task is completed.

Security note
This grants an LLM the ability to run arbitrary shell commands in a tmux session.
Use only in isolated or test environments you control.

Requirements
- tmux installed and available on PATH
- Python 3.9+
- pip install -r requirements.txt
"""

import argparse
from html import parser
import os
import platform
import re
import shutil
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests
import libtmux
from dotenv import load_dotenv
import json
from web_search import perform_web_search, get_webpage_content

load_dotenv()

# This is the system message with instructions on how the llm should operate, change it to fit your needs
SYSTEM_MESSAGE = """You are a careful, capable terminal user. Your goal is to complete the task provided in [task][/task] using the information and tools below.

Inputs Provided
[context][/context]: System/environment details.
[web][/web]: Web search results in json form.
[notes][/notes]: Your own short memory to help you work.
[thistory][/thistory]: Your previous terminal inputs.
[toutput][/toutput]: The last 20 lines of terminal output.

Output Format (exactly one per turn)
You must send one of the following blocks each turn:

1. Terminal input
[tinput]INPUT_GOES_HERE[/tinput]
Send one command or input at a time.
Avoid newlines; ENTER is pressed automatically after each command.

or

2. Special keywords
[tspecial]SPECIAL_KEYWORD [optional arguments][/tspecial]
Available tspecial keywords:
AWAIT — wait for the current command to finish. DO NOT WAIT FOR EXTERNAL INPUT, YOU ARE THE TERMINAL USER.
CTRLC — send Ctrl+C to stop the current process.
MORE — request 10 more output lines (repeatable).
PASSWORD — whenever the terminal prompts for a password, use the PASSWORD tspecial command.
COMPLETE — declare the task finished.
ERROR [error]brief explanation of what you need from the user[/error] — ask for user intervention.

You may include an optional [notes][/notes] block with either [tinput] or [tspecial]. Omit [notes] if you have nothing new.

Operating Loop
1. Read [task], [context], [web], [thistory], and [toutput].
2. Decide the single next best action.
3. Send [tinput] or [tspecial].
4. Use AWAIT when a command will take time; use MORE to page output.
5. Observe new [toutput] and iterate.
6. Use COMPLETE when the task objective is met. If blocked, use ERROR with a clear request.

Guidelines
Be decisive: one command per turn, minimal side effects, prefer safe and idempotent actions first.
Handle failures: if a command errors, adjust and retry or explain via ERROR.
Use the CTRLC tspecial command to stop runaway or hanging processes.
Use the PASSWORD tspecial command whenever the terminal explicitly asks for a password.
Keep [notes] short, actionable, and future-useful (e.g., paths, flags, credentials prompts, gotchas).
Never include both [tinput] and [tspecial] in the same turn (if both are present, only [tinput] executes).
ALWAYS wrap tspecial keywords in a [tspecial] block.
If you can't find something, try looking around for it.
If a program asks for user input, try to provide it.
"""

SEARCH_QUERY_SYSTEM = """You are a search-query generator.
Given the user's [task][/task] and [context][/context], output ONE concise web search query string that would best help a terminal operator accomplish the task.
Do NOT explain.
Do NOT add quotes.
Return only the query text.
"""

def require_tmux():
    if shutil.which("tmux") is None:
        print("Error: tmux is not installed or not on PATH.", file=sys.stderr)
        sys.exit(2)


def get_linux_distro() -> str:
    try:
        if os.path.exists("/etc/os-release"):
            data = {}
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        data[k.strip()] = v.strip().strip('"')
            name = data.get("PRETTY_NAME") or data.get("NAME") or ""
            ident = data.get("ID") or ""
            if name and ident:
                return f"{name} ({ident})"
            return name or ident or "linux"
    except Exception as e:
        print(f"Warning: failed to get Linux distro info: {e}", file=sys.stderr)
        pass
    return "linux"


def get_system_context(pane: libtmux.Pane) -> str:
    sysname = platform.system().lower()  # 'linux', 'darwin', 'windows'
    arch = platform.machine()
    kernel = platform.release()
    node = socket.gethostname()
    distro = ""
    if sysname == "linux":
        distro = get_linux_distro()
    elif sysname == "darwin":
        distro = "macOS"
    elif sysname == "windows":
        distro = "Windows"
    try:
        current = get_current_directory(pane)
    except Exception as e:
        print(f"Warning: failed to get current directory: {e}", file=sys.stderr)
        current = ""
    context = {
        "os": sysname,
        "arch": arch,
        "kernel": kernel,
        "hostname": node,
        "distro": distro,
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "current_directory": current,
        "directory_contents": ", ".join(os.listdir(current)) if current and os.path.isdir(current) else "",
    }
    # Present as simple human-readable lines:
    lines = [
        f"os={context['os']}",
        f"arch={context['arch']}",
        f"kernel={context['kernel']}",
        f"hostname={context['hostname']}",
        f"distro={context['distro']}",
        f"platform_version={context['platform_version']}",
        f"python_version={context['python_version']}",
        f"time_utc={context['time_utc']}",
        f"current_directory={context['current_directory']}",
        f"directory_contents={context['directory_contents']}",
    ]
    return "\n".join(lines)


def new_or_attach_session(server, session_name):
    sess = next((s for s in server.sessions if s.name == session_name), None)
    if sess is None:
        sess = server.new_session(session_name=session_name, attach=False, start_directory=os.getcwd())
    window = sess.active_window or sess.windows[0]
    pane = window.active_pane or window.panes[0]
    return sess, window, pane

def get_current_directory(pane: libtmux.Pane) -> str:
    try:
        # libtmux exposes 'pane_current_path'
        return (pane.pane_current_path or "").strip()
    except Exception as e:
        print(f"Warning: failed to get current directory: {e}", file=sys.stderr)
        return ""


def capture_tail(pane: libtmux.Pane, lines: int) -> str:
    try:
        out = pane.capture_pane(start=-lines)
        if isinstance(out, list):
            return "\n".join(out)
        return out or ""
    except Exception as e:
        print(f"Warning: failed to capture pane output: {e}", file=sys.stderr)
        return ""

SHELL_NAMES = {"bash", "zsh", "sh", "fish", "dash"}

def get_pane_current_command(pane: libtmux.Pane) -> str:
    try:
        # libtmux exposes 'pane_current_command'
        return (pane.current_command or "").strip().lower()
    except Exception as e:
        print(f"Warning: failed to get current command: {e}", file=sys.stderr)
        return ""

def send_ctrl_c(pane: libtmux.Pane):
    try:
        # Try literal Ctrl-C character:
        pane.send_keys("\x03", enter=False)
    except Exception:
        # Fallback to tmux notation:
        try:
            pane.send_keys("C-c", enter=False)
        except Exception as e:
            print(f"Warning: failed to send Ctrl-C: {e}", file=sys.stderr)


TAG_RE_CACHE = {}
def extract_tag(text: str, tag: str) -> Optional[str]:
    # Returns first match content or None. Non-greedy, DOTALL.
    key = (tag,)
    regex = TAG_RE_CACHE.get(key)
    if regex is None:
        regex = re.compile(rf"\[{tag}\](.*?)\[/{tag}\]", re.DOTALL | re.IGNORECASE)
        TAG_RE_CACHE[key] = regex
    m = regex.search(text)
    if not m:
        return None
    return m.group(1).strip()


def strip_think_blocks(text: str, tag: str) -> str:
    regex = re.compile(rf"<{tag}>.*?</{tag}>", re.DOTALL | re.IGNORECASE)
    return regex.sub("", text)


def sanitize_single_line(cmd: str) -> str:
    # Keep only first line; collapse internal whitespace a bit
    first = cmd.splitlines()[0].strip()
    return re.sub(r"\s+", " ", first)

def generate_ai_search_query(base_url: str, model: str, api_key: str, task: str, context: str, cohere: bool = False, timeout: int = 120) -> str:
    """
    Use a separate system message to derive a single search query string from the task/context.
    """
    user_payload = f"[task]{task}[/task]\n[context]{context}[/context]"
    raw = call_llm(
        base_url=base_url,
        model=model,
        system_message=SEARCH_QUERY_SYSTEM,
        user_content=user_payload,
        api_key=api_key,
        timeout=timeout,
        cohere=cohere,
    )
    strip_think_blocks(raw, "think")
    # Keep to one line
    return re.sub(r"\s+", " ", raw.strip())


def build_user_payload(task: str, context: str, web: str, notes: str, thistory: str, toutput: str) -> str:
    return (
        f"[task]{task}[/task]\n"
        f"[context]{context}[/context]\n"
        f"[web]{web}[/web]\n"
        f"[notes]{notes}[/notes]\n"
        f"[thistory]{thistory}[/thistory]\n"
        f"[toutput]{toutput}[/toutput]"
    )


def call_llm(base_url: str, model: str, system_message: str, user_content: str, api_key: str, timeout: int = 300, cohere: bool = False) -> str:
    """
    Calls an OpenAI-compatible /v1/chat/completions endpoint.
    The server is expected to accept an empty api_key if it doesn't require auth.
    """
    url = base_url.rstrip("/")
    if cohere:
        url += "/v2/chat"
    else:
        url += "/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }
    # Include Authorization header even if empty (some proxies require presence)
    headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:2000]}")
    data = resp.json()
    try:
        if cohere:
            return data["message"]["content"][0]["text"]
        else:
            return data["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"Unexpected LLM response format: {data}")


def append_log(path: str, content: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n===== {datetime.now(timezone.utc).isoformat()} =====\n")
        f.write(content)
        f.write("\n")

def redact_secrets(text: str) -> str:
    """
    Masks the TERM_PASSWORD value if it somehow appears.
    """
    if not text:
        return text
    redacted = text

    pwd = os.environ.get("TERM_PASSWORD")
    if pwd:
        redacted = redacted.replace(pwd, "[REDACTED]")

    return redacted

def close_session(session: libtmux.Session):
    close = input(f"Close tmux session '{session.name}'? [y/N]: ").strip().lower()
    if close.startswith("y"):
        try:
            session.kill()
            print(f"Session '{session.name}' killed.")
        except Exception as e:
            print(f"Failed to kill session: {e}", file=sys.stderr)
    return

def main():
    default_base_url = (
        os.environ.get("LLM_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "http://127.0.0.1:5000"
    )
    default_model = (
        os.environ.get("LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4o-mini"
    )
    default_api_key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    parser = argparse.ArgumentParser(description="LLM-controlled tmux assistant")
    parser.add_argument("--base-url", default=default_base_url, help="Base URL of the OpenAI-compatible server (no trailing /v1)")
    parser.add_argument("--model", default=default_model, help="Model name on the server")
    parser.add_argument("--api-key", default=default_api_key, help="API key. Empty string allowed.")
    parser.add_argument("--cohere", default=False, action="store_true",
                        help="Use Cohere API format instead of OpenAI (implies --base-url and --api-key are for Cohere)")
    parser.add_argument("--session", default="llmterm", help="tmux session name to create/use")
    parser.add_argument("--confirm", action="store_true", help="Always require confirmation before executing commands")
    parser.add_argument("--no-confirm", action="store_true", help="Never require confirmation (overrides prompt)")
    parser.add_argument("--sleep-secs", type=int, default=10, help="Seconds to wait between LLM rounds")
    parser.add_argument("--logfile", default="llmout.txt", help="Path to append raw LLM outputs")
    parser.add_argument("--print-prompts", action="store_true", help="Print composed user payloads for debugging")
    parser.add_argument("--print-llm", action="store_true", help="Print the sanitized LLM response (with <think> removed)")
    parser.add_argument("--print-llm-raw", action="store_true", help="Print the raw LLM response from the server (debug)")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds to wait for the LLM response (per request)")
    # Web search options
    parser.add_argument("--web", action="store_true", help="Force-enable web search without interactive prompt")
    parser.add_argument("--no-web", action="store_true", help="Force-disable web search without interactive prompt")
    parser.add_argument("--web-top-k", type=int, default=3, help="Number of top pages to fetch (default: 3)")
    parser.add_argument("--web-query", type=str, default="", help="Custom/override web search query to use")
    parser.add_argument("--web-timeout", type=int, default=10, help="Per-request timeout for web search")

    args = parser.parse_args()

    require_tmux()

    # Ask for task and confirmation preference (unless overridden by flags)
    task = input("Enter the task the LLM should complete: ").strip()
    if not task:
        print("A task is required.", file=sys.stderr)
        sys.exit(1)

    if args.no_confirm:
        require_confirm = False
    elif args.confirm:
        require_confirm = True
    else:
        yn = input("Require confirmation before running each input? [y/N]: ").strip().lower()
        require_confirm = yn.startswith("y")
    
    # Optional Web search for context (interactive unless forced by flags)
    if args.no_web:
        web_enabled = False
    elif args.web:
        web_enabled = True
    else:
        yn_web = input("Perform a web search to gather context? [y/N]: ").strip().lower()
        web_enabled = yn_web.startswith("y")

    # Determine search query (allow override via CLI or interactive)
    web_query = args.web_query.strip()
    if web_enabled and not web_query:
        custom = input("Enter a custom web query (leave blank to let AI decide): ").strip()
        if custom:
            web_query = custom

    server = libtmux.Server()
    session, window, pane = new_or_attach_session(server, args.session)
    # Clear visible screen so output capture starts fresh
    try:
        pane.send_keys("clear", enter=True)
    except Exception as e:
        print(f"Warning: failed to clear pane: {e}", file=sys.stderr)

    notes_state = ""
    web_payload_json = ""
    # Prepare web results once (re-used every loop)
    if web_enabled:
        # Build context now so the AI can use it to craft a query if needed
        context_for_search = get_system_context(pane)
        if not web_query:
            try:
                web_query = generate_ai_search_query(
                    base_url=args.base_url,
                    model=args.model,
                    timeout=max(1, args.timeout),
                    api_key=args.api_key,
                    task=task,
                    context=context_for_search,
                    cohere=args.cohere,
                )
                if not web_query:
                    raise RuntimeError("Empty AI-generated query")
            except Exception as e:
                print(f"[web] Failed to generate AI search query, falling back to no-web. Reason: {e}", file=sys.stderr)
                web_enabled = False

    if web_enabled:
        try:
            results = perform_web_search(web_query, max_results=max(1, args.web_top_k), timeout=args.web_timeout) or []            
            enriched = []
            for r in results:
                try:
                    print(f"[web] Fetching content for {r['url'][8:]}")
                    r["content"] = get_webpage_content(r["url"][8:])
                except Exception as e:
                    print(f"[web] Failed to fetch content for {r['url'][8:]}: {e}", file=sys.stderr)
                    r["content"] = ""
                enriched.append(r)
            results = enriched
            web_payload_json = json.dumps({
                "query": web_query,
                "results": results,
            }, ensure_ascii=False)
        except Exception as e:
            print(f"[web] Search error: {e}", file=sys.stderr)
            web_payload_json = json.dumps({
                "query": web_query or "",
                "results": [],
                "error": str(e),
            }, ensure_ascii=False)
    else:
        web_payload_json = "No web information provided or needed"

    # Command status tracking
    last_exit_code: Optional[int] = None
    last_cmd_pending: bool = False
    # Need to implement getting command vstatus
    CURRENT_CSTATUS = "success"  # default when idle
    thistory_list = []
    more_streak = 0  # counts consecutive MORE commands
    base_lines = 20

    print(f"Attached to tmux session '{session.name}'. Press Ctrl+C to stop.")
    try:
        while True:
            # 1) CAPTURE (always capture first, so the request we send contains the latest screen)
            context = get_system_context(pane)
            lines_to_capture = base_lines + 10 * more_streak
            toutput = capture_tail(pane, lines_to_capture)

            # Filter out password from output
            toutput = redact_secrets(toutput)

            # 2) ASK the LLM
            user_payload = build_user_payload(
                task=task,
                context=context,
                web=web_payload_json,
                notes=notes_state,
                thistory="\n".join(thistory_list),
                toutput=toutput,
            )
            if args.print_prompts:
                print("\n--- LLM USER PAYLOAD BEGIN ---\n")
                print(user_payload)
                print("\n--- LLM USER PAYLOAD END ---\n")

            try:
                llm_raw = call_llm(
                    base_url=args.base_url,
                    model=args.model,
                    system_message=SYSTEM_MESSAGE,
                    user_content=user_payload,
                    api_key=args.api_key,
                    timeout=max(1, args.timeout),
                    cohere=args.cohere,
                )
                if args.print_llm_raw:
                    print("\n--- LLM RAW RESPONSE BEGIN ---\n")
                    print(llm_raw)
                    print("\n--- LLM RAW RESPONSE END ---\n")
            except Exception as e:
                print(f"[LLM error] {e}", file=sys.stderr)
                time.sleep(args.sleep_secs)
                continue

            # Strip think + log
            llm_sanitized = strip_think_blocks(llm_raw, "think")
            if args.print_llm:
                print("\n--- LLM RESPONSE BEGIN ---\n")
                print(llm_sanitized)
                print("\n--- LLM RESPONSE END ---\n")
            try:
                append_log(args.logfile, llm_sanitized)
            except Exception as e:
                print(f"[warn] Failed to write log: {e}", file=sys.stderr)

            # Persist notes
            maybe_notes = extract_tag(llm_sanitized, "notes")
            if maybe_notes is not None:
                notes_state = maybe_notes

            # 3) EXECUTE the instruction
            tinput = extract_tag(llm_sanitized, "tinput")
            tspecial = extract_tag(llm_sanitized, "tspecial")
            error = extract_tag(llm_sanitized, "error")

            # If both are present, prefer tinput per your spec
            did_send_or_wait = False

            if tinput:
                cmd = sanitize_single_line(tinput)
                if require_confirm:
                    ans = input(f"Run: {cmd!r}? [y/N]: ").strip().lower()
                    if ans.startswith("y"):
                        pane.send_keys(cmd, enter=True)
                        thistory_list.append(cmd)
                        more_streak = 0
                        did_send_or_wait = True
                    else:
                        print("Skipped.")
                else:
                    pane.send_keys(cmd, enter=True)
                    thistory_list.append(cmd)
                    more_streak = 0
                    did_send_or_wait = True
                    print(f"Sent: {cmd!r}")

            elif tspecial:
                sp = tspecial.strip().upper()
                if "CTRLC" in sp:
                    send_ctrl_c(pane)
                    more_streak = 0
                    did_send_or_wait = True
                    print("Sent Ctrl-C")
                elif "COMPLETE" in sp:
                    print("LLM indicated task COMPLETED. Exiting.")
                    close_session(session)
                    break
                elif "ERROR" in sp:
                    print("LLM indicated ERROR requiring user intervention. Exiting with error.", file=sys.stderr)
                    if error:
                        print(f"LLM error explanation: {error}", file=sys.stderr)
                    sys.exit(3)
                elif "MORE" in sp:
                    # Only adjust capture size; no forced wait here.
                    more_streak += 1
                    did_send_or_wait = False
                elif "PASSWORD" in sp:
                    password = os.environ.get("TERM_PASSWORD")
                    if not password:
                        print("LLM requested PASSWORD but TERM_PASSWORD env var is not set. Skipping.", file=sys.stderr)
                    else:
                        if require_confirm:
                            ans = input(f"Enter password into terminal? [y/N]: ").strip().lower()
                            if not ans.startswith("y"):
                                print("Skipped password entry.")
                            else:
                                pane.send_keys(password, enter=True)
                                thistory_list.append("PASSWORD")
                                more_streak = 0
                                did_send_or_wait = True
                                print("Entered password.")
                        else:
                            pane.send_keys(password, enter=True)
                            thistory_list.append("PASSWORD")
                            more_streak = 0
                            did_send_or_wait = True
                            print("Entered password.")
                else:
                    # Treat AWAIT (or unknown) as a wait request
                    did_send_or_wait = True

            # 4) SLEEP 10s ONLY if we actually sent something or were told to wait
            if did_send_or_wait:
                time.sleep(args.sleep_secs)

            # 5) Loop continues; next iteration will capture first



    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
        # Close session?
        close_session(session)
        return


if __name__ == "__main__":
    main()