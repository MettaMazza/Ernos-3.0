import logging
import discord
import asyncio
from typing import Dict
from .synthesizer import AudioSynthesizer
from .transcriber import AudioTranscriber

logger = logging.getLogger("Voice.Manager")

class VoiceManager:
    """
    Manages Discord Voice connections, TTS, and STT.
    """
    def __init__(self, bot):
        self.bot = bot
        self.synthesizer = AudioSynthesizer()
        self.transcriber = AudioTranscriber()
        self.active_connections: Dict[int, discord.VoiceClient] = {}

    async def join_channel(self, channel: discord.VoiceChannel):
        """Joins a voice channel."""
        if channel.guild.id in self.active_connections:
            return self.active_connections[channel.guild.id]
        
        try:
            vc = await channel.connect()
            self.active_connections[channel.guild.id] = vc
            logger.info(f"Joined voice channel: {channel.name}")
            return vc
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            return None

    async def leave_channel(self, guild_id: int):
        """Leaves a voice channel."""
        if guild_id in self.active_connections:
            vc = self.active_connections.pop(guild_id)
            await vc.disconnect()
            logger.info(f"Left voice channel in guild {guild_id}")

    async def get_audio_path(self, text: str) -> str:
        """Generates or retrieves cached audio path."""
        import hashlib
        import os
        import time
        
        cache_dir = "memory/cache/tts"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Cleanup old cache files (12 hour expiration)
        self._cleanup_cache(cache_dir, max_age_hours=12)
        
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        output_path = os.path.join(cache_dir, f"{text_hash}.wav")
        
        if os.path.exists(output_path):
             logger.info(f"Using cached TTS: {output_path}")
             return output_path
        else:
             logger.info(f"Generating new TTS for: {text[:20]}...")
             return await self.synthesizer.generate_audio(text, output_path)

    def _cleanup_cache(self, cache_dir: str, max_age_hours: int = 12):
        """Delete TTS cache files older than max_age_hours."""
        import os
        import time
        
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        deleted_count = 0
        
        try:
            for filename in os.listdir(cache_dir):
                if filename.endswith('.wav'):
                    filepath = os.path.join(cache_dir, filename)
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"TTS cache cleanup: deleted {deleted_count} files older than {max_age_hours}h")
        except Exception as e:
            logger.warning(f"TTS cache cleanup error: {e}")

    async def speak(self, guild_id: int, text: str):
        """Synthesizes text and plays it in the voice channel."""
        if guild_id not in self.active_connections:
            logger.warning("Not connected to voice in this guild.")
            return

        vc = self.active_connections[guild_id]
        if not vc.is_connected():
            return
            
        audio_file = await self.get_audio_path(text)
        
        if audio_file:
            source = discord.FFmpegPCMAudio(audio_file)
            if not vc.is_playing():
                vc.play(source, after=lambda e: logger.info("Finished speaking."))
            else:
                # If already playing, maybe stop and play new? 
                # User said "pm4 is deleted", maybe they want to toggle?
                # For now, we interrupt.
                vc.stop()
                vc.play(source, after=lambda e: logger.info("Finished speaking."))
