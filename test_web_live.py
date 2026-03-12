import logging
import sys
import os

# Ensure Ernos src path is in resolution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.tools.web import search_web

logging.basicConfig(level=logging.INFO)

def run_live_test():
    query = "offshore wind farm projects commissioning 2026"
    print(f"\n==============================================")
    print(f"📡 RUNNING LIVE UN-MOCKED END-TO-END WEB TEST")
    print(f"==============================================\n")
    print(f"Query: '{query}'\n")
    
    # We will purposely pass a dummy loader that raises an Exception, 
    # to perfectly simulate the DuckDuckGo `ddgs` Python package failing or rate-limiting.
    def force_ddgs_failure():
        raise Exception("Simulated DDGS Rate Limit / Timeout")

    try:
        # Run the tool exactly as the agent swarm would, 
        # injecting the fake failure to trigger the new DDG HTML, Bing, and Yahoo cascade.
        results = search_web(query=query, _loader=force_ddgs_failure)
        
        print("\n=== FINAL TOOL OUTPUT RETURNED TO AGENT ===")
        print(results)
        print("===========================================")
        
        if "No results found" in results or not results.strip():
            print("\n❌ TEST FAILED: Fallbacks could not extract any links.")
            sys.exit(1)
        else:
            print("\n✅ TEST PASSED: Fallbacks successfully parsed organic text links.")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n❌ FATAL ERROR During Search: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_live_test()
