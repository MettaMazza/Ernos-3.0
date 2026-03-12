import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())

from config import settings
from huggingface_hub import InferenceClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyCloud")

def verify_cloud():
    print("Locked & Loaded: Verifying Cloud Credentials & API...")
    
    token = settings.HF_API_TOKEN
    if not token:
        print("ERROR: No HF_API_TOKEN found in settings.")
        return

    client = InferenceClient(token=token)
    
    # 1. Test Image (Flux)
    print(f"\n[1/2] Testing Cloud Image (Flux: {settings.FLUX_MODEL_PATH})...")
    try:
        # Call API directly to avoid fallback logic
        image = client.text_to_image(
            "A futuristic city with glowing neon lights, cyberpunk style",
            model=settings.FLUX_MODEL_PATH,
            width=1024,
            height=1024
        )
        image.save("verify_cloud_image.png")
        print("✅ Cloud Image Generation: SUCCESS")
    except Exception as e:
        print(f"❌ Cloud Image Generation FAILED: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test Video (LTX)
    print(f"\n[2/2] Testing Cloud Video (LTX: {settings.LTX_MODEL_PATH})...")
    try:
        # Call API directly
        video_bytes = client.text_to_video(
            "A drone shot of a futuristic city",
            model=settings.LTX_MODEL_PATH
        )
        with open("verify_cloud_video.mp4", "wb") as f:
            f.write(video_bytes)
        print("✅ Cloud Video Generation: SUCCESS")
    except Exception as e:
        print(f"❌ Cloud Video Generation FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_cloud()
