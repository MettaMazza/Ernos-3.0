import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
import sys

def test_urllib(ua):
    url = f"https://www.google.com/search?q=python"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, "html.parser")
            links = len(soup.select("div.g"))
            print(f"[urllib] {ua}: Success, found {links} results")
    except Exception as e:
        print(f"[urllib] {ua}: Failed - {e}")

def test_cffi(ua):
    url = f"https://www.google.com/search?q=python"
    try:
        response = cffi_requests.get(
            url,
            headers={"User-Agent": ua},
            impersonate="chrome120",
            timeout=10
        )
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = len(soup.select("div.g"))
            print(f"[cffi] {ua}: Success, found {links} results")
        else:
            print(f"[cffi] {ua}: Failed - Status {response.status_code}")
    except Exception as e:
        print(f"[cffi] {ua}: Failed - {e}")

def test_cffi_no_ua():
    url = f"https://www.google.com/search?q=python"
    try:
        response = cffi_requests.get(
            url,
            impersonate="chrome120",
            timeout=10
        )
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = len(soup.select("div.g"))
            print(f"[cffi] default impersonate: Success, found {links} results")
        else:
            print(f"[cffi] default impersonate: Failed - Status {response.status_code}")
    except Exception as e:
        print(f"[cffi] default impersonate: Failed - {e}")


print("--- Testing Google Bypass ---")
uas = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "AdsBot-Google (+http://www.google.com/adsbot.html)",
    "Googlebot/2.1 (+http://www.google.com/bot.html)"
]

for ua in uas:
    test_urllib(ua)
    test_cffi(ua)

test_cffi_no_ua()
