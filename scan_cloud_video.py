import os
from huggingface_hub import list_models, InferenceClient
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("HF_API_TOKEN")

print(f"Scanning for working text-to-video models with token: {token[:4]}...")

def test_model(model_id):
    print(f"\n[TEST] Testing {model_id}...")
    try:
        client = InferenceClient(token=token)
        # Try a simple generation
        client.text_to_video("A flowing river", model=model_id)
        print(f"[SUCCESS] {model_id} IS WORKING!")
        return True
    except Exception as e:
        print(f"[FAIL] {model_id}: {str(e)[:200]}...") # Truncate error
        return False

# 1. Get candidates from Hub
print("Fetching candidate models from Hub...")
try:
    # Filter for text-to-video and inference enabled
    models = list_models(filter="text-to-video", inference="warm", limit=10, sort="downloads", direction=-1)
    hub_candidates = [m.modelId for m in models]
except Exception as e:
    print(f"Could not list models: {e}")
    hub_candidates = []

# 2. Add manual popular list
manual_candidates = [
    "cerspense/zeroscope_v2_576w",
    "cerspense/zeroscope_v2_dark_30x576x30",
    "damo-vilab/text-to-video-ms-1.7b",
    "ali-vilab/text-to-video-ms-1.7b",
    "Lightricks/LTX-Video",
    "Imager/Noise-V-Video-Generation"
]

all_candidates = list(set(hub_candidates + manual_candidates))
print(f"Found {len(all_candidates)} candidates: {all_candidates}")

working_model = None

for model in all_candidates:
    if test_model(model):
        working_model = model
        break

if working_model:
    print(f"\n[CONCLUSION] FOUND WORKING MODEL: {working_model}")
else:
    print("\n[CONCLUSION] NO WORKING MODELS FOUND.")
