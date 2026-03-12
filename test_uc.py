import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import urllib.parse
import time

def test_uc():
    query = "offshore wind farm projects commissioning 2026"
    encoded = urllib.parse.quote_plus(query)
    urls = {
        "Google": (f"https://www.google.com/search?q={encoded}", "div.g"),
        "Bing": (f"https://www.bing.com/search?q={encoded}", "li.b_algo")
    }

    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    driver = uc.Chrome(options=options)
    
    for name, (url, selector) in urls.items():
        print(f"\nEvaluating {name} with UC...")
        try:
            driver.get(url)
            time.sleep(2)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            results = soup.select(selector)
            
            print(f"  Len: {len(html)}")
            print(f"  Found '{selector}': {len(results)}")
            
            is_captcha = "turnstile" in html.lower() or "recaptcha" in html.lower() or 'id="captcha-form"' in html.lower()
            print(f"  CAPTCHA keywords found: {is_captcha}")
            
        except Exception as e:
            print(f"  Error: {e}")
            
    driver.quit()

if __name__ == "__main__":
    test_uc()
