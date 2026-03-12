import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time

def scrape_with_selenium():
    print("--- Testing Selenium Undetected Chrome on Google ---")
    options = uc.ChromeOptions()
    # Explicitly do NOT use headless so it matches the user's browser fingerprint
    
    # We add common arguments to avoid standard bot detection flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    
    driver = None
    try:
        # Initializing the driver without the subprocess flag to tie it directly to this thread's scope
        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # Navigate to Google
        url = "https://www.google.com/search?q=machine+learning"
        print(f"Loading {url}")
        driver.get(url)
        
        # Wait for the page to render (and any potential Javascript challenges to execute)
        time.sleep(5)
        
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # Google's organic search results are currently encapsulated in 'div.g'
        results = soup.select("div.g")
        print(f"Found {len(results)} organic links")
        
        if not results:
            print("TITLE:", soup.title.string if soup.title else "No Title")
            with open("google_selenium_debug.html", "w") as f:
                f.write(soup.prettify())
            print("Saved debug HTML.")
        else:
            for div in results[:3]:
                h3 = div.select_one("h3")
                a = div.select_one("a")
                if h3 and a:
                    print(f" - {h3.text.strip()} | {a.get('href', '')}")
                    
    except Exception as e:
         print(f"Exception: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    scrape_with_selenium()
