import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.tools.web import _robust_ddgs_text, _fallback_google_search, _fallback_bing_search, _fallback_yahoo_search
from ddgs import DDGS

def test_tier_1_ddgs(query):
    print("\n[TIER 1] DuckDuckGo (via `ddgs` library)")
    try:
        with DDGS() as ddgs:
            results = _robust_ddgs_text(ddgs, query, max_results=3)
            print(f"✅ SUCCESS: {len(results)} results found.")
            if results: print(f"Sample: {results[0].get('title')}")
            return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def test_tier_2_google(query):
    print("\n[TIER 2] Google Scraper")
    results = _fallback_google_search(query, max_results=3)
    if results:
        print(f"✅ SUCCESS: {len(results)} results found.")
        print(f"Sample: {results[0].get('title')}")
        return True
    else:
        print("❌ FAILED: Returned 0 results. (Likely HTTP 429 / Recaptcha)")
        return False

def test_tier_3_bing(query):
    print("\n[TIER 3] Bing Scraper")
    results = _fallback_bing_search(query, max_results=3)
    if results:
        print(f"✅ SUCCESS: {len(results)} results found.")
        print(f"Sample: {results[0].get('title')}")
        return True
    else:
        print("❌ FAILED: Returned 0 results. (Likely Cloudflare/JS challenge blocking)")
        return False

def test_tier_4_yahoo(query):
    print("\n[TIER 4] Yahoo Scraper")
    results = _fallback_yahoo_search(query, max_results=3)
    if results:
        print(f"✅ SUCCESS: {len(results)} results found.")
        print(f"Sample: {results[0].get('title')}")
        return True
    else:
        print("❌ FAILED: Returned 0 results.")
        return False

if __name__ == "__main__":
    test_query = "offshore wind farm projects commissioning 2026"
    print(f"🚀 EXECUTING LIVE SEARCH TIER ANALYSIS")
    print(f"Query: '{test_query}'\n")
    print("This script hits every search backend simultaneously to demonstrate why the fallback cascade is required when primary engines fail during deep-research swarms.")
    
    t1 = test_tier_1_ddgs(test_query)
    t2 = test_tier_2_google(test_query)
    t3 = test_tier_3_bing(test_query)
    t4 = test_tier_4_yahoo(test_query)
    
    print("\n=== SUMMARY ===")
    print(f"Tier 1 (DDGS API): {'✅ PASS' if t1 else '❌ FAIL'}")
    print(f"Tier 2 (Google Web): {'✅ PASS' if t2 else '❌ FAIL'}")
    print(f"Tier 3 (Bing Web): {'✅ PASS' if t3 else '❌ FAIL'}")
    print(f"Tier 4 (Yahoo Web): {'✅ PASS' if t4 else '❌ FAIL'}")
