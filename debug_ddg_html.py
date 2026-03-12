import requests
from bs4 import BeautifulSoup
import urllib.parse
from fake_useragent import UserAgent

def debug_ddg_html():
    query = "offshore wind farm projects commissioning 2026"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    
    ua = UserAgent()
    headers = {
        "User-Agent": ua.chrome,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://duckduckgo.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1"
    }
    
    print(f"Testing DDG URL: {url}")
    session = requests.Session()
    try:
        response = session.get(url, headers=headers, timeout=10)
        html = response.text
        
        print(f"DDG HTML Response Code: {response.status_code}")
        print(f"DDG HTML Length: {len(html)} characters")
        soup = BeautifulSoup(html, "html.parser")
        
        results = soup.select("a.result__url")
        print(f"DDG HTML found {len(results)} 'a.result__url' elements.")
        
        if len(results) > 0:
            for a in results[:3]:
                print(f" - {a.get('href')}")
        else:
            print("Content snippet (first 1000 chars):\n")
            print(html[:1000])
                
    except Exception as e:
        print(f"DDG HTML Error: {e}")

if __name__ == "__main__":
    debug_ddg_html()
