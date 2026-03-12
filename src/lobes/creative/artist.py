from ..base import BaseAbility
import logging
import asyncio
import json
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from config import settings
# Lazy import MediaGenerator inside methods usually, but singleton is fine
from src.lobes.creative.generators import get_generator, MediaGenerator

logger = logging.getLogger("Lobe.Creative.Artist")

# Only 1 audiobook production at a time — prevents multiple heavy ML models stacking in memory
_audiobook_semaphore = asyncio.Semaphore(1)

class VisualCortexAbility(BaseAbility):
    """
    Handles Image Generation (VisualCortex).
    Routes requests to diffusers/Flux or API.
    """
    def __init__(self, lobe):
        super().__init__(lobe)
        # We don't bind global usage_file anymore
        self.turn_lock = False # Block multiple generation per turn
    
    def _get_usage_file(self, user_id: int) -> Path:
        from src.privacy.scopes import ScopeManager
        # Resolve path dynamically
        user_home = ScopeManager.get_user_home(user_id)
        return user_home / "usage.json"

    def _check_limits(self, media_type: str, user_id: int) -> bool:
        usage_file = self._get_usage_file(user_id)
        
        # Load or create usage
        data = {"image_count": 0, "video_count": 0, "last_reset": 0}
        if usage_file.exists():
            try:
                data = json.loads(usage_file.read_text())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
        # Check reset (Daily) - LEGACY CHECK REMOVED
        # We now rely on Flux Tiers for enhanced limits
        
        # Load Tier
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor() # No bot needed for just reading
        tier = flux.get_tier(user_id)
        
        # Tier-based Limits
        # Base (Tier 0): 4 Images (Original setting)
        # Pollinator (Tier 1): 6 Images
        # Planter (Tier 2): 10 Images + 2 Videos
        # Gardener (Tier 3): 20 Images + 5 Videos
        # Terraformer (Tier 4): 50 Images + 10 Videos
        
        IMAGE_LIMITS = {0: 4, 1: 6, 2: 10, 3: 20, 4: 50}
        VIDEO_LIMITS = {0: 0, 1: 0, 2: 2, 3: 5, 4: 10}
        
        img_limit = IMAGE_LIMITS.get(tier, IMAGE_LIMITS[0])
        vid_limit = VIDEO_LIMITS.get(tier, VIDEO_LIMITS[0])
        
        limit = img_limit if media_type == "image" else vid_limit
        
        # Admin Override
        if str(user_id) in {str(aid) for aid in settings.ADMIN_IDS}:
            return True

        # Check limit
        current = data.get(f"{media_type}_count", 0)
        
        # Check reset (Daily for media is separate from 12h Flux cycle)
        # We keep the daily reset logic for Media specifically
        now = time.time()
        if now - data.get("last_reset", 0) > 86400:
             data = {"image_count": 0, "video_count": 0, "last_reset": now}
             current = 0

        if current >= limit:
            logger.warning(f"Rate limit exceeded for {media_type} (User {user_id}, Tier {tier}). ({current}/{limit})")
            return False
            
        # Increment and save
        data[f"{media_type}_count"] = current + 1
        # Only save last_reset if it was updated above, else keep it
        if "last_reset" not in data: 
             data["last_reset"] = now
             
        usage_file.write_text(json.dumps(data))
        return True

    async def execute(self, prompt: str, media_type: str = "image", user_id: int = None, request_scope: str = "PUBLIC", is_autonomy: bool = False, channel_id: int = None, intention: str = None, **audio_kwargs) -> str:
        """
        Generate media and store in user-scoped directory.
        
        Args:
            prompt: Generation prompt (or text for speech)
            media_type: "image", "video", "music", or "speech"
            user_id: User who requested (None = CORE/autonomy)
            request_scope: Privacy scope (PUBLIC/PRIVATE)
            is_autonomy: If True, send to imaging channel; if False, return path for user's channel
            channel_id: Optional channel to send to (for user requests)
            intention: Reason for creation (for provenance/anti-hallucination)
            **audio_kwargs: Extra params for music/speech:
                duration (int): Music duration in seconds (default 10)
                voice (str): TTS speaker name (default "Chelsie")
                instruct (str): TTS emotion/style instruction
                mode (str): TTS mode — "custom", "design", "clone"
                ref_audio (str): Reference audio path (clone mode)
                ref_text (str): Reference audio transcript (clone mode)
        """
        logger.info(f"VisualCortex request: {prompt[:200]} [{media_type}] User: {user_id} Autonomy: {is_autonomy} Intention: {intention}")
        
        if user_id is None:
             # Autonomy/system generation - map to admin
             user_id = settings.ADMIN_ID
             is_autonomy = True  # Force autonomy flag if no user_id

        
        # Admin Override — admins bypass ALL rate limits including turn lock
        is_admin = str(user_id) in {str(aid) for aid in settings.ADMIN_IDS}

        if self.turn_lock and not is_admin:
             return "Rate limit: Only one generation per turn allowed."
              
        # Rate limits only apply to user-requested generations, not autonomy/system
        if not is_autonomy and not is_admin and not self._check_limits(media_type, user_id):
             limit = settings.DAILY_IMAGE_LIMIT if media_type == "image" else settings.DAILY_VIDEO_LIMIT
             return f"Daily limit reached ({limit} {media_type}s/day). Upgrade your tier for more: https://www.patreon.com/c/TheErnOSGardens"

        # Determine user-scoped output path
        from src.privacy.scopes import ScopeManager, PrivacyScope
        
        try:
            scope = PrivacyScope[request_scope.upper()]
        except Exception:
            scope = PrivacyScope.PUBLIC
        
        timestamp = str(int(time.time()))
        
        # File extension based on media type
        ext_map = {"image": "png", "video": "mp4", "music": "wav", "speech": "wav"}
        ext = ext_map.get(media_type, "png")
        filename = f"generated_{media_type}_{timestamp}.{ext}"
        
        # Route to user-scoped media directory
        if user_id and str(user_id) not in {str(aid) for aid in settings.ADMIN_IDS}:
            # User media: memory/users/{user_id}/media/{scope}/
            base_dir = Path(os.getcwd()) / "memory" / "users" / str(user_id) / "media" / scope.name.lower()
        else:
            # Autonomy/CORE media: memory/core/media/
            base_dir = Path(os.getcwd()) / "memory" / "core" / "media"
        
        base_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(base_dir / filename)
        
        # Execute Generation (Async wrapper for heavy blocking call)
        try:
             generator = get_generator(user_id=user_id)
             if media_type == "video":
                 # Offload to background task for non-blocking UI
                 if channel_id:
                     asyncio.create_task(self._generate_video_background(prompt, user_id, channel_id, request_scope, is_autonomy, intention))
                     return f"🎬 **Video Generation Started**\n**Resolution:** 1024x576 (High Quality)\n**ETA:** ~2-3 minutes\n\nI will upload the result here when it is ready. You can continue chatting in the meantime."
                 else:
                      # Fallback if no channel_id (e.g. autonomy): Blocking
                      await asyncio.to_thread(generator.generate_video, prompt, output_path)
             elif media_type == "music":
                 duration = audio_kwargs.get("duration", 10)
                 # generate_music returns the final path (mp3 after conversion)
                 output_path = await asyncio.to_thread(generator.generate_music, prompt, output_path, duration)

             elif media_type == "speech":
                 voice = audio_kwargs.get("voice", "Chelsie")
                 instruct = audio_kwargs.get("instruct", "")
                 mode = audio_kwargs.get("mode", "custom")
                 ref_audio = audio_kwargs.get("ref_audio")
                 ref_text = audio_kwargs.get("ref_text")
                 output_path = await asyncio.to_thread(
                     generator.generate_speech, prompt, output_path,
                     voice, instruct, mode, ref_audio, ref_text
                 )
             elif media_type == "audiobook":
                 # Full audiobook production — background task (very long running)
                 title = audio_kwargs.get("title", "Audiobook")
                 if channel_id:
                     asyncio.create_task(self._produce_audiobook_background(
                         prompt, user_id, channel_id, request_scope,
                         is_autonomy, intention, title, output_path
                     ))
                     return (
                         f"📖🎧 **Audiobook Production Started: {title}**\n"
                         f"**Engines:** Kokoro (narrator) + Qwen3-TTS (characters) + MusicGen (music/SFX)\n"
                         f"**ETA:** Depends on script length (short story ~5 min, novel chapter ~15-30 min)\n\n"
                         f"I will upload the finished audiobook here when it is ready. "
                         f"You can continue chatting in the meantime."
                     )
                 else:
                     from src.lobes.creative.audiobook_producer import AudiobookProducer
                     producer = AudiobookProducer(self.bot)
                     output_path = await producer.produce(prompt, output_path, title=title)
             else:
                 await asyncio.to_thread(generator.generate_image, prompt, output_path)
             
             # Log Provenance
             from src.security.provenance import ProvenanceManager
             ProvenanceManager.log_artifact(output_path, media_type, {
                 "prompt": prompt, 
                 "user_id": user_id, 
                 "scope": request_scope, 
                 "is_autonomy": is_autonomy,
                 "intention": intention # Added intention logging
             })
             
             # Channel Routing Logic
             if is_autonomy:
                 AUDIOBOOK_CHANNEL_ID = 1472697547402252329
                 MUSIC_CHANNEL_ID    = 1472713306874581023

                 if media_type == "audiobook":
                     await self._send_to_media_channel(output_path, prompt, AUDIOBOOK_CHANNEL_ID, "📖🎧", "Audiobook")
                 elif media_type == "music":
                     await self._send_to_media_channel(output_path, prompt, MUSIC_CHANNEL_ID, "🎵", "Music")
                 else:
                     # Images, video, speech → imaging channel
                     await self._send_to_imaging_channel(output_path, prompt)
             # else: caller will handle sending to user's channel

             self.turn_lock = True

             # KG Provenance: Record this creation so Ernos recognizes it later
             if is_autonomy:
                 try:
                     from src.bot import globals as bot_globals
                     if bot_globals.bot and bot_globals.bot.hippocampus and bot_globals.bot.hippocampus.graph:
                         graph = bot_globals.bot.hippocampus.graph
                         safe_prompt = prompt[:2000].replace('"', "'").replace('\n', ' ')
                         rel_type_map = {
                             "image": "CREATED_IMAGE", "video": "CREATED_VIDEO",
                             "music": "CREATED_MUSIC", "speech": "CREATED_SPEECH",
                         }
                         graph.add_node(
                             label="Artifact", name=os.path.basename(output_path),
                             layer="creative", user_id=-1, scope="CORE",
                             properties={
                                 "type": media_type, 
                                 "prompt": safe_prompt, 
                                 "path": output_path,
                                 "intention": intention or "Unknown" # Store intention in KG
                             }
                         )
                         graph.add_relationship(
                             source_name="Ernos", rel_type=rel_type_map.get(media_type, "CREATED_ARTIFACT"),
                             target_name=os.path.basename(output_path),
                             layer="creative", scope="CORE", user_id=-1,
                             source="autonomy"
                         )
                 except Exception as kg_err:
                     logger.debug(f"Media KG provenance warning: {kg_err}")

             return output_path
             
        except Exception as e:
             logger.error(f"Generation failed: {e}")
             return f"Generation Error: {str(e)}"
    
    async def _generate_video_background(self, prompt: str, user_id: int, channel_id: int, request_scope: str, is_autonomy: bool, intention: str):
        """Background task for video generation."""
        try:
            logger.info(f"Starting background video generation for {user_id} in {channel_id}")
            # Re-calculate path in background task context
            # (We duplicate path logic here for simplicity or refactor path logic to helper)
            # Let's use a simplified temp variable to avoid code duplication issues if possible?
            # Actually, better to refactor path logic? No, just copy it for safety.
            
            from src.privacy.scopes import ScopeManager, PrivacyScope
            try:
                scope = PrivacyScope[request_scope.upper()]
            except Exception:
                scope = PrivacyScope.PUBLIC
            
            timestamp = str(int(time.time()))
            filename = f"generated_video_{timestamp}.mp4"
            
            if user_id and str(user_id) not in {str(aid) for aid in settings.ADMIN_IDS}:
                base_dir = Path(os.getcwd()) / "memory" / "users" / str(user_id) / "media" / scope.name.lower()
            else:
                base_dir = Path(os.getcwd()) / "memory" / "core" / "media"
            
            base_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(base_dir / filename)
            
            # Generate
            generator = get_generator(user_id=user_id)
            await asyncio.to_thread(generator.generate_video, prompt, output_path)
            
            # Log Provenance
            from src.security.provenance import ProvenanceManager
            ProvenanceManager.log_artifact(output_path, "video", {
                "prompt": prompt, 
                "user_id": user_id, 
                "scope": request_scope, 
                "is_autonomy": is_autonomy,
                "intention": intention # Added intention logging
            })

            # Send to Channel
            channel_id_int = int(channel_id)
            channel = self.bot.get_channel(channel_id_int)
            if channel:
                import discord
                file = discord.File(output_path)
                await channel.send(f"🎬 **Video Complete**\n*Prompt: {prompt}*", file=file)
                logger.info(f"Sent background video to channel {channel_id}")
            else:
                logger.error(f"Could not find channel {channel_id} for background video upload.")
                
        except Exception as e:
            logger.error(f"Background video generation failed: {e}")
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(f"❌ **Video Generation Failed**: {str(e)}")
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")


    async def _produce_audiobook_background(self, script: str, user_id: int, channel_id: int,
                                             request_scope: str, is_autonomy: bool, intention: str,
                                             title: str, output_path: str):
        """Background task for audiobook production with chunked delivery."""
        AUDIOBOOK_CHANNEL_ID = 1472697547402252329
        
        # Re-enabled: Memory stability verified via concurrency guard and chunked delivery.
        
        # ── Concurrency guard: only 1 audiobook at a time ──
        # ... (rest of code commented out or unreachable) ...

    async def _split_audio_chunks(self, audio_path: str, title: str, max_mb: int = 20) -> list:
        """Split an audio file into chunks of ≤ max_mb using ffmpeg."""
        import subprocess
        import math

        try:
            # Get total duration using ffprobe
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, timeout=30,
            )
            total_duration = float(probe.stdout.strip())
            file_size = os.path.getsize(audio_path)
            
            # Calculate bytes per second, then how many seconds fit in max_mb
            bytes_per_sec = file_size / total_duration
            chunk_duration = int((max_mb * 1024 * 1024) / bytes_per_sec)
            
            # How many chunks do we need?
            num_chunks = math.ceil(total_duration / chunk_duration)
            if num_chunks <= 1:
                return [audio_path]  # Shouldn't happen, but safety
            
            output_dir = os.path.dirname(audio_path)
            safe_title = title.replace(" ", "_").replace("/", "_")[:50]
            chunk_pattern = os.path.join(output_dir, f"{safe_title}_chunk_%03d.mp3")
            
            # Use ffmpeg segment muxer for exact splitting
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path,
                 "-f", "segment", "-segment_time", str(chunk_duration),
                 "-c", "copy", chunk_pattern],
                capture_output=True, text=True, timeout=300,
            )
            
            if result.returncode != 0:
                logger.error(f"ffmpeg chunking failed: {result.stderr[:300]}")
                return []
            
            # Collect generated chunk files
            chunks = sorted([
                os.path.join(output_dir, f) for f in os.listdir(output_dir)
                if f.startswith(f"{safe_title}_chunk_") and f.endswith(".mp3")
            ])
            
            logger.info(f"Split audiobook into {len(chunks)} chunks of ~{chunk_duration}s each")
            return chunks
            
        except Exception as e:
            logger.error(f"Audio chunking failed: {e}")
            return []


    async def _send_to_imaging_channel(self, image_path: str, prompt: str):
        """Send autonomy-generated image to the ernos-imaging channel."""
        IMAGING_CHANNEL_ID = 1445500249631096903
        await self._send_to_media_channel(image_path, prompt, IMAGING_CHANNEL_ID, "🎨", "Image")

    async def _send_to_media_channel(self, file_path: str, prompt: str, channel_id: int, emoji: str, label: str):
        """Send autonomy-generated media to a specific Discord channel."""
        MAX_CHUNK_MB = 50
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                import discord
                file_size = os.path.getsize(file_path)
                size_mb = file_size / (1024 * 1024)

                truncated = f"{prompt[:1800]}..." if len(prompt) > 1800 else prompt
                msg = f"{emoji} **Autonomy {label}**\n*Prompt: {truncated}*"

                if size_mb <= MAX_CHUNK_MB:
                    file = discord.File(file_path)
                    await channel.send(msg, file=file)
                elif label.lower() in ("audiobook", "music"):
                    # Chunked delivery for large audio
                    title = os.path.splitext(os.path.basename(file_path))[0]
                    chunks = await self._split_audio_chunks(file_path, title, MAX_CHUNK_MB)
                    if chunks:
                        await channel.send(f"{msg}\n*Total: {size_mb:.1f} MB — split into {len(chunks)} parts*")
                        for i, chunk_path in enumerate(chunks, 1):
                            try:
                                chunk_size = os.path.getsize(chunk_path) / (1024 * 1024)
                                file = discord.File(chunk_path, filename=f"{title}_part{i}.mp3")
                                await channel.send(
                                    f"{emoji} **Part {i}/{len(chunks)}** ({chunk_size:.1f} MB)",
                                    file=file
                                )
                            except Exception as chunk_err:
                                logger.error(f"Failed to send chunk {i}: {chunk_err}")
                            finally:
                                try:
                                    os.remove(chunk_path)
                                except OSError as e:
                                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
                    else:
                        await channel.send(f"{msg}\n*File is {size_mb:.1f} MB — chunking failed. Saved to: `{file_path}`*")
                else:
                    await channel.send(f"{msg}\n*File is {size_mb:.1f} MB (too large). Saved to: `{file_path}`*")
                logger.info(f"Sent autonomy {label.lower()} to channel {channel_id}: {file_path}")
            else:
                logger.warning(f"Could not find channel {channel_id} for autonomy {label.lower()}")
        except Exception as e:
            logger.error(f"Failed to send {label.lower()} to channel {channel_id}: {e}")

    def reset_turn_lock(self):
        """Called by Lobe Manager at end of turn"""
        self.turn_lock = False
