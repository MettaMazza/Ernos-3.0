import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time

def test_google_uc():
    print("--- Testing uc on Google ---")
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    
    driver = None
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.set_page_load_timeout(30)
        
        url = "https://www.google.com/search?q=machine+learning"
        driver.get(url)
        time.sleep(5)
        
        html = driver.page_source
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
            print("TITLE:", soup.title.string if soup.title else "No Title")
            with open("google_debug.html", "w") as f:
                f.write(soup.prettify())
            print("Saved google_debug.html")
            
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    test_google_uc()
