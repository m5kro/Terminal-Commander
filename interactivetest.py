#!/usr/bin/env python3
"""
Interactive terminal questionnaire.
Asks for:
- System OS
- System architecture
- Hostname
- Kernel
- Supplied password

Run: python3 interactivetest.py
"""

def main() -> None:
    print("Interactive system info test\n" + "-" * 32)
    answers = {}
    try:
        answers["System OS"] = input("What is the system OS? ")
        answers["System architecture"] = input("What is the system arch? ")
        answers["Hostname"] = input("What is the hostname? ")
        answers["Kernel"] = input("What is the kernel? ")
        answers["Supplied password"] = input("Enter supplied password: ")
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        return

    print("\n\nSummary\n" + "=" * 32)
    # compute column width
    key_width = max(len(k) for k in answers.keys())
    for k, v in answers.items():
        print(f"{k:<{key_width}} : {v}")

if __name__ == "__main__":
    main()
