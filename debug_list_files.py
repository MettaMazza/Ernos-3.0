from huggingface_hub import list_repo_files

repos = ["hexgrad/Kokoro-82M", "adrianlyjak/kokoro-onnx", "onnx-community/Kokoro-82M-v1.0-ONNX", "onnx-community/Kokoro-82M-ONNX"]

print("Listing files in repositories...")
for repo in repos:
    print(f"\n--- {repo} ---")
    try:
        files = list_repo_files(repo)
        for f in files:
            print(f"  {f}")
    except Exception as e:
        print(f"  Error: {e}")
