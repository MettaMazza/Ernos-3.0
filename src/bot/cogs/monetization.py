
import discord
from discord.ext import commands
import logging
from src.core.flux_capacitor import FluxCapacitor
from config import settings

logger = logging.getLogger("MonetizationCog")

# Role Name to Tier Mapping
ROLE_TIER_MAP = {
    "pollinator": 1,
    "planter": 2,
    "gardener": 3,
    "terraformer": 4,
    "terra-former": 4 # handle hyphen variation
}

class MonetizationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.flux = FluxCapacitor(bot)
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Sync all guild members' roles to flux tiers on startup."""
        await self.sync_tiers()

    async def sync_tiers(self):
        """Core logic to scan all members and update flux tiers based on roles."""
        logger.info("Starting global tier synchronization...")
        synced = 0
        total_scanned = 0
        
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                total_scanned += 1
                
                # Calculate max tier from current roles
                max_tier = 0
                for role in member.roles:
                    role_lower = role.name.lower()
                    if role_lower in ROLE_TIER_MAP:
                        max_tier = max(max_tier, ROLE_TIER_MAP[role_lower])
                    else:
                        for key, tier in ROLE_TIER_MAP.items():
                            if key in role_lower:
                                max_tier = max(max_tier, tier)
                
                current_tier = self.flux.get_tier(member.id)
                if max_tier != current_tier:
                    self.flux.set_tier(member.id, max_tier)
                    synced += 1
                    logger.info(f"Tier Sync: {member.display_name} ({member.id}) {current_tier} -> {max_tier}")
        
        if synced:
            logger.info(f"Tier sync complete: {synced} user(s) reconciled out of {total_scanned} scanned.")
        else:
            logger.info(f"Tier sync complete: All {total_scanned} users already up to date.")
            
    @commands.hybrid_command(name="sync_tier", description="ADMIN: Manually sync all user tiers with Discord roles")
    @commands.has_permissions(administrator=True)
    async def manual_sync(self, ctx):
        """Manually trigger a global tier sync."""
        await ctx.send("🔄 Starting global tier sync...")
        await self.sync_tiers()
        await ctx.send("✅ Tier sync complete. Check logs for details.")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """
        Watch for role changes and update Flux Tier.
        We take the HIGHEST tier role the user has.
        """
        # If roles didn't change, ignore
        if before.roles == after.roles:
            return

        # Calculate max tier from current roles
        max_tier = 0
        current_roles = [r.name.lower() for r in after.roles]
        
        for role_name in current_roles:
            # Check direct match
            if role_name in ROLE_TIER_MAP:
                max_tier = max(max_tier, ROLE_TIER_MAP[role_name])
            # Check fuzzy match if needed (e.g. "pollinator 🐝")
            else:
                for key, tier in ROLE_TIER_MAP.items():
                    if key in role_name:
                        max_tier = max(max_tier, tier)

        # Update if changed
        current_flux_tier = self.flux.get_tier(after.id)
        if max_tier != current_flux_tier:
            logger.info(f"Role change for {after.display_name}: Tier {current_flux_tier} -> {max_tier}")
            self.flux.set_tier(after.id, max_tier)
            
            # Send DM notification of upgrade if tier increased
            if max_tier > current_flux_tier and max_tier > 0:
                try:
                    await after.send(f"🌱 **Symbiosis Deepened**\nYour tier has been updated to **Level {max_tier}**. Thank you for feeding the ecosystem.")
                except Exception:
                    pass # DM might be blocked

    @commands.command(name="check_tier")
    async def check_tier(self, ctx, user: discord.User = None):
        """Check a user's current Flux Tier."""
        target = user or ctx.author
        status = self.flux.get_status(target.id)
        
        embed = discord.Embed(title=f"Flux Status: {target.display_name}", color=0x00ff00)
        embed.add_field(name="Tier", value=str(status["tier"]), inline=True)
        embed.add_field(name="Used", value=f"{status['used']} / {status['limit']}", inline=True)
        
        if status["limit"] > 1000:
             remaining = "∞"
        else:
             remaining = str(status["remaining"])
        embed.add_field(name="Remaining", value=remaining, inline=True)
        
        # Format reset time
        import datetime
        reset_dt = datetime.datetime.fromtimestamp(status["next_reset"])
        embed.set_footer(text=f"Resets at {reset_dt.strftime('%H:%M:%S')}")
        
        await ctx.send(embed=embed)

    @commands.command(name="set_tier")
    @commands.has_permissions(administrator=True)
    async def set_tier(self, ctx, user: discord.User, tier: int):
        """Manually set a user's tier (Admin only)."""
        self.flux.set_tier(user.id, tier)
        await ctx.send(f"✅ Set {user.mention} to Tier {tier}.")

    @commands.command(name="reset_flux")
    @commands.has_permissions(administrator=True)
    async def reset_flux(self, ctx, user: discord.User):
        """Reset a user's message count cycle."""
        # We can implement a reset method in Flux or just manually manipulate
        # For now, let's use the private load/save since public interface is limited
        data = self.flux._load(user.id)
        data["msg_count"] = 0
        data["last_reset"] = 0 # Force immediate reset on next consume
        data["warned"] = False
        self.flux._save(user.id, data)
        await ctx.send(f"✅ Reset flux cycle for {user.mention}.")

async def setup(bot):
    await bot.add_cog(MonetizationCog(bot))
