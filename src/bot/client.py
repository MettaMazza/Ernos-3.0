import discord
from discord.ext import commands, tasks
import logging
import time
from config import settings
from src.engines import OllamaEngine, VectorEnhancedOllamaEngine, SteeringEngine, EngineManager
from src.memory.hippocampus import Hippocampus
from src.lobes.manager import Cerebrum
from src.silo_manager import SiloManager
from src.voice.manager import VoiceManager
from src.channels.manager import ChannelManager
from src.channels.discord_adapter import DiscordChannelAdapter
from src.skills.registry import SkillRegistry
from src.skills.sandbox import SkillSandbox
from src.concurrency.lane import LaneQueue

logger = logging.getLogger("ErnosBot")

class ErnosBot(commands.Bot):
    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # Required for on_member_join welcome messages
        
        super().__init__(
            command_prefix=["!", "/"],
            intents=intents,
            help_command=None
        )
        
        self.last_interaction = time.time()
        self.engine_manager = EngineManager()
        # Initialize Memory System
        try:
            self.hippocampus = Hippocampus()
        except Exception as e:
            logger.critical(f"FATAL: Hippocampus Failed to Initialize: {e}")
            raise e
        
        # Initialize KG Consolidator Daemon (auto-extracts KG after every 5 turns)
        try:
            from src.daemons.kg_consolidator import KGConsolidator
            self.kg_consolidator = KGConsolidator(self)
            self.hippocampus.set_kg_consolidator(self.kg_consolidator)
            logger.info("KG Consolidator Daemon initialized")
        except Exception as e:
            logger.warning(f"KG Consolidator failed to initialize (non-fatal): {e}")
            self.kg_consolidator = None
            
        # Initialize Cerebrum (Cognitive Architecture)
        self.cerebrum = Cerebrum(self)
        
        # Initialize Silo Manager (Privacy)
        self.silo_manager = SiloManager(self)

        # Initialize Voice System
        self.voice_manager = VoiceManager(self)

        # Initialize Channel Adapter Framework (Synapse Bridge v3.1)
        self.channel_manager = ChannelManager()

        # Initialize Skills Framework (Synapse Bridge v3.1)
        self.skill_registry = SkillRegistry()
        self.skill_sandbox = SkillSandbox()
        
        # Initialize Unified CognitionEngine (shared by all subsystems)
        try:
            from src.engines.cognition import CognitionEngine
            self.cognition = CognitionEngine(self)
            logger.info("Unified CognitionEngine initialized")
        except Exception as e:
            logger.error(f"CognitionEngine failed to initialize: {e}")
            self.cognition = None
        
        # Superego State
        self.grounding_pulse = None
        
        # Performance Tracking
        # Performance Tracking
        self.start_time = time.time()
        
        from collections import defaultdict
        self.message_queues = defaultdict(list)
        
        # Concurrency Tracking
        self.processing_users = set()

        # Lane Queue System (Synapse Bridge v3.1)
        self.lane_queue = LaneQueue()

    @property
    def is_processing(self):
        """Returns True if ANY user is currently being processed."""
        return len(self.processing_users) > 0

    def add_processing_user(self, user_id, channel_id=None):
        self.processing_users.add((user_id, channel_id))

    def remove_processing_user(self, user_id, channel_id=None):
        self.processing_users.discard((user_id, channel_id))

    @tasks.loop(hours=24)
    async def maintenance_loop(self):
        """Runs daily maintenance cycles (Sentinel, Cleanup)."""
        logger.info("Maintenance Loop Triggered.")
        try:
            # 1. Sentinel Daily Cycle
            sentinel = self.cerebrum.get_lobe("StrategyLobe").get_ability("SentinelAbility")
            if sentinel:
                result = await sentinel.run_daily_cycle()
                logger.info(f"Sentinel Cycle: {result}")
                
            # 2. Add other daily tasks here (e.g. Memory Pruning)
            
        except Exception as e:
            logger.error(f"Maintenance Loop Failed: {e}")

    @maintenance_loop.before_loop
    async def before_maintenance(self):
        # Fix for tests: don't wait if loop is cancelled/stopping
        if self.is_closed():
             return
        if self.maintenance_loop.is_running():
            try:
                await self.wait_until_ready()
            except RuntimeError:
                # Client might not be initialized in tests
                pass

    async def send_to_mind(self, content: str):
        """Sends chunked thought process to the dedicated Mind Channel."""
        if not content: return
        
        try:
            channel = self.get_channel(settings.MIND_CHANNEL_ID)
            if not channel:
                # Try fetching if not in cache
                try:
                    channel = await self.fetch_channel(settings.MIND_CHANNEL_ID)
                except Exception:
                    logger.error(f"Mind Channel {settings.MIND_CHANNEL_ID} not found.")
                    return

            # Chunking (2000 char limit)
            # We use 1900 to be safe with code blocks if needed, though raw text is fine
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            
            for chunk in chunks:
                await channel.send(chunk)
                
        except Exception as e:
            logger.error(f"Failed to send to Mind Channel: {e}")

    async def send_to_dev_channel(self, content: str):
        """Sends work mode activity to the dedicated Dev Channel for full transparency."""
        if not content: return
        
        try:
            channel = self.get_channel(settings.DEV_CHANNEL_ID)
            if not channel:
                try:
                    channel = await self.fetch_channel(settings.DEV_CHANNEL_ID)
                except Exception:
                    logger.error(f"Dev Channel {settings.DEV_CHANNEL_ID} not found.")
                    return

            # Chunking (2000 char Discord limit, use 1900 for safety)
            chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
            
            for chunk in chunks:
                await channel.send(chunk)
                
        except Exception as e:
            logger.error(f"Failed to send to Dev Channel: {e}")

    async def setup_hook(self):
        # 1. /cloud -> RAG Enabled (Ollama: Gemini)
        cloud_engine = VectorEnhancedOllamaEngine(
            model_name=settings.OLLAMA_CLOUD_MODEL, 
            base_url=settings.OLLAMA_BASE_URL,
            embedding_model=settings.OLLAMA_EMBED_MODEL
        )
        self.engine_manager.register_engine("cloud", cloud_engine)

        # 2. /local -> RAG Enabled (Ollama: Qwen)
        local_engine = VectorEnhancedOllamaEngine(
            model_name=settings.OLLAMA_LOCAL_MODEL, 
            base_url=settings.OLLAMA_BASE_URL,
            embedding_model=settings.OLLAMA_EMBED_MODEL
        )
        self.engine_manager.register_engine("local", local_engine)

        # 3. /LocalSteer -> Steering + RAG (Llama.cpp)
        # NOW accepts embedding model for RAG bridge
        steer_engine = SteeringEngine(
            model_path=settings.STEERING_MODEL_PATH,
            control_vector_path=settings.CONTROL_VECTOR_PATH,
            embedding_model=settings.OLLAMA_EMBED_MODEL
        )
        self.engine_manager.register_engine("LocalSteer", steer_engine)

        # Default to Local
        self.engine_manager.set_active_engine("local")

        # Register Channel Adapters (Synapse Bridge v3.1)
        self.channel_manager.register_adapter(DiscordChannelAdapter(self))

        # Load Cogs
        await self.load_extension("src.bot.cogs.admin")
        await self.load_extension("src.bot.cogs.proxy_cog")
        await self.load_extension("src.bot.cogs.chat")
        await self.load_extension("src.bot.cogs.silo_commands")
        await self.load_extension("src.bot.cogs.mrn_commands")
        await self.load_extension("src.bot.cogs.persona_commands")
        await self.load_extension("src.bot.cogs.inbox_commands")
        await self.load_extension("src.bot.cogs.relationship_commands")
        await self.load_extension("src.bot.cogs.welcome")
        await self.load_extension("src.bot.cogs.monetization")
        await self.load_extension("src.bot.cogs.support")
        await self.load_extension("src.bot.cogs.stop_command")
        
        # Setup Cerebrum
        await self.cerebrum.setup()

        # SYNC COMMANDS (Temporary auto-sync to register /sync_tier)
        logger.info("Syncing application commands...")
        await self.tree.sync()
        logger.info("Application commands synced.")

        # Load Skills (Synapse Bridge v3.1)
        from pathlib import Path
        skills_dir = Path("memory/core/skills")
        loaded = self.skill_registry.load_skills(skills_dir)
        logger.info(f"Loaded {loaded} skill(s) from {skills_dir}")
        
        
        lite = getattr(settings, 'AUTONOMY_LITE_MODE', False)
        mode_label = "Local" if self.engine_manager._active_key == "local" else "Cloud"
        logger.info(f"Bot setup complete. Active: {mode_label} | Autonomy Lite: {'ON' if lite else 'OFF'}")
        
        # Start Lane Queue (Synapse Bridge v3.1)
        await self.lane_queue.start()

        # Start Maintenance
        self.maintenance_loop.start()

        # Start Schedulers (v3.2 Sleep Cycle)
        try:
            from src.scheduler import setup_backup_scheduler
            await setup_backup_scheduler(self)
            
            from src.daemons.dream_consolidation import setup_dream_scheduler
            self.dream_daemon = setup_dream_scheduler(self)
            
            from src.scheduler import get_scheduler
            get_scheduler().start()
            logger.info("All schedulers started (backup + dream consolidation)")
        except Exception as e:
            logger.warning(f"Scheduler setup failed (non-fatal): {e}")
            self.dream_daemon = None
            
        # Initialize TownHall Daemon (Continuous Persona Chat)
        try:
            # Seed system personas into public registry
            from src.memory.public_registry import PublicPersonaRegistry
            admin_personas = Path("memory/users/1299810741984956449/personas")
            if admin_personas.exists():
                PublicPersonaRegistry.seed_system_personas(admin_personas)
                logger.info("Public persona registry seeded")
            
            from src.daemons.town_hall import TownHallDaemon
            self.town_hall = TownHallDaemon(self)
            
            # Register ALL public personas with Town Hall (system + user-created)
            self.town_hall.register_persona("ernos")  # Always present (core identity)
            for entry in PublicPersonaRegistry.list_all():
                name = entry["name"]
                if name != "ernos":  # Already registered above
                    self.town_hall.register_persona(name, owner_id=entry.get("creator_id"))
            
            # Start TownHall
            self.loop.create_task(self.town_hall.start())
            self.loop.create_task(self._persona_idle_checker())
            logger.info("TownHall Daemon initialized and started")
        except Exception as e:
            logger.warning(f"TownHall Daemon failed to start: {e}")
            self.town_hall = None

        # Initialize Agency Daemon (Homeostatic Drive)
        try:
            from src.daemons.agency import AgencyDaemon
            self.agency = AgencyDaemon(self)
            self.loop.create_task(self.agency.start())
            logger.info("Agency Daemon initialized and started")
        except Exception as e:
            logger.warning(f"Agency Daemon failed to start: {e}")
            logger.warning(f"Agency Daemon failed to start: {e}")
            self.agency = None

        # Initialize Weekly Quota Scheduler (Self-Development Cadence)
        try:
            from src.tools.review_pipeline import daily_quota_check, friday_review_summary
            from src.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler.add_daily_task("daily_quota_check", 8, 0, daily_quota_check)
            scheduler.add_daily_task("friday_review", 9, 0,
                                     lambda: friday_review_summary(self))
            logger.info("Weekly quota scheduler initialized (08:00 daily check, 09:00 Friday review)")
        except Exception as e:
            logger.warning(f"Weekly quota scheduler failed to start: {e}")

    async def _persona_idle_checker(self):
        """Background task: return idle personas to Town Hall after 5 minutes."""
        import asyncio
        from src.memory.persona_session import PersonaSessionTracker
        
        IDLE_THRESHOLD = 300  # 5 minutes
        CHECK_INTERVAL = 60  # Check every minute
        
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                if self.town_hall:
                    idle_threads = PersonaSessionTracker.get_idle_threads(IDLE_THRESHOLD)
                    for thread_id, persona_name in idle_threads:
                        if persona_name.lower() not in self.town_hall._engaged:
                            continue  # Already in Town Hall, skip
                        self.town_hall.mark_available(persona_name)
                        logger.info(f"Idle check: '{persona_name}' returned to Town Hall (thread {thread_id} idle >5min)")
            except Exception as e:
                logger.warning(f"Persona idle checker error: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        
        # Sync slash commands with Discord
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
        
        # Auto-discover persona threads in ernos-chat
        try:
            from config import settings
            from src.memory.persona_session import PersonaSessionTracker
            from src.memory.public_registry import PublicPersonaRegistry
            
            channel = self.get_channel(settings.TARGET_CHANNEL_ID)
            if channel:
                # Fetch all active threads (including archived)
                threads = channel.threads  # cached active threads
                
                discovered = 0
                for thread in threads:
                    if thread.archived:
                        continue
                    
                    # Already bound? Skip
                    if PersonaSessionTracker.get_thread_persona(str(thread.id)):
                        continue
                    
                    # Parse thread name: "💬 PersonaName — UserName"
                    name = thread.name
                    if name.startswith("💬 ") and " — " in name:
                        persona_part = name[2:].split(" — ")[0].strip().lower()
                        # Sanitize to match registry format
                        clean = PersonaSessionTracker._sanitize_name(persona_part)
                        
                        if PublicPersonaRegistry.get(clean):
                            PersonaSessionTracker.set_thread_persona(str(thread.id), clean)
                            discovered += 1
                            logger.info(f"Auto-discovered thread {thread.id} → persona '{clean}'")
                
                if discovered:
                    logger.info(f"Auto-discovered {discovered} persona thread(s)")
        except Exception as e:
            logger.warning(f"Thread auto-discovery failed: {e}")

    async def on_thread_member_remove(self, member, thread):
        """Monitor Silo threads for emptiness."""
        if thread.id in self.silo_manager.active_silos:
            await self.silo_manager.check_empty_silo(thread)

    async def close(self):
        logger.info("ErnosBot shutting down...")
        
        # Record temporal shutdown for downtime tracking
        try:
            from src.memory.temporal import TemporalTracker
            temporal = TemporalTracker()
            temporal.record_shutdown()
        except Exception as e:
            logger.warning(f"Temporal shutdown recording failed: {e}")
        
        if hasattr(self, 'town_hall') and self.town_hall:
            self.town_hall.stop()
        
        if hasattr(self, 'agency') and self.agency:
            await self.agency.stop()
        
        await self.lane_queue.stop()
        await self.cerebrum.shutdown()
        self.hippocampus.shutdown()
        await super().close()
