import asyncio
import nodriver as uc
import time
from bs4 import BeautifulSoup

async def main():
    print("--- Testing nodriver on Google ---")
    browser = await uc.start(headless=True)
    page = await browser.get("https://www.google.com/search?q=machine+learning")
    
    # Wait for potential CAPTCHA to resolve or page to load
    print("Waiting 10 seconds for Cloudflare/Turnstile...")
    await asyncio.sleep(10)
    
    html = await page.get_content()
    soup = BeautifulSoup(html, "html.parser")
    
    results = soup.select("div.g")
    print(f"Found {len(results)} organic links (div.g)")
    
    if len(results) == 0:
        print("Failed to find results. Dumping raw HTML for debug...")
        print("TITLE:", soup.title.string if soup.title else "No Title")
        with open("google_debug_nodriver.html", "w") as f:
            f.write(soup.prettify())
        print("Saved google_debug_nodriver.html")
    else:
        for div in results[:3]:
            h3 = div.select_one("h3")
            a = div.select_one("a")
            if h3 and a:
                print(f" - {h3.text.strip()} | {a.get('href', '')}")

    browser.stop()

if __name__ == '__main__':
    asyncio.run(main())
