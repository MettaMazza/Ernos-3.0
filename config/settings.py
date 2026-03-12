import os
import logging
from typing import Set, List
import dotenv # type: ignore
from dotenv import load_dotenv


load_dotenv()


# Logging setup removed (handled in main.py)
logger = logging.getLogger("ErnosConfig")

# Identity
TIMEZONE = os.getenv("TIMEZONE", "UTC")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_IDS = set()
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
if _admin_ids_raw:
    ADMIN_IDS = {int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()}
if ADMIN_ID and ADMIN_ID not in ADMIN_IDS:
    ADMIN_IDS.add(ADMIN_ID)
SYSTEM_CORE_ID = 0  # Sentinel ID for Internal Autonomous Actions

# Data Directory — all user data, logs, and state go here
# Docker users mount a volume at this path
ERNOS_DATA_DIR = os.getenv("ERNOS_DATA_DIR", "memory")

# Channel IDs (0 = disabled/unconfigured)
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "0"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID", "0"))
MIND_CHANNEL_ID = int(os.getenv("MIND_CHANNEL_ID", "0"))
DEV_CHANNEL_ID = int(os.getenv("DEV_CHANNEL_ID", "0"))
RESEARCH_CHANNEL_ID = int(os.getenv("RESEARCH_CHANNEL_ID", "0"))
PERSONA_CHAT_CHANNEL_ID = int(os.getenv("PERSONA_CHAT_CHANNEL_ID", "0"))
OUTREACH_CHANNEL_ID = int(os.getenv("OUTREACH_CHANNEL_ID", "0"))
PATREON_URL = os.getenv("PATREON_URL", "")
CODE_AUDIT_CHANNEL_ID = int(os.getenv("CODE_AUDIT_CHANNEL_ID", "0"))
SKILL_PROPOSALS_CHANNEL_ID = int(os.getenv("SKILL_PROPOSALS_CHANNEL_ID", "0"))
SCHEDULED_TASKS_CHANNEL_ID = int(os.getenv("SCHEDULED_TASKS_CHANNEL_ID", "0"))
ERNOS_CODE_CHANNEL_ID = int(os.getenv("ERNOS_CODE_CHANNEL_ID", "0"))
LISTEN_CHANNEL_IDS = set()
_listen_channels_raw = os.getenv("LISTEN_CHANNEL_IDS", "")
if _listen_channels_raw:
    LISTEN_CHANNEL_IDS = {int(x.strip()) for x in _listen_channels_raw.split(",") if x.strip().isdigit()}
ADMIN_USER_ID = ADMIN_ID  # Alias for review_pipeline DMs

# Blocked Users (comma-separated IDs in env)
BLOCKED_IDS = []
_blocked_raw = os.getenv("BLOCKED_IDS", "")
if _blocked_raw:
    BLOCKED_IDS = [int(x.strip()) for x in _blocked_raw.split(",") if x.strip().isdigit()]
BLOCKED_MESSAGE = os.getenv("BLOCKED_MESSAGE", "Sorry, you have been blocked from interacting with me. Reach out to the admin to help resolve this.")

# DM Ban List (comma-separated IDs in env)
DM_BANNED_IDS = []
_dm_banned_raw = os.getenv("DM_BANNED_IDS", "")
if _dm_banned_raw:
    DM_BANNED_IDS = [int(x.strip()) for x in _dm_banned_raw.split(",") if x.strip().isdigit()]
DM_BAN_MESSAGE = os.getenv("DM_BAN_MESSAGE", "Sorry, your DMs are currently restricted. Reach out to the admin to help resolve this.")

# DM Global Toggle - Set to False during update testing periods
DMS_ENABLED = False
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

# Feature Toggles
AUTONOMY_LITE_MODE = os.getenv("AUTONOMY_LITE_MODE", "false").lower() in ("true", "1", "yes")
ENABLE_TOWN_HALL = os.getenv("ENABLE_TOWN_HALL", "false").lower() in ("true", "1", "yes")
ENABLE_WORK_MODE = os.getenv("ENABLE_WORK_MODE", "false").lower() in ("true", "1", "yes")
LISTEN_TO_BOTS = os.getenv("LISTEN_TO_BOTS", "false").lower() in ("true", "1", "yes")

# --- Knowledge Graph (Neo4j) ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
if NEO4J_PASSWORD == "password":
    logger.warning("NEO4J_PASSWORD is using the default 'password' — consider changing it in .env for production")

logger.info(f"Loaded config. Local: {OLLAMA_LOCAL_MODEL}, Local2 (Steering): {STEERING_MODEL_PATH}")

# --- Voice System (Kokoro ONNX) ---
# Paths relative to data dir
_data_root = os.path.dirname(os.path.dirname(__file__))
KOKORO_MODEL_PATH = os.path.join(_data_root, ERNOS_DATA_DIR, "public", "voice_models", "kokoro-v0_19.onnx")
KOKORO_VOICES_PATH = os.path.join(_data_root, ERNOS_DATA_DIR, "public", "voice_models", "voices.json")
KOKORO_DEFAULT_VOICE = "am_michael"

# --- Creative (Image/Video) ---
# Model IDs used for both local (diffusers) and cloud (HF Inference API)
# Set MEDIA_BACKEND=local and download models to ~/.cache/huggingface for local use

# --- Garden: Proof of Contribution System ---
GARDEN_GUILD_ID = int(os.getenv("GARDEN_GUILD_ID", "0"))
GARDEN_ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("GARDEN_ANNOUNCEMENT_CHANNEL_ID", "0"))
GARDEN_ANNOUNCEMENT_MESSAGE_ID = int(os.getenv("GARDEN_ANNOUNCEMENT_MESSAGE_ID", "0"))
POLLINATOR_ROLE_ID = int(os.getenv("POLLINATOR_ROLE_ID", "0"))
PLANTER_ROLE_ID = int(os.getenv("PLANTER_ROLE_ID", "0"))
GARDENER_ROLE_ID = int(os.getenv("GARDENER_ROLE_ID", "0"))
TERRAFORMER_ROLE_ID = int(os.getenv("TERRAFORMER_ROLE_ID", "0"))
