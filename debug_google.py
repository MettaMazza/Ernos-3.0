import requests
import urllib.parse
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

def debug_google():
    query = "offshore wind farm projects commissioning 2026"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    
    ua = UserAgent()
    headers = {
        "User-Agent": ua.chrome,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    
    print(f"Testing Google URL: {url}")
    session = requests.Session()
    try:
        response = session.get(url, headers=headers, timeout=10)
        html = response.text
        
        print(f"Google Response Code: {response.status_code}")
        print(f"Google Response Length: {len(html)} characters")
        soup = BeautifulSoup(html, "html.parser")
        
        results = soup.select("div.g")
        print(f"Google found {len(results)} 'div.g' elements.")
        
        if len(results) > 0:
            for div in results[:3]:
                h3 = div.select_one("h3")
                a = div.select_one("a")
                print(f" - {h3.text if h3 else 'No Title'}: {a.get('href') if a else ''}")
        else:
            print("Content snippet (first 1000 chars):\n")
            print(html[:1000])
            with open("google_debug.html", "w") as f:
                f.write(html)
                
    except Exception as e:
        print(f"Google Error: {e}")

if __name__ == "__main__":
    debug_google()
