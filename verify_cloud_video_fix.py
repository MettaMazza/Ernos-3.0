import os
import sys
import logging
import httpx
from config import settings

sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)

def verify_video_fix():
    print("Testing Cloud Video (Direct HTTPX POST)...")
    
    token = settings.HF_API_TOKEN
    model = "damo-vilab/text-to-video-ms-1.7b"
    api_url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": "A drone shot of a futuristic city"}

    print(f"Target: {api_url}")
    
    try:
        response = httpx.post(api_url, headers=headers, json=payload, timeout=60.0)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS! Video bytes received.")
            with open("verify_video_direct.mp4", "wb") as f:
                f.write(response.content)
            print("Saved to verify_video_direct.mp4")
        else:
            print(f"❌ FAILED: {response.text}")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    verify_video_fix()
