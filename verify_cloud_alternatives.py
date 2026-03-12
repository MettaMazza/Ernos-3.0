import os
import sys
import logging
from huggingface_hub import InferenceClient
from config import settings

sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)

def verify_alternatives():
    print("Testing Alternative Cloud Models...")
    
    token = settings.HF_API_TOKEN
    client = InferenceClient(token=token)
    
    # 1. Test Flux Schnell (Often free/cheaper)
    print(f"\n[1/2] Testing Cloud Image (FLUX.1-schnell)...")
    try:
        image = client.text_to_image(
            "A futuristic city with glowing neon lights",
            model="black-forest-labs/FLUX.1-schnell", 
            width=1024,
            height=1024
        )
        image.save("verify_cloud_schnell.png")
        print("✅ Cloud Image (Schnell): SUCCESS")
    except Exception as e:
        print(f"❌ Cloud Image (Schnell) FAILED: {e}")

    # 2. Test Older Video Model (Known to work on free tier?)
    # "Ali-Vilab/text-to-video-ms-1.7b" or "damo-vilab/text-to-video-ms-1.7b"
    print(f"\n[2/2] Testing Cloud Video (MS-1.7b)...")
    try:
        video_bytes = client.text_to_video(
            "A drone shot of a futuristic city",
            model="damo-vilab/text-to-video-ms-1.7b"
        )
        with open("verify_cloud_ms17b.mp4", "wb") as f:
            f.write(video_bytes)
        print("✅ Cloud Video (MS-1.7b): SUCCESS")
    except Exception as e:
        print(f"❌ Cloud Video (MS-1.7b) FAILED: {e}")

if __name__ == "__main__":
    verify_alternatives()
