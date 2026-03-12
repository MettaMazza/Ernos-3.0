"""
Script to resend missed autonomy images to the ernos-imaging channel.
Run this once when the bot is online to send the recovered images.

Usage: Import and call `await resend_missed_images(bot)` from a bot command or startup.
"""
import discord
import logging
from pathlib import Path

logger = logging.getLogger("ImageResend")

IMAGING_CHANNEL_ID = 1445500249631096903

async def resend_missed_images(bot):
    """
    Sends all images in memory/core/media/ to the ernos-imaging channel.
    These are autonomy creations that were missed due to prior channel routing issues.
    """
    media_dir = Path("memory/core/media")
    
    if not media_dir.exists():
        logger.info("No media directory found.")
        return "No images to resend."
    
    images = list(media_dir.glob("*.png")) + list(media_dir.glob("*.jpg"))
    
    if not images:
        logger.info("No images found in media directory.")
        return "No images to resend."
    
    channel = bot.get_channel(IMAGING_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find imaging channel {IMAGING_CHANNEL_ID}")
        return f"Error: Could not find channel {IMAGING_CHANNEL_ID}"
    
    sent_count = 0
    for img in sorted(images):
        try:
            # Extract timestamp from filename
            timestamp = img.stem.split("_")[-1]
            
            file = discord.File(str(img))
            await channel.send(
                f"🎨 **Recovered Autonomy Creation** (from {timestamp})",
                file=file
            )
            sent_count += 1
            logger.info(f"Sent: {img.name}")
        except Exception as e:
            logger.error(f"Failed to send {img.name}: {e}")
    
    return f"Resent {sent_count}/{len(images)} images to ernos-imaging channel."


# If run directly (requires bot to be available)
if __name__ == "__main__":
    print("This script should be run from within the bot context.")
    print("Call: await resend_missed_images(bot)")
