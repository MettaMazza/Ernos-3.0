"""
Script to resend missed autonomy research files to the ernos-research channel.
Run this once when the bot is online to send the recovered .md files.

Usage: Import and call `await resend_missed_research(bot)` from a bot command or startup.
"""
import discord
import logging
from pathlib import Path

logger = logging.getLogger("ResearchResend")

RESEARCH_CHANNEL_ID = 1447560747982000172

async def resend_missed_research(bot, limit: int = 20):
    """
    Sends autonomy research .md files from memory/core/research/ to the research channel.
    These are autonomy creations that were missed due to prior channel routing issues.
    
    Args:
        bot: Discord bot instance
        limit: Maximum files to send (to avoid flooding, default 20)
    """
    research_dir = Path("memory/core/research")
    
    if not research_dir.exists():
        logger.info("No research directory found.")
        return "No research to resend."
    
    md_files = sorted(research_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not md_files:
        logger.info("No research files found.")
        return "No research to resend."
    
    channel = bot.get_channel(RESEARCH_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find research channel {RESEARCH_CHANNEL_ID}")
        return f"Error: Could not find channel {RESEARCH_CHANNEL_ID}"
    
    # Send notification
    await channel.send(f"📚 **Recovering {min(limit, len(md_files))} missed autonomy research files...**")
    
    sent_count = 0
    for md_file in md_files[:limit]:
        try:
            # Extract topic from filename
            topic = md_file.stem.replace("research_", "").replace("_", " ")[:50]
            
            file = discord.File(str(md_file))
            await channel.send(
                f"🔬 **Recovered Research**: {topic}",
                file=file
            )
            sent_count += 1
            logger.info(f"Sent: {md_file.name}")
        except Exception as e:
            logger.error(f"Failed to send {md_file.name}: {e}")
    
    await channel.send(f"✅ **Recovery complete**: {sent_count}/{min(limit, len(md_files))} files sent.")
    return f"Resent {sent_count}/{min(limit, len(md_files))} research files to ernos-research channel."


# If run directly (requires bot to be available)
if __name__ == "__main__":
    print("This script should be run from within the bot context.")
    print("Call: await resend_missed_research(bot)")
    print(f"\nNote: There are {len(list(Path('memory/core/research').glob('*.md')))} research files available.")
