import os
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("HF_API_TOKEN")

model_id = "cerspense/zeroscope_v2_576w"
print(f"Testing {model_id}...")

try:
    client = InferenceClient(token=token)
    client.text_to_video("A flowing river", model=model_id)
    print("SUCCESS: Zeroscope works!")
except Exception as e:
    print(f"FAILED: {e}")
