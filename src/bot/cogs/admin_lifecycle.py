"""
Admin Lifecycle Cog — Cycle resets, salt rotation, channel purge.

Split from admin.py per <300 line modularity standard.
"""
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging
from config import settings

logger = logging.getLogger("AdminCogs")


class AdminLifecycle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.author.id in settings.ADMIN_IDS

    @commands.hybrid_command(name="cyclereset", description="ADMIN: Full cycle reset with user backup DMs")
    async def cycle_reset(self, ctx):
        """
        Perform a full cycle reset:
        1. Export master backup to admin
        2. Export all user contexts and send via DM
        3. Wipe memory directories
        4. Clear Neo4j graph
        
        ADMIN ONLY.
        """
        await ctx.send("⚠️ **CYCLE RESET INITIATED**\nPhase 0a: Creating master backup for admin...")
        
        # Phase 0a: Master Backup to Admin
        try:
            from src.backup.manager import BackupManager
            
            backup_mgr = BackupManager(bot=self.bot)
            master_path = await backup_mgr.export_master_backup()
            
            if master_path and master_path.exists():
                admin_user = await self.bot.fetch_user(settings.ADMIN_ID)
                if admin_user:
                    with open(master_path, "rb") as f:
                        await admin_user.send(
                            "📦 **MASTER BACKUP** - Complete system state before cycle reset.",
                            file=discord.File(f, filename=master_path.name)
                        )
                    await ctx.send(f"✅ Phase 0a Complete: Master backup sent to admin")
                else:
                    await ctx.send("⚠️ Could not find admin user for master backup")
            else:
                await ctx.send("⚠️ Master backup creation failed")
        except Exception as e:
            logger.error(f"Master backup failed: {e}")
            await ctx.send(f"⚠️ Master backup failed: {e}")
        
        await ctx.send("Phase 0b: Backing up user contexts...")
        
        # Phase 0b: User Context Preservation
        try:
            backed_up = await backup_mgr.export_all_users_on_reset()
            await ctx.send(f"✅ Phase 0b Complete: {backed_up} users backed up via DM")
        except Exception as e:
            logger.error(f"Backup phase failed: {e}")
            await ctx.send(f"⚠️ Backup phase failed: {e}")
        
        # Phase 0c: Block new messages + flush in-memory state
        await ctx.send(">>> Phase 0c: Flushing in-memory state...")
        settings.TESTING_MODE = True
        
        try:
            hippo = self.bot.hippocampus
            hippo._shutting_down = True
            
            if hasattr(hippo, 'stream') and hippo.stream:
                hippo.stream.turns.clear()
                hippo.stream.state = type(hippo.stream.state)()
                    
            if hasattr(hippo, 'vector_store') and hippo.vector_store:
                if hasattr(hippo.vector_store, '_data'):
                    hippo.vector_store._data.clear()
                if hasattr(hippo.vector_store, 'reset'):
                    hippo.vector_store.reset()
            
            if hasattr(hippo, 'kg_consolidator') and hippo.kg_consolidator:
                if hasattr(hippo.kg_consolidator, '_buffer'):
                    hippo.kg_consolidator._buffer.clear()
                    
            logger.info("In-memory state flushed: stream, vector, KG buffer")
            await ctx.send("✅ Phase 0c Complete: In-memory state flushed")
        except Exception as e:
            logger.error(f"In-memory flush failed: {e}")
            await ctx.send(f"⚠️ In-memory flush partial: {e}")
        
        # Phase 1: File System Wipe
        await ctx.send(">>> Phase 1: File system wipe...")
        import shutil
        import os
        import tempfile
        
        # PRESERVE public personas
        personas_backup = None
        personas_src = "memory/public/personas"
        if os.path.exists(personas_src):
            personas_backup = os.path.join(tempfile.gettempdir(), "ernos_personas_backup")
            if os.path.exists(personas_backup):
                shutil.rmtree(personas_backup)
            shutil.copytree(personas_src, personas_backup)
            logger.info(f"Preserved {len(os.listdir(personas_src))} public personas before wipe")
        
        # PRESERVE voice_models
        voice_models_backup = None
        voice_models_src = "memory/public/voice_models"
        if os.path.exists(voice_models_src):
            voice_models_backup = os.path.join(tempfile.gettempdir(), "ernos_voice_models_backup")
            if os.path.exists(voice_models_backup):
                shutil.rmtree(voice_models_backup)
            shutil.copytree(voice_models_src, voice_models_backup)
            logger.info(f"Preserved voice_models before wipe")
        
        # PRESERVE shard_salt.secret
        salt_backup = None
        salt_src = "memory/core/shard_salt.secret"
        if os.path.exists(salt_src):
            salt_backup = os.path.join(tempfile.gettempdir(), "ernos_salt_backup")
            shutil.copy2(salt_src, salt_backup)
            logger.info("Preserved shard_salt.secret before wipe")
        
        target_dirs = [
            "memory/users", "memory/core", "memory/public", "memory/system",
            "memory/traces", "memory/chroma", "logs/autonomous", "logs/errors",
        ]
        for d in target_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                    logger.info(f"Deleted Directory: {d}")
                except Exception as e:
                    logger.error(f"Failed to delete {d}: {e}")
        
        target_files = [
            "memory/goals.json", "memory/project_manifest.json",
            "memory/usage.json", "memory/security_profiles.json",
            "memory/lessons.json", "memory/relationships.json",
            "memory/preferences.json", "memory/quarantine.json",
            "logs/stream_of_consciousness.log",
        ]
        for f in target_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                    logger.info(f"Deleted File: {f}")
                except Exception as e:
                    logger.error(f"Failed to delete {f}: {e}")
        
        # Phase 2: Structure Rebuild
        await ctx.send(">>> Phase 2: Structure rebuild...")
        os.makedirs("memory/users", exist_ok=True)
        os.makedirs("memory/core", exist_ok=True)
        os.makedirs("memory/public", exist_ok=True)
        
        try:
            if personas_backup and os.path.exists(personas_backup):
                shutil.copytree(personas_backup, personas_src, dirs_exist_ok=True)
                shutil.rmtree(personas_backup)
                logger.info(f"Restored public personas after wipe")
        except Exception as e:
            logger.error(f"Failed to restore personas: {e}")
        
        try:
            if voice_models_backup and os.path.exists(voice_models_backup):
                shutil.copytree(voice_models_backup, voice_models_src, dirs_exist_ok=True)
                shutil.rmtree(voice_models_backup)
                logger.info("Restored voice_models after wipe")
        except Exception as e:
            logger.error(f"Failed to restore voice_models: {e}")
        
        if salt_backup and os.path.exists(salt_backup):
            os.makedirs(os.path.dirname(salt_src), exist_ok=True)
            shutil.copy2(salt_backup, salt_src)
            os.remove(salt_backup)
            from src.security.provenance import ProvenanceManager
            ProvenanceManager._salt_cache = None
            logger.info("Restored shard_salt.secret after wipe")
        
        # Phase 3: Neo4j Wipe
        await ctx.send(">>> Phase 3: Knowledge graph wipe (preserving CORE foundation)...")
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            with driver.session() as session:
                total = session.run("MATCH (n) RETURN count(n) as c").single()['c']
                core_count = session.run(
                    "MATCH (n {user_id: -1, immutable: true}) RETURN count(n) as c"
                ).single()['c']
                user_count = total - core_count
                
                if user_count > 0:
                    session.run(
                        "MATCH (n) WHERE NOT (n.user_id = -1 AND n.immutable = true) "
                        "DETACH DELETE n"
                    )
                    await ctx.send(
                        f"✅ Cleared {user_count} user nodes from Neo4j\n"
                        f"🏛️ Preserved {core_count} CORE foundation nodes"
                    )
                else:
                    await ctx.send(f"✅ No user data to clear ({core_count} CORE nodes preserved)")
            driver.close()
        except Exception as e:
            logger.error(f"Neo4j wipe failed: {e}")
            await ctx.send(f"⚠️ Neo4j wipe failed: {e}")
        
        # Phase 4: Monetization State Rebuild
        await ctx.send(">>> Phase 4: Rebuilding monetization state...")
        monetization = self.bot.get_cog("MonetizationCog")
        if monetization:
            try:
                await monetization.sync_tiers()
                await ctx.send("✅ Monetization tiers synced from roles")
            except Exception as e:
                logger.error(f"Monetization sync failed: {e}")
                await ctx.send(f"⚠️ Monetization sync failed: {e}")
        else:
            logger.warning("MonetizationCog not found during reset")

        await ctx.send("🔄 **CYCLE RESET COMPLETE** - System is clean. Shutting down for fresh reboot...")
        await self.bot.close()

    @commands.hybrid_command(name="cycleandrotate", description="ADMIN: Cycle reset + rotate salt (invalidates old backups)")
    async def cycle_and_rotate(self, ctx):
        """
        Perform a full cycle reset AND rotate the cryptographic salt.
        This permanently invalidates ALL previous backups.
        
        Use /cyclereset for normal resets (preserves salt, backups stay valid).
        Use /cycleandrotate when you want a clean cryptographic break.
        
        ADMIN ONLY.
        """
        await ctx.send(
            "⚠️ **CYCLE + SALT ROTATION INITIATED**\n"
            "This will **permanently invalidate ALL existing backups**.\n"
            "Rotating salt first..."
        )
        
        try:
            from src.security.rotate_salt import rotate_salt
            rotate_salt(confirm=True)
            from src.security.provenance import ProvenanceManager
            ProvenanceManager._salt_cache = None
            await ctx.send("🔑 Salt rotated. Old backups are now cryptographically invalid.")
        except Exception as e:
            logger.error(f"Salt rotation failed: {e}")
            await ctx.send(f"⚠️ Salt rotation failed: {e}. Proceeding with reset...")
        
        await self.cycle_reset(ctx)

    @commands.hybrid_command(name="purgeall", description="ADMIN: Delete all messages in the Ernos chat channel")
    async def purge_all(self, ctx):
        """
        Delete all messages from the TARGET_CHANNEL_ID channel.
        ADMIN ONLY - Use with caution.
        """
        target_channel = self.bot.get_channel(settings.TARGET_CHANNEL_ID)
        if not target_channel:
            try:
                target_channel = await self.bot.fetch_channel(settings.TARGET_CHANNEL_ID)
            except Exception as e:
                await ctx.send(f"❌ Could not find target channel `{settings.TARGET_CHANNEL_ID}`: {e}")
                return
        
        await ctx.send("🗑️ **PURGE INITIATED** - Deleting all messages...")
        
        deleted_count = 0
        try:
            while True:
                deleted = await target_channel.purge(limit=100)
                if not deleted:
                    break
                deleted_count += len(deleted)
                
            await ctx.send(f"✅ **PURGE COMPLETE** - Deleted {deleted_count} messages.")
        except Exception as e:
            logger.error(f"Purge failed: {e}")
            await ctx.send(f"⚠️ Purge failed: {e}")
    @commands.hybrid_command(name="nuke", description="ADMIN: Total system wipe — erases ALL data, KG, images, runtime, salt")
    @app_commands.describe(confirmation="Type CONFIRMNUKE to execute")
    async def nuke(self, ctx, confirmation: Optional[str] = None):
        """
        NUCLEAR OPTION: Complete annihilation of all system data.
        
        Unlike /cyclereset (which preserves personas, voice_models, salt, CORE KG),
        /nuke destroys EVERYTHING:
        - ALL memory directories (core, users, public, system, chroma, cache, archive, backups)
        - ALL generated images, audio, media
        - ALL KG nodes INCLUDING CORE foundation
        - ALL logs, traces, debug files
        - ALL quarantine, security profiles, manifests
        - Rotates cryptographic salt (invalidates ALL backups)
        - ALL in-memory state
        
        Requires: /nuke CONFIRMNUKE
        ADMIN ONLY.
        """
        if confirmation != "CONFIRMNUKE":
            await ctx.send(
                "☢️ **NUCLEAR WIPE** — This will destroy almost everything.\n"
                "- All memory (core, users, system)\n"
                "- All KG nodes **including CORE foundation**\n"
                "- All generated images, audio, media\n"
                "- All logs, caches, backups\n"
                "- Salt rotation (invalidates all backups)\n\n"
                "**Preserved:** Personas, Voice Models\n"
                "**No backup is created before wipe.**\n\n"
                "To proceed, run: `/nuke CONFIRMNUKE`"
            )
            return
        
        await ctx.send("☢️ **NUCLEAR WIPE INITIATED** — Total system destruction in progress...")
        
        # ─── Phase 0: Block new messages + flush in-memory state ──────
        await ctx.send(">>> Phase 0: Blocking input and flushing in-memory state...")
        settings.TESTING_MODE = True
        
        try:
            hippo = self.bot.hippocampus
            hippo._shutting_down = True
            
            if hasattr(hippo, 'stream') and hippo.stream:
                hippo.stream.turns.clear()
                hippo.stream.state = type(hippo.stream.state)()
            
            if hasattr(hippo, 'vector_store') and hippo.vector_store:
                if hasattr(hippo.vector_store, '_data'):
                    hippo.vector_store._data.clear()
                if hasattr(hippo.vector_store, 'reset'):
                    hippo.vector_store.reset()
            
            if hasattr(hippo, 'kg_consolidator') and hippo.kg_consolidator:
                if hasattr(hippo.kg_consolidator, '_buffer'):
                    hippo.kg_consolidator._buffer.clear()
            
            await ctx.send("✅ Phase 0 Complete: In-memory state flushed")
        except Exception as e:
            logger.error(f"Nuke: in-memory flush failed: {e}")
            await ctx.send(f"⚠️ Phase 0 partial: {e}")
        
        # ─── Phase 1: Salt rotation ──────────────────────────────────
        await ctx.send(">>> Phase 1: Rotating cryptographic salt...")
        try:
            from src.security.rotate_salt import rotate_salt
            rotate_salt(confirm=True)
            from src.security.provenance import ProvenanceManager
            ProvenanceManager._salt_cache = None
            await ctx.send("✅ Phase 1 Complete: Salt rotated — all existing backups invalidated")
        except Exception as e:
            logger.error(f"Nuke: salt rotation failed: {e}")
            await ctx.send(f"⚠️ Phase 1 failed: {e}")
        
        # ─── Phase 2: Total file system wipe ─────────────────────────
        await ctx.send(">>> Phase 2: Total file system wipe...")
        import shutil
        import os
        import tempfile
        
        # PRESERVE public personas (core infrastructure, not runtime data)
        personas_backup = None
        personas_src = "memory/public/personas"
        if os.path.exists(personas_src):
            personas_backup = os.path.join(tempfile.gettempdir(), "ernos_nuke_personas_backup")
            if os.path.exists(personas_backup):
                shutil.rmtree(personas_backup)
            shutil.copytree(personas_src, personas_backup)
            logger.info(f"NUKE: Preserved {len(os.listdir(personas_src))} public personas before wipe")
        
        # PRESERVE voice_models (core infrastructure, not runtime data)
        voice_models_backup = None
        voice_models_src = "memory/public/voice_models"
        if os.path.exists(voice_models_src):
            voice_models_backup = os.path.join(tempfile.gettempdir(), "ernos_nuke_voice_models_backup")
            if os.path.exists(voice_models_backup):
                shutil.rmtree(voice_models_backup)
            shutil.copytree(voice_models_src, voice_models_backup)
            logger.info("NUKE: Preserved voice_models before wipe")
        
        # Wipe ALL memory directories
        nuke_dirs = [
            "memory/users",
            "memory/core",
            "memory/public",
            "memory/system",
            "memory/chroma",
            "memory/cache",
            "memory/archive",
            "memory/backups",
            "memory/traces",
            "logs/autonomous",
            "logs/errors",
        ]
        
        dirs_deleted = 0
        for d in nuke_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                    dirs_deleted += 1
                    logger.info(f"NUKE: Destroyed directory: {d}")
                except Exception as e:
                    logger.error(f"NUKE: Failed to destroy {d}: {e}")
        
        # Wipe ALL loose files in memory/
        nuke_files = [
            "memory/goals.json",
            "memory/project_manifest.json",
            "memory/usage.json",
            "memory/security_profiles.json",
            "memory/lessons.json",
            "memory/relationships.json",
            "memory/preferences.json",
            "memory/quarantine.json",
            "memory/crawl_state.json",
            "memory/debug_prompt_last.txt",
            "logs/stream_of_consciousness.log",
        ]
        
        files_deleted = 0
        for f in nuke_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                    files_deleted += 1
                    logger.info(f"NUKE: Destroyed file: {f}")
                except Exception as e:
                    logger.error(f"NUKE: Failed to destroy {f}: {e}")
        
        # Catch any remaining files/dirs inside memory/ not explicitly listed
        if os.path.exists("memory"):
            for item in os.listdir("memory"):
                item_path = os.path.join("memory", item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        dirs_deleted += 1
                    elif os.path.isfile(item_path):
                        os.remove(item_path)
                        files_deleted += 1
                    logger.info(f"NUKE: Destroyed remaining: {item_path}")
                except Exception as e:
                    logger.error(f"NUKE: Failed to clean {item_path}: {e}")
        
        await ctx.send(
            f"✅ Phase 2 Complete: Destroyed {dirs_deleted} directories, {files_deleted} files\n"
            "   Salt: **ROTATED** | Media: **GONE** | Personas: **PRESERVED** | Voice models: **PRESERVED**"
        )
        
        # ─── Phase 3: Rebuild empty directory structure ──────────────
        await ctx.send(">>> Phase 3: Rebuilding directory structure and restoring preserved assets...")
        os.makedirs("memory/users", exist_ok=True)
        os.makedirs("memory/core", exist_ok=True)
        os.makedirs("memory/public", exist_ok=True)
        os.makedirs("memory/system", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Restore preserved personas
        try:
            if personas_backup and os.path.exists(personas_backup):
                shutil.copytree(personas_backup, personas_src, dirs_exist_ok=True)
                shutil.rmtree(personas_backup)
                logger.info("NUKE: Restored public personas after wipe")
        except Exception as e:
            logger.error(f"NUKE: Failed to restore personas: {e}")
            await ctx.send(f"⚠️ Failed to restore personas: {e}")
        
        # Restore preserved voice_models
        try:
            if voice_models_backup and os.path.exists(voice_models_backup):
                shutil.copytree(voice_models_backup, voice_models_src, dirs_exist_ok=True)
                shutil.rmtree(voice_models_backup)
                logger.info("NUKE: Restored voice_models after wipe")
        except Exception as e:
            logger.error(f"NUKE: Failed to restore voice_models: {e}")
            await ctx.send(f"⚠️ Failed to restore voice_models: {e}")
        
        await ctx.send("✅ Phase 3 Complete: Structure rebuilt, personas + voice models restored")
        
        # ─── Phase 4: Neo4j TOTAL wipe (including CORE foundation) ──
        await ctx.send(">>> Phase 4: Neo4j TOTAL wipe (**including CORE foundation**)...")
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            with driver.session() as session:
                total = session.run("MATCH (n) RETURN count(n) as c").single()['c']
                
                if total > 0:
                    # Delete EVERYTHING — no CORE preservation
                    session.run("MATCH (n) DETACH DELETE n")
                    await ctx.send(
                        f"✅ Phase 4 Complete: Destroyed **ALL** {total} KG nodes\n"
                        "   CORE foundation: **GONE** | User data: **GONE** | Synapses: **GONE**"
                    )
                else:
                    await ctx.send("✅ Phase 4 Complete: Neo4j was already empty")
            driver.close()
        except Exception as e:
            logger.error(f"NUKE: Neo4j wipe failed: {e}")
            await ctx.send(f"⚠️ Phase 4 failed: {e}")
        
        # ─── Phase 5: Confirmation ──────────────────────────────────
        await ctx.send(
            "☢️ **NUCLEAR WIPE COMPLETE**\n\n"
            "Destroyed:\n"
            "- ✅ Memory directories (core, users, system, chroma, cache)\n"
            "- ✅ Generated images, audio, and media\n"
            "- ✅ Knowledge Graph (ALL nodes including CORE foundation)\n"
            "- ✅ Logs, traces, debug files\n"
            "- ✅ Salt rotated (all backups invalidated)\n\n"
            "Preserved:\n"
            "- 🛡️ Personas\n"
            "- 🛡️ Voice models\n\n"
            "The system will now shut down. On next boot:\n"
            "- Foundation KG must be re-seeded\n\n"
            "Shutting down..."
        )
        await self.bot.close()


async def setup(bot):
    await bot.add_cog(AdminLifecycle(bot))
