import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.tools.web import _fallback_google_search, _fallback_bing_search, _fallback_yahoo_search

logging.basicConfig(level=logging.INFO)

def run_tests():
    query = "offshore wind farm projects commissioning 2026"
    print(f"--- Testing Fallbacks for query: '{query}' ---")
    
    print("\n1. Google:")
    try:
        g_res = _fallback_google_search(query)
        print(f"Found {len(g_res)} results.")
        for r in g_res:
            print(f"- {r['title'][:40]} : {r['href']}")
    except Exception as e:
        print(f"Google Error: {e}")

    print("\n2. Bing:")
    try:
        b_res = _fallback_bing_search(query)
        print(f"Found {len(b_res)} results.")
        for r in b_res:
            print(f"- {r['title'][:40]} : {r['href']}")
            
        if not b_res:
            import urllib.request
            import urllib.parse
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.bing.com/search?q={encoded}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
            print(f"No Bing results. Length of Bing HTML: {len(html)} chars")
            with open("bing_debug.html", "w") as f:
                f.write(html)
            print("Saved bing_debug.html")
    except Exception as e:
        print(f"Bing Error: {e}")

    print("\n3. Yahoo:")
    try:
        y_res = _fallback_yahoo_search(query)
        print(f"Found {len(y_res)} results.")
        for r in y_res:
            print(f"- {r['title'][:40]} : {r['href']}")
            
        if not y_res:
            import urllib.request
            import urllib.parse
            encoded = urllib.parse.quote_plus(query)
            url = f"https://search.yahoo.com/search?p={encoded}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
            print(f"No Yahoo results. Length of Yahoo HTML: {len(html)} chars")
            with open("yahoo_debug.html", "w") as f:
                f.write(html)
            print("Saved yahoo_debug.html")

    except Exception as e:
        print(f"Yahoo Error: {e}")

if __name__ == "__main__":
    run_tests()
