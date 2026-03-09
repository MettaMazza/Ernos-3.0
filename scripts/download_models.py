import torch
from diffusers import FluxPipeline, LTXPipeline
from huggingface_hub import login
import sys

# Models defined in config/settings.py
FLUX_MODEL = "black-forest-labs/FLUX.1-dev"
LTX_MODEL = "Lightricks/LTX-Video"

def download_models():
    # Check for token argument
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print(f"🔑 Logging in with provided token...")
        login(token=token, add_to_git_credential=True)
    
    print(f"\n⬇️  Downloading Flux Image Model: {FLUX_MODEL}...")
    try:
        FluxPipeline.from_pretrained(
            FLUX_MODEL,
            torch_dtype=torch.bfloat16
        )
        print("✅ Flux downloaded successfully.")
    except Exception as e:
        print(f"❌ Flux download failed: {e}")

    print(f"\n⬇️  Downloading LTX Video Model: {LTX_MODEL}...")
    try:
        LTXPipeline.from_pretrained(
            LTX_MODEL,
            torch_dtype=torch.bfloat16
        )
        print("✅ LTX downloaded successfully.")
    except Exception as e:
        print(f"❌ LTX download failed: {e}")

if __name__ == "__main__":
    download_models()
