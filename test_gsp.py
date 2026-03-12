import googlesearch

try:
    results = list(googlesearch.search("machine learning", num_results=10, sleep_interval=2))
    print(f"Found {len(results)} results")
    for r in results[:3]:
        print(r)
except Exception as e:
    print(f"Failed: {e}")
