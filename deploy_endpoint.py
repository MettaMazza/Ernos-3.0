import os
import time
from huggingface_hub import create_inference_endpoint, get_inference_endpoint
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("HF_API_TOKEN")

repo_id = "cerspense/zeroscope_v2_576w"
endpoint_name = "ernos-zeroscope-video"

print(f"Attempting to deploy Private Endpoint for {repo_id}...")

try:
    # 1. Check if already exists
    try:
        endpoint = get_inference_endpoint(endpoint_name, token=token)
        print(f"Endpoint '{endpoint_name}' already exists. Status: {endpoint.status}")
    except Exception:
        endpoint = None

    # 2. Create if not exists
    if not endpoint:
        print("Creating new endpoint (using credits)...")
        endpoint = create_inference_endpoint(
            name=endpoint_name,
            repository=repo_id,
            framework="pytorch",
            task="text-to-video",
            accelerator="gpu",
            instance_size="medium",
            instance_type="nvidia-a10g",
            region="us-east-1",
            vendor="aws",
            token=token
        )
        print(f"Endpoint created: {endpoint.url}")

    # 3. Wait for initialization
    print("Waiting for endpoint to initialize (this can take 5-10 minutes)...")
    print("Do not interrupt this script.")
    
    # Simple polling loop if .wait() is flaky in old versions
    while endpoint.status in ["pending", "initializing"]:
        print(f"Status: {endpoint.status}...")
        time.sleep(30)
        endpoint.fetch()
    
    if endpoint.status == "running":
        print(f"SUCCESS! Endpoint is running at: {endpoint.url}")
        print("Update your .env with this URL as LTX_MODEL_PATH (or create a new var).")
    else:
        print(f"Endpoint failed to start. Status: {endpoint.status}")

except Exception as e:
    print(f"Deployment failed: {e}")
