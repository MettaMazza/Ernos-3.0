from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import random

def test_cffi_advanced_impersonate():
    print("--- Testing Advanced curl_cffi on Google ---")
    url = "https://www.google.com/search?q=machine+learning"
    
    # We use impersonate="chrome120" which automatically sets up a Chrome 120 TLS fingerprint
    # and HTTP/2 framing. We also pass a legitimate User-Agent just in case.
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": "\"Not A(Brand\";v=\"99\", \"Google Chrome\";v=\"121\", \"Chromium\";v=\"121\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"macOS\"",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        response = requests.get(
            url,
            impersonate="chrome120",
            headers=headers,
            timeout=15
        )
        
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.text, "html.parser")
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
            with open("google_debug_cffi.html", "w") as f:
                f.write(soup.prettify())
            print("Saved google_debug_cffi.html")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_cffi_advanced_impersonate()
