import re

with open("src/tools/web.py", "r") as f:
    content = f.read()

def replace_urllib_with_cloudscraper(func_body, indent="        "):
    # Look for the urllib import and the urlopen block
    import_pattern = r"import urllib\.request\n\s*import urllib\.parse\n\s*from bs4 import BeautifulSoup"
    import_replace = "import urllib.parse\n" + indent[:-4] + "from bs4 import BeautifulSoup\n" + indent[:-4] + "import cloudscraper"
    
    req_pattern = r"encoded = urllib\.parse\.quote_plus\(query\)\n(.*?)with urllib\.request\.urlopen\(req, timeout=10\) as response:\n\s*html = response\.read\(\)\.decode\('utf-8'(?:, errors='ignore')?\)\n\n\s*soup = BeautifulSoup\(html, \"html\.parser\"\)"
    
    req_replace = "encoded = urllib.parse.quote_plus(query)\n" + indent[:-4] + "url = f\"https://www.{DOMAIN}/search?q={encoded}\"\n" + indent[:-4] + "if 'yahoo' in '{DOMAIN}':\n" + indent + 'url = f"https://search.yahoo.com/search?p={{encoded}}"\n' + indent[:-4] + "scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})\n" + indent[:-4] + "response = scraper.get(url, timeout=10)\n" + indent[:-4] + "html = response.text\n\n" + indent[:-4] + "soup = BeautifulSoup(html, \"html.parser\")"

    return content

# I will just write a simpler regex

import_pattern = r"(import urllib\.request\s*import urllib\.parse\s*from bs4 import BeautifulSoup\s*encoded = urllib\.parse\.quote_plus\(query\)\s*url = [^\n]+(?:.|\n)*?with urllib\.request\.urlopen\(req, timeout=10\) as response:\s*html = response\.read\(\)\.decode\('utf-8'(?:, errors='ignore')?\)\s*soup = BeautifulSoup\(html, \"html\.parser\"\))"

import re

blocks = re.findall(import_pattern, content)
for i, block in enumerate(blocks):
    domain = 'google.com'
    if 'bing.com' in block:
        domain = 'bing.com'
    elif 'yahoo.com' in block:
        domain = 'yahoo.com'
        
    url_line = f'url = f"https://www.{domain}/search?q={{encoded}}"'
    if domain == 'yahoo.com':
        url_line = f'url = f"https://search.yahoo.com/search?p={{encoded}}"'

    replacement = f"""import urllib.parse
        from bs4 import BeautifulSoup
        import cloudscraper

        encoded = urllib.parse.quote_plus(query)
        {url_line}
        
        scraper = cloudscraper.create_scraper(browser={{'browser': 'chrome', 'platform': 'darwin', 'desktop': True}})
        response = scraper.get(url, timeout=10)
        html = response.text

        soup = BeautifulSoup(html, "html.parser")"""
    
    content = content.replace(block, replacement)

with open("src/tools/web.py", "w") as f:
    f.write(content)
print("Patched!")
