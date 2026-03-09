from huggingface_hub import hf_hub_download
import os
import shutil

repo_id = "onnx-community/Kokoro-82M-v1.0-ONNX"
filename = "onnx/model.onnx"
local_dir = "memory/public/voice_models"
target_name = "kokoro-v0_19.onnx" # Keep old name for compatibility with settings

print(f"Downloading {filename} from {repo_id}...")
try:
    # force_download=True to ensure fresh copy if cached
    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        force_download=True
    )
    print(f"Downloaded to: {path}")
    
    expected_path = os.path.join(local_dir, target_name)
    
    # If download path is different from target, move it
    if os.path.abspath(path) != os.path.abspath(expected_path):
        print(f"Moving {path} -> {expected_path}")
        shutil.move(path, expected_path)
        
        # Cleanup created subdirs
        parent = os.path.dirname(path) # memory/public/voice_models/onnx
        if os.path.exists(parent) and not os.listdir(parent):
            os.rmdir(parent)
            
    # Verify
    if os.path.exists(expected_path):
        size = os.path.getsize(expected_path)
        print(f"Success. File size: {size} bytes ({size / (1024*1024):.2f} MB)")
    else:
        print("Error: Target file missing.")

except Exception as e:
    print(f"Download failed: {e}")
