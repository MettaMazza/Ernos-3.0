import asyncio
import logging
from logging.handlers import RotatingFileHandler
import warnings
# Scope warning suppression to noisy libraries only
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"phonemizer|espeakng|kokoro")
import os
import sys

# Add project root to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Logging
# Session Error Handler (Refreshes on startup, captures WARNING+)
session_error_handler = logging.FileHandler("session_error.log", mode='w')
session_error_handler.setLevel(logging.WARNING)
session_error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler("ernos_bot.log", maxBytes=10*1024*1024, backupCount=5),
        session_error_handler
    ]
)

# Silence noisy external libraries
logging.getLogger("phonemizer").setLevel(logging.ERROR)
logging.getLogger("espeakng").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("primp").setLevel(logging.WARNING)

from config import settings
from src.bot.client import ErnosBot

logger = logging.getLogger("Main")

async def main():
    if not settings.DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN environment variable not set. Exiting.")
        sys.exit(1)

    logger.info("Initializing Ernos 3.0 Bot...")
    from src.bot import globals
    bot = ErnosBot()
    globals.bot = bot

    try:
        await bot.start(settings.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Bot crash: {e}")
    finally:
        await bot.close()

if __name__ == "__main__": # pragma: no cover
    asyncio.run(main())
