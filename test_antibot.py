import logging
import urllib.parse
from bs4 import BeautifulSoup

def test_cloudscraper(url):
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})
        resp = scraper.get(url, timeout=10)
        return resp.status_code, len(resp.text), "turnstile" in resp.text.lower() or "recaptcha" in resp.text.lower()
    except Exception as e:
        return "ERROR", str(e), False

def test_curl_cffi(url):
    try:
        from curl_cffi import requests as cc_requests
        resp = cc_requests.get(url, impersonate="chrome120", timeout=10)
        return resp.status_code, len(resp.text), "turnstile" in resp.text.lower() or "recaptcha" in resp.text.lower()
    except Exception as e:
        return "ERROR", str(e), False

def main():
    query = "offshore wind farm projects commissioning 2026"
    encoded = urllib.parse.quote_plus(query)
    
    urls = {
        "Google": f"https://www.google.com/search?q={encoded}",
        "DDG": f"https://html.duckduckgo.com/html/?q={encoded}",
        "Bing": f"https://www.bing.com/search?q={encoded}"
    }
    
    for name, url in urls.items():
        print(f"\nEvaluating {name}...")
        cs_status, cs_len, cs_captcha = test_cloudscraper(url)
        print(f"  [Cloudscraper] Status: {cs_status}, Len: {cs_len}, CAPTCHA: {cs_captcha}")
        
        cc_status, cc_len, cc_captcha = test_curl_cffi(url)
        print(f"  [curl_cffi] Status: {cc_status}, Len: {cc_len}, CAPTCHA: {cc_captcha}")

if __name__ == "__main__":
    main()
