# Super Striped down version of mamei16's llm_web_search.py
# Original at:https://github.com/mamei16/LLM_Web_search/
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE Version 3
# More info at: https://www.gnu.org/licenses/agpl-3.0.en.html

import urllib
from urllib.parse import quote_plus
import regex
import logging
import html

import requests
from requests.exceptions import JSONDecodeError
import lxml
from bs4 import BeautifulSoup

def perform_web_search(query, max_results=3, timeout=10):
    """Modified version of function from main webUI in modules/web_search.py"""
    try:
        # Use DuckDuckGo HTML search endpoint
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        response = requests.get(search_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        if regex.search("anomaly-modal__mask", response.text, regex.DOTALL):
            raise ValueError("Web search failed due to CAPTCHA")

        # Extract results with regex
        titles = regex.findall(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>', response.text, regex.DOTALL)
        urls = regex.findall(r'<a[^>]*class="[^"]*result__url[^"]*"[^>]*>(.*?)</a>', response.text, regex.DOTALL)
        snippets = regex.findall(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', response.text, regex.DOTALL)

        result_dicts = []
        for i in range(min(len(titles), len(urls), len(snippets), max_results)):
            url = f"https://{urls[i].strip()}"
            title = regex.sub(r'<[^>]+>', '', titles[i]).strip()
            title = html.unescape(title)
            snippet = html.unescape(snippets[i]).replace("<b>", "").replace("</b>", "")
            result_dicts.append({"url": url, "title": title, "content": snippet})
        return result_dicts

    except Exception as e:
        logger = logging.getLogger('text-generation-webui')
        logger.error(f"Error performing web search: {e}")
        return []

def get_webpage_content(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
               "Accept-Language": "en-US,en;q=0.5"}
    if not url.startswith("https://"):
        try:
            response = requests.get(f"https://{url}", headers=headers)
        except:
            response = requests.get(url, headers=headers)
    else:
        response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.content, features="lxml")
    for script in soup(["script", "style"]):
        script.extract()

    strings = soup.stripped_strings
    return '\n'.join([s.strip() for s in strings])