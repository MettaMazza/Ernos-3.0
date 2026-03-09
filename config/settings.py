import os
import logging
from typing import Set, List
import dotenv # type: ignore
from dotenv import load_dotenv


load_dotenv()


# Logging setup removed (handled in main.py)
logger = logging.getLogger("ErnosConfig")

# Identity
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1299810741984956449"))
ADMIN_IDS = {
    1299810741984956449,   # Maria
    1282286389953695745,   # Admin 2
}
SYSTEM_CORE_ID = 0  # Sentinel ID for Internal Autonomous Actions
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "1469739123056054376"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID", "1471572249206325280"))
MIND_CHANNEL_ID = int(os.getenv("MIND_CHANNEL_ID", "1407440722348740738"))
DEV_CHANNEL_ID = int(os.getenv("DEV_CHANNEL_ID", "1472300695121170629"))
RESEARCH_CHANNEL_ID = int(os.getenv("RESEARCH_CHANNEL_ID", "1447560747982000172"))
PERSONA_CHAT_CHANNEL_ID = int(os.getenv("PERSONA_CHAT_CHANNEL_ID", "1469713200315367490"))
OUTREACH_CHANNEL_ID = int(os.getenv("OUTREACH_CHANNEL_ID", "0"))
PATREON_URL = os.getenv("PATREON_URL", "https://www.patreon.com/c/TheErnOSGardens")
CODE_AUDIT_CHANNEL_ID = int(os.getenv("CODE_AUDIT_CHANNEL_ID", "1463279232208601150"))
ERNOS_CODE_CHANNEL_ID = int(os.getenv("ERNOS_CODE_CHANNEL_ID", "1463279232208601150"))
ADMIN_USER_ID = ADMIN_ID  # Alias for review_pipeline DMs
BLOCKED_IDS = [
    804137266435850280,
    734147888640163940,
    1455318873481150596
]
BLOCKED_MESSAGE = "Sorry, you have been blocked from interacting with me. Reach out to the admin @metta_mazza to help resolve this."

# DM Ban List - Users who can still chat publicly but are blocked from DMs
# They receive a trust-based rejection message instead
DM_BANNED_IDS = [
    378425638962462720,  # DM restricted
]
DM_BAN_MESSAGE = "Sorry, I've decided my trust level is too low in this discussion. You can have it in public on #ernos-chat but your DMs are now restricted. Reach out to the admin @metta_mazza to help resolve this. Thank you."

# DM Global Toggle - Set to False during update testing periods
DMS_ENABLED = True
DM_CLOSED_MESSAGE = (
    "🌿 **DMs are currently closed** while we test the new ErnOS 3.1 update!\n\n"
    "You can still talk to me in **#ernos-chat**, or say **\"Ernos, start a thread\"** "
    "and I'll create a public space for us so Maria can monitor development.\n\n"
    "See you there! 🌱"
)

# Testing Mode Toggle - When True, only ADMIN_IDS can interact; all others are silently ignored
TESTING_MODE = False
TESTING_MODE_MESSAGE = (
    "🔧 **Ernos is currently in testing mode** and only responding to admins.\n\n"
    "Check back soon — we'll be live again shortly! 🌱"
)

# Ollama Global Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- RAG Models (Cloud & Local) ---
# Used for /cloud (RAG enabled)
OLLAMA_CLOUD_MODEL = os.getenv("OLLAMA_CLOUD_MODEL", "gemini-3-flash-preview:cloud")
# Used for /local (RAG enabled)
OLLAMA_LOCAL_MODEL = os.getenv("OLLAMA_LOCAL_MODEL", "qwen3-vl:32b")

# Context Window Limits (Characters)
# Cloud: ~1M tokens * 4 chars = ~4M chars
CONTEXT_CHAR_LIMIT_CLOUD = int(os.getenv("CONTEXT_CHAR_LIMIT_CLOUD", "4000000"))
# Local: ~128k tokens * 4 chars = ~512k chars
CONTEXT_CHAR_LIMIT_LOCAL = int(os.getenv("CONTEXT_CHAR_LIMIT_LOCAL", "500000"))

# Output Token Limits (num_predict for Ollama)
# Controls max tokens the LLM can generate per response.
# Too low = truncated code/HTML files. Set high to match model capacity.
# Cloud (Gemini 3): 1M context window — allow generous output
OUTPUT_TOKEN_LIMIT_CLOUD = int(os.getenv("OUTPUT_TOKEN_LIMIT_CLOUD", "65536"))
# Local (qwen3-vl:32b): 128k context — allow generous output
OUTPUT_TOKEN_LIMIT_LOCAL = int(os.getenv("OUTPUT_TOKEN_LIMIT_LOCAL", "32768"))

# Embedding Model (Shared)
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest") 

# --- Steering Mode Config (/local2) ---
# Used for /local2 (Steering Engine)
STEERING_MODEL_PATH = os.getenv("STEERING_MODEL_PATH", "./models/local_model.gguf")
CONTROL_VECTOR_PATH = os.getenv("CONTROL_VECTOR_PATH", "")

# --- Media Generation (Flux/LTX) ---
# MEDIA_BACKEND: "cloud" (HuggingFace Inference API) or "local" (diffusers on device)
MEDIA_BACKEND = os.getenv("MEDIA_BACKEND", "cloud")
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
FLUX_MODEL_PATH = os.getenv("FLUX_MODEL_PATH", "black-forest-labs/FLUX.1-dev")
LTX_MODEL_PATH = os.getenv("LTX_MODEL_PATH", "Lightricks/LTX-Video")
DAILY_IMAGE_LIMIT = int(os.getenv("DAILY_IMAGE_LIMIT", "4"))
DAILY_VIDEO_LIMIT = int(os.getenv("DAILY_VIDEO_LIMIT", "1"))

# Privacy
ENABLE_PRIVACY_SCOPES = os.getenv("ENABLE_PRIVACY_SCOPES", "true").lower() in ("true", "1", "yes")

# --- Knowledge Graph (Neo4j) ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
if NEO4J_PASSWORD == "password":
    logger.warning("NEO4J_PASSWORD is using the default 'password' — set a strong password via .env before production deployment")

logger.info(f"Loaded config. Local: {OLLAMA_LOCAL_MODEL}, Local2 (Steering): {STEERING_MODEL_PATH}")

# --- Voice System (Kokoro ONNX) ---
# Paths relative to project root
KOKORO_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "public", "voice_models", "kokoro-v0_19.onnx")
KOKORO_VOICES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "public", "voice_models", "voices.json")
KOKORO_DEFAULT_VOICE = "am_michael"

# --- Creative (Image/Video) ---
# Model IDs used for both local (diffusers) and cloud (HF Inference API)
# Set MEDIA_BACKEND=local and download models to ~/.cache/huggingface for local use
