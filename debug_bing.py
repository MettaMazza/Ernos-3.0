import requests
from bs4 import BeautifulSoup
import urllib.parse
from fake_useragent import UserAgent

def debug_bing():
    query = "offshore wind farm projects commissioning 2026"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={encoded}"
    
    ua = UserAgent()
    headers = {
        "User-Agent": ua.chrome,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "TE": "trailers"
    }
    
    print(f"Testing Bing URL: {url}")
    session = requests.Session()
    try:
        response = session.get(url, headers=headers, timeout=10)
        html = response.text
        
        print(f"Bing Response Code: {response.status_code}")
        print(f"Bing Response Length: {len(html)} characters")
        soup = BeautifulSoup(html, "html.parser")
        
        results = soup.select("li.b_algo")
        print(f"Bing found {len(results)} 'li.b_algo' elements.")
        
        if len(results) > 0:
            for div in results[:3]:
                h2 = div.select_one("h2 a")
                print(f" - {h2.text if h2 else 'No Title'}")
        else:
            print("Turnstile? ", "turnstile" in html.lower())
                
    except Exception as e:
        print(f"Bing Error: {e}")

if __name__ == "__main__":
    debug_bing()
