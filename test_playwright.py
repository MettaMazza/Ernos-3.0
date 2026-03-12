from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import urllib.parse
from bs4 import BeautifulSoup

def test_playwright_scraper():
    query = "offshore wind farm projects commissioning 2026"
    encoded = urllib.parse.quote_plus(query)
    
    urls = {
        "Google": (f"https://www.google.com/search?q={encoded}", "div.g"),
        "Bing": (f"https://www.bing.com/search?q={encoded}", "li.b_algo")
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Using a very standard fingerprint
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            has_touch=False
        )
        page = context.new_page()
        stealth_sync(page)
        
        for name, (url, selector) in urls.items():
            print(f"\nEvaluating {name} with Playwright Stealth...")
            try:
                response = page.goto(url, timeout=15000)
                page.wait_for_timeout(2000)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                results = soup.select(selector)
                
                print(f"  Status: {response.status if response else 'Unknown'}, Len: {len(html)}")
                print(f"  Found '{selector}': {len(results)}")
                
                is_captcha = "turnstile" in html.lower() or "recaptcha" in html.lower() or 'id="captcha-form"' in html.lower()
                print(f"  CAPTCHA keywords found: {is_captcha}")
                
            except Exception as e:
                print(f"  Error: {e}")
                
        context.close()
        browser.close()

if __name__ == "__main__":
    test_playwright_scraper()
