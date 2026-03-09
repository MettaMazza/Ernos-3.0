"""
The Cerebrum (Cognitive Manager).
Orchestrates the high-level cognitive Lobes.
"""
import logging
from typing import Dict, Optional
from .base import BaseLobe
from .strategy import StrategyLobe
from .memory import MemoryLobe
from .interaction import InteractionLobe
from .creative import CreativeLobe
from .superego import SuperegoLobe

logger = logging.getLogger("Cerebrum")

class Cerebrum:
    def __init__(self, bot):
        self.bot = bot
        self.lobes: Dict[str, BaseLobe] = {}
        
    async def setup(self):
        """Initialize all Cognitive Lobes."""
        logger.info("Initializing Cerebrum...")
        
        self.register_lobe(StrategyLobe)
        self.register_lobe(MemoryLobe)
        self.register_lobe(InteractionLobe)
        self.register_lobe(CreativeLobe)
        self.register_lobe(SuperegoLobe)
        
        # Start Autonomy Loop if Autonomy exists
        creative = self.get_lobe("CreativeLobe")
        if creative:
            autonomy = creative.get_ability("AutonomyAbility")
            if autonomy:
                # We start it as a background task
                import asyncio
                asyncio.create_task(autonomy.execute())
        
        # Start Town Hall Daemon (v3.5+ Proactive Messaging)
        try:
            import asyncio
            from pathlib import Path
            from src.daemons.town_hall import TownHallDaemon
            
            self.bot.town_hall = TownHallDaemon(self.bot)
            
            # Auto-discover all personas across all users
            users_dir = Path("memory/users")
            if users_dir.exists():
                seen = set()
                for user_dir in users_dir.iterdir():
                    if not user_dir.is_dir():
                        continue
                    personas_dir = user_dir / "personas"
                    if personas_dir.exists():
                        for persona_dir in personas_dir.iterdir():
                            if persona_dir.is_dir() and persona_dir.name not in seen:
                                self.bot.town_hall.register_persona(
                                    persona_dir.name, owner_id=user_dir.name
                                )
                                seen.add(persona_dir.name)
            
            # Always register Ernos as a participant
            if "ernos" not in {p.name for p in self.bot.town_hall._personas.values()}:
                self.bot.town_hall.register_persona("ernos")
            
            logger.info(f"TownHall daemon registered {len(self.bot.town_hall._personas)} personas")
        except Exception as e:
            logger.warning(f"TownHall startup failed (non-fatal): {e}")
            self.bot.town_hall = None

    def register_lobe(self, lobe_cls):
        """Instantiate and register a Lobe."""
        try:
            lobe = lobe_cls(self)
            name = lobe.__class__.__name__
            self.lobes[name] = lobe
            logger.info(f"Lobe Registered: {name}")
        except Exception as e:
            logger.critical(f"Failed to register Lobe {lobe_cls}: {e}")

    def get_lobe(self, name: str) -> Optional[BaseLobe]:
        return self.lobes.get(name)
    
    def get_lobe_by_name(self, name: str) -> Optional[BaseLobe]:
        """Alias for get_lobe - prevents AttributeError from legacy/external calls."""
        return self.get_lobe(name)

    async def shutdown(self):
        """Shutdown all lobes."""
        logger.info("Cerebrum shutting down...")
        for name, lobe in self.lobes.items():
            await lobe.shutdown()
