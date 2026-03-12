from kokoro_onnx import Kokoro
import soundfile as sf
import os
import sys

# Define expected paths
BASE_DIR = os.getcwd() # Should be Ernos 3.0
KOKORO_MODEL_PATH = os.path.join(BASE_DIR, "memory", "public", "voice_models", "kokoro-v0_19.onnx")
KOKORO_VOICES_PATH = os.path.join(BASE_DIR, "memory", "public", "voice_models", "voices.npz")

print(f"Checking paths:")
print(f"Model: {KOKORO_MODEL_PATH} -> Exists: {os.path.exists(KOKORO_MODEL_PATH)}")
print(f"Voices: {KOKORO_VOICES_PATH} -> Exists: {os.path.exists(KOKORO_VOICES_PATH)}")

try:
    print("Initializing Kokoro...")
    kokoro = Kokoro(KOKORO_MODEL_PATH, KOKORO_VOICES_PATH)
    print("Success!")
except Exception as e:
    print(f"Initialization Failed: {e}")
