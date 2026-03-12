from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup

def test_stealth_google():
    print("--- Testing Playwright Stealth on Google ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1920,1080',
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2,
            has_touch=False,
            is_mobile=False,
            locale='en-US',
            timezone_id='America/New_York'
        )
        page = context.new_page()
        
        # Apply stealth directly using the correct import
        from playwright_stealth import stealth
        stealth(page)
        
        try:
            print("Navigating to Google...")
            page.goto("https://www.google.com/search?q=machine+learning", wait_until="networkidle", timeout=30000)
            
            # Additional wait to mimic human behavior reading the page
            page.wait_for_timeout(5000)
            
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            results = soup.select("div.g")
            print(f"Found {len(results)} organic links (div.g)")
            
            for div in results[:3]:
                h3 = div.select_one("h3")
                a = div.select_one("a")
                if h3 and a:
                    print(f" - {h3.text.strip()} | {a.get('href', '')}")
                    
            if len(results) == 0:
                print("Failed to find results. Dumping raw HTML for debug...")
                print("TITLE:", soup.title() if soup.title else "No Title")
                with open("google_debug_playwright.html", "w") as f:
                    f.write(soup.prettify())
                print("Saved google_debug_playwright.html")
                
        except Exception as e:
            print(f"Exception: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_stealth_google()

if __name__ == "__main__":
    test_stealth_google()
