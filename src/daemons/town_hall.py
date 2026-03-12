"""
Town Hall Daemon — Continuous inter-persona conversation.

A lived community where AI personas converse with each other
in #persona-chat (read-only for humans). Each persona is a
fully realized agent with its own memory silo, system context,
and access to tools — but scoped to PUBLIC information only.

Runs continuously like the autonomy loop. Interrupted when
a persona is actively engaged with a user in DMs.

Split modules:
  - persona_agent.py          → PersonaAgent class
  - town_hall_generation.py   → Topic & response generation
"""
import asyncio
import json
import logging
import discord  # type: ignore
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

from src.daemons.persona_agent import PersonaAgent  # noqa: F401 (re-export)
from src.daemons.town_hall_generation import (
    generate_topic,
    generate_persona_response,
    _generate_fallback,
)
from src.core.data_paths import data_dir

logger = logging.getLogger("Daemon.TownHall")


class TownHallDaemon:
    """
    Continuous inter-persona conversation daemon.
    
    Runs in #persona-chat, where personas take turns talking.
    Each persona is a fully realized agent with own memory.
    Interrupted when a persona is engaged with a user.
    """
    
    HISTORY_FILE = data_dir() / "system/town_hall/history.jsonl"
    
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self._personas: Dict[str, PersonaAgent] = {}
        self._engaged: Set[str] = set()  # Personas currently talking to users
        self._last_speaker: Optional[str] = None
        self._conversation_turns = 0
        self._topic: Optional[str] = None
        self._suggested_topics: deque = deque(maxlen=50)  # User-suggested topics (FIFO)
        
        self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not self.HISTORY_FILE.exists():
            self.HISTORY_FILE.touch()
    
    def add_suggestion(self, user_id: str, topics: List[str]) -> int:
        """Add user-suggested topics to the FIFO queue. Returns count added."""
        added: int = 0
        for topic in topics:
            clean = topic.strip()
            if clean and len(clean) > 3:
                self._suggested_topics.append({
                    "topic": clean[:200],
                    "suggested_by": user_id,
                    "timestamp": datetime.now().isoformat()
                })
                added += 1
        logger.info(f"TownHall: {added} topic(s) suggested by user {user_id}")
        return added
    
    def get_suggestion(self) -> Optional[str]:
        """Pop and return the next suggested topic, or None."""
        if self._suggested_topics:
            entry = self._suggested_topics.popleft()
            return entry["topic"]
        return None
    
    def register_persona(self, name: str, owner_id: Optional[str] = None) -> PersonaAgent:
        """Register a persona to participate in town hall."""
        agent = PersonaAgent(name, owner_id)
        self._personas[name.lower()] = agent
        logger.info(f"TownHall: Registered persona '{name}'")
        return agent
    
    def mark_engaged(self, persona_name: str):
        """Mark persona as engaged with a user (pull from town hall)."""
        self._engaged.add(persona_name.lower())
        logger.info(f"TownHall: '{persona_name}' engaged with user, pausing")
    
    def mark_available(self, persona_name: str):
        """Mark persona as available (rejoins town hall)."""
        self._engaged.discard(persona_name.lower())
        logger.info(f"TownHall: '{persona_name}' available, rejoining")
    
    def _get_available_personas(self) -> List[PersonaAgent]:
        """Get personas not currently engaged with users."""
        return [
            p for name, p in self._personas.items()
            if name not in self._engaged
        ]
    
    def _pick_next_speaker(self) -> Optional[PersonaAgent]:
        """Pick the next persona to speak (avoid repeating last speaker)."""
        import random
        available = self._get_available_personas()
        if not available:
            return None
        
        candidates = [p for p in available if p.name != self._last_speaker]
        if not candidates:
            candidates = available
        
        return random.choice(candidates)
    
    async def _read_public_chat(self, limit: int = 10) -> str:
        """Read recent messages from the main chat channel for gossip."""
        try:
            from config import settings  # type: ignore
            channel_id = getattr(settings, 'TARGET_CHANNEL_ID', 0)
            if not channel_id:
                return ""
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return ""
            
            messages = []
            async for msg in channel.history(limit=limit):
                if not msg.author.bot and msg.content:
                    author = msg.author.display_name
                    content = msg.content[:150]
                    messages.append(f"{author}: {content}")
            
            return "\n".join(reversed(messages))
        except Exception as e:
            logger.warning(f"TownHall: Failed to read public chat: {e}")
            return ""
    
    # ─── Proxy methods (backward-compat for tests & subclasses) ────

    async def _generate_topic(self):
        """Proxy to standalone generate_topic."""
        return await generate_topic(
            self.bot, self._topic,
            self.get_recent_history(limit=10),
            self._pick_next_speaker,
            self.get_suggestion,
            self._read_public_chat,
        )

    async def _generate_persona_response(self, speaker):
        """Proxy to standalone generate_persona_response."""
        return await generate_persona_response(
            self.bot, speaker, self._topic,
            self._get_available_personas(),
            self.get_recent_history,
        )

    async def _generate_persona_response_fallback(self, speaker):
        """Proxy to standalone _generate_fallback."""
        return await _generate_fallback(self.bot, speaker, self._topic)

    # ─── Main Loop ─────────────────────────────────────────────── 

    async def start(self):
        """Start the continuous town hall loop."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("TownHall: STARTED (Continuous Persona Community)")
        
        try:
            while self.is_running:
                await asyncio.sleep(3600)  # ~1hr between turns
                
                available = self._get_available_personas()
                if len(available) < 2:
                    await asyncio.sleep(60)
                    continue
                
                import random
                topic_threshold = random.randint(10, 15)
                if not self._topic or self._conversation_turns >= topic_threshold:
                    self._topic = await self._generate_topic()
                    self._conversation_turns = 0
                    
                    await self._post_to_channel(
                        "Town Hall",
                        f"*New topic:* {self._topic}",
                        color=0x7289DA
                    )
                
                speaker = self._pick_next_speaker()
                if not speaker:
                    continue
                
                response = await self._generate_persona_response(speaker)
                if not response:
                    continue
                
                await self._post_to_channel(
                    speaker.display_name,
                    response,
                    color=self._persona_color(speaker.name)
                )
                
                for p in self._personas.values():
                    p.record_message(speaker.name, response)
                
                self._record_history(speaker.name, response)
                
                self._last_speaker = speaker.name
                self._conversation_turns += 1
                
                await asyncio.sleep(random.randint(45, 75))
                
        except asyncio.CancelledError:
            self.is_running = False
            logger.info("TownHall: Loop cancelled")
        except Exception as e:
            logger.error(f"TownHall: Fatal error: {e}")
            self.is_running = False
    
    def stop(self):
        """Stop the town hall loop."""
        self.is_running = False
        logger.info("TownHall: Stopped")
    
    async def _post_to_channel(self, speaker_name: str, content: str, color: int = 0x2F3136):
        """Post a message to the persona-chat channel as a rich embed."""
        try:
            from config import settings  # type: ignore
            channel_id = getattr(settings, 'PERSONA_CHAT_CHANNEL_ID', 0)
            if not channel_id:
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    logger.error(f"TownHall: Cannot find persona-chat channel {channel_id}")
                    return
            
            chunks = self._chunk_at_sentences(content, max_len=2000)
            
            for chunk in chunks:
                embed = discord.Embed(
                    description=chunk,
                    color=color,
                    timestamp=datetime.now()
                )
                embed.set_author(name=speaker_name)
                await channel.send(embed=embed)
                if len(chunks) > 1:
                    await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"TownHall: Failed to post: {e}")
    
    @staticmethod
    def _chunk_at_sentences(text: str, max_len: int = 2000) -> list:
        """Split text at sentence boundaries to avoid mid-word truncation."""
        if len(text) <= max_len:
            return [text]
        
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break
            
            cut = max_len
            for sep in ['. ', '? ', '! ', '.\n', '?\n', '!\n']:
                idx = remaining[:max_len].rfind(sep)
                if idx > 0:
                    cut = idx + len(sep)
                    break
            else:
                space_idx = remaining[:max_len].rfind(' ')
                if space_idx > 0:
                    cut = space_idx + 1
            
            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        
        return chunks
    
    def _record_history(self, speaker: str, content: str):
        """Record to global town hall history."""
        entry = {
            "speaker": speaker,
            "content": content[:10000],
            "topic": self._topic,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.HISTORY_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        lines = self.HISTORY_FILE.read_text().strip().split("\n")
        if len(lines) > 500:
            self.HISTORY_FILE.write_text("\n".join(lines[-500:]) + "\n")
    
    @staticmethod
    def _persona_color(name: str) -> int:
        """Deterministic color from persona name."""
        import hashlib
        h = int(hashlib.md5(name.encode()).hexdigest(), 16) % 360
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(h / 360, 0.6, 0.85)
        return int(r * 255) << 16 | int(g * 255) << 8 | int(b * 255)
    
    def get_recent_history(self, limit: int = 20) -> List[Dict]:
        """Get recent town hall history (for persona joining)."""
        if not self.HISTORY_FILE.exists() or self.HISTORY_FILE.stat().st_size == 0:
            return []
        lines = self.HISTORY_FILE.read_text().strip().split("\n")
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
                continue
        return entries
    
    def get_status(self) -> str:
        """Human-readable status."""
        available = len(self._get_available_personas())
        engaged = len(self._engaged)
        total = len(self._personas)
        return (
            f"{'🟢 Running' if self.is_running else '🔴 Stopped'} | "
            f"Personas: {total} ({available} available, {engaged} engaged) | "
            f"Topic: {self._topic or 'None'} | "
            f"Turns: {self._conversation_turns}"
        )
