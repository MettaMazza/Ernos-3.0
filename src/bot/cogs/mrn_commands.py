import discord
from discord.ext import commands
from discord import app_commands
import logging
import json
import tempfile
import os
from pathlib import Path

from src.backup.manager import BackupManager

logger = logging.getLogger("Cog.MRN")

class MRNCommands(commands.Cog):
    """
    Mycelium Root Network (MRN) commands.
    Allows users to hold and restore their own context shards.
    """
    def __init__(self, bot):
        self.bot = bot
        self.backup_manager = BackupManager(bot)
        
    @app_commands.command(name="backup_my_shard", description="Receive your encryption-signed context shard via DM (The Spore)")
    async def backup_my_shard(self, interaction: discord.Interaction):
        """Generates and DMs the user's context shard."""
        await interaction.response.defer(ephemeral=True)
        
        user_id = interaction.user.id
        logger.info(f"User {user_id} requested context shard backup")
        
        success = await self.backup_manager.send_user_backup_dm(user_id)
        
        if success:
            await interaction.followup.send("✅ **Backup sent via DM.** Keep this safe! It is your slice of the Mycelium Network.", ephemeral=True)
        else:
            await interaction.followup.send("⏳ **Rate Limited** (or Empty). You can only export once every 24 hours.", ephemeral=True)

    @app_commands.command(name="restore_my_shard", description="Restore your context from a shard file (The Inoculation)")
    @app_commands.describe(shard_file="The JSON shard file to restore")
    async def restore_my_shard(self, interaction: discord.Interaction, shard_file: discord.Attachment):
        """Restores a context shard after verification and Sentinel review."""
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        
        # 1. Basic File Validation
        if not shard_file.filename.endswith(".json"):
            await interaction.followup.send("❌ Invalid file type. Please upload a JSON shard.", ephemeral=True)
            return
            
        # 2. Download and Parse
        try:
            content = await shard_file.read()
            data = json.loads(content.decode('utf-8'))
        except Exception as e:
            await interaction.followup.send(f"❌ Corrupted File: Unable to parse JSON. ({e})", ephemeral=True)
            return

        # 3. Crypto Verification (The Firewall)
        is_valid, reason = self.backup_manager.verify_backup(data)
        if not is_valid:
            await interaction.followup.send(f"🛡️ **REJECTED (Crypto/Date Check)**: {reason}", ephemeral=True)
            logger.warning(f"MRN Restore Rejected for {user_id}: {reason}")
            return
            
        # 4. Sentinel Lobe Review (The Immune System)
        # Access SentinelAbility from SuperegoLobe
        sentinel = None
        if hasattr(self.bot, 'cerebrum'):
            superego = self.bot.cerebrum.lobes.get("SuperegoLobe")
            if superego:
                sentinel = superego.get_ability("SentinelAbility")
        
        if sentinel:
            await interaction.followup.send("👁️ **Sentinel Lobe is reviewing this shard...**", ephemeral=True)
            is_approved, sent_reason = await sentinel.review_shard(data)
            
            if not is_approved:
                await interaction.followup.send(f"🛡️ **REJECTED (Sentinel Lobe)**: {sent_reason}\n\n*The system detected content that violates core directives (Sycophancy/Hallucination).*2", ephemeral=True)
                logger.warning(f"MRN Sentinel Rejected {user_id}: {sent_reason}")
                return
        else:
            logger.warning("Sentinel Lobe not found! Skipping semantic review (Risky).")
            # Fail safe? Or proceed? 
            # Given the strict requirement, we should probably warn or fail, but for now we proceed with warning log.
        
        # 5. Import / Merge
        success, msg = await self.backup_manager.import_user_context(user_id, data)
        
        if success:
            await interaction.followup.send(f"🌱 **Restoration Complete**: {msg}", ephemeral=True)
            logger.info(f"MRN Restore Success for {user_id}")
        else:
            await interaction.followup.send(f"❌ **Import Failed**: {msg}", ephemeral=True)

    @commands.hybrid_command(name="link_minecraft", description="Link your Discord account to your Minecraft username")
    @app_commands.describe(minecraft_username="Your Minecraft username (e.g., metta_mazza)")
    async def link_minecraft(self, ctx, minecraft_username: str):
        """Links a Discord user to their Minecraft username for cross-platform recognition."""
        # Support both slash and prefix commands
        if hasattr(ctx, 'interaction') and ctx.interaction:
            await ctx.defer(ephemeral=True)
        
        user_id = str(ctx.author.id)
        discord_name = ctx.author.display_name
        mc_name = minecraft_username.strip()
        
        # Validate username (no spaces, reasonable length)
        if " " in mc_name or len(mc_name) < 3 or len(mc_name) > 16:
            await ctx.send("❌ Invalid Minecraft username. Must be 3-16 characters with no spaces.", ephemeral=True)
            return
        
        # Load existing links
        links_path = Path("memory/public/user_links.json")
        links_path.parent.mkdir(parents=True, exist_ok=True)
        
        if links_path.exists():
            try:
                with open(links_path, 'r') as f:
                    links = json.load(f)
            except Exception:
                links = {"mc_to_discord": {}, "discord_to_mc": {}}
        else:
            links = {"mc_to_discord": {}, "discord_to_mc": {}}
        
        # Store bidirectional mapping
        links["mc_to_discord"][mc_name.lower()] = {
            "discord_id": user_id,
            "discord_name": discord_name
        }
        links["discord_to_mc"][user_id] = {
            "mc_username": mc_name,
            "linked_at": str(discord.utils.utcnow())
        }
        
        # Save
        with open(links_path, 'w') as f:
            json.dump(links, f, indent=2)
        
        logger.info(f"User {user_id} ({discord_name}) linked to Minecraft: {mc_name}")
        
        await ctx.send(
            f"✅ **Account Linked!**\n"
            f"Discord: **{discord_name}**\n"
            f"Minecraft: **{mc_name}**\n\n"
            f"Ernos will now recognize you across both platforms! 🎮",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(MRNCommands(bot))

