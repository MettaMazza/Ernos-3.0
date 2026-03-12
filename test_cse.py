import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import json

def test_google_cse():
    print("--- Testing Google CSE / AJAX Endpoints ---")
    query = "machine learning"
    encoded = urllib.parse.quote_plus(query)
    # Testing an old known CSE ajax endpoint (often still responds but sometimes heavily rate-limited)
    url = f"https://cse.google.com/cse/element/v1?rsz=filtered_cse&num=10&hl=en&source=gcsc&gss=.com&cselibv=1ac69480dc297e64&cx=017121650394541785566:i0kydhmy6m8&q={encoded}&safe=off&cse_tok=AJvRUv27pA7eM-H68aV7hS4Q1y-I:1708514107106&exp=csqr,cc&callback=google.search.cse.api3568"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://cse.google.com/"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            print(f"Response: {html[:200]}...")
    except Exception as e:
        print(f"Failed - {e}")

if __name__ == "__main__":
    test_google_cse()
