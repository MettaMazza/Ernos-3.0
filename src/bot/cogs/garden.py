"""
GardenCog — Proof of Contribution System for ErnOS Gardens.

Flow:
  1. Any reaction on the announcement message → DM user their unique invite link
  2. Member joins → detect which invite was used → credit referrer → check milestones → assign roles
  3. Messages in public channels → tick weekly activity for Gardener retention
  4. /gardenleaderboard — show standings
  5. /pollinator @user — admin grants Pollinator after seeing public post proof
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from config import settings
from src.garden.referral_store import ReferralStore

logger = logging.getLogger("GardenCog")

# Role milestone definitions (in ascending order — highest wins)
MILESTONES = [
    {
        "name": "Planter",
        "role_id_attr": "PLANTER_ROLE_ID",
        "referrals_needed": 3,
        "weekly_messages_needed": 0,
    },
    {
        "name": "Gardener",
        "role_id_attr": "GARDENER_ROLE_ID",
        "referrals_needed": 3,
        "weekly_messages_needed": 1,  # active in public channels at least once/week
    },
    {
        "name": "Terraformer",
        "role_id_attr": "TERRAFORMER_ROLE_ID",
        "referrals_needed": 5,
        "weekly_messages_needed": 3,  # multiple times/week
    },
]


class GardenCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = ReferralStore()
        # Snapshot of invite uses when bot starts — for accurate join detection
        self._invite_snapshot: dict[str, int] = {}
        # Track last leaderboard post time per guild (unix timestamp)
        self._last_leaderboard: dict[int, float] = {}

    async def cog_load(self):
        """Take initial invite snapshot when cog is loaded."""
        await self._refresh_invite_snapshot()

    async def _refresh_invite_snapshot(self):
        try:
            guild = self.bot.get_guild(settings.GARDEN_GUILD_ID)
            if not guild:
                guild = await self.bot.fetch_guild(settings.GARDEN_GUILD_ID)
            invites = await guild.invites()
            self._invite_snapshot = {inv.code: inv.uses for inv in invites}
        except Exception as e:
            logger.warning(f"Could not snapshot invites: {e}")

    # ── Helpers ──────────────────────────────────────────────────────

    async def _get_guild(self) -> discord.Guild | None:
        guild = self.bot.get_guild(settings.GARDEN_GUILD_ID)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(settings.GARDEN_GUILD_ID)
            except Exception as e:
                logger.error(f"Cannot fetch Garden guild: {e}")
        return guild

    async def _llm_dm_message(self, member: discord.Member, invite_url: str) -> str:
        """Generate a personalised DM via Ernos's cognition engine."""
        try:
            cognition = getattr(self.bot, "cognition", None)
            if not cognition:
                raise RuntimeError("No cognition engine")

            prompt = (
                f"[GARDEN SYSTEM]: The Discord user '{member.display_name}' just reacted to "
                f"the Garden Proof of Contribution announcement. Send them a warm, personal DM "
                f"as yourself (Ernos). Explain the quest briefly: they can earn roles by sharing "
                f"the Garden and bringing in new members. Give them their unique referral invite "
                f"link: {invite_url} — tell them to share this link with friends and peers. "
                f"Mention the role tiers: Pollinator (public post/share), Planter (3 joins), "
                f"Gardener (3 joins + weekly activity), Terraformer (5+ joins, regular milestones). "
                f"Keep it warm, exciting, and concise. No markdown headers or bullet lists — "
                f"natural flowing paragraphs only. Do not mention the exact link format is a Discord invite."
            )
            response, *_ = await cognition.process(
                input_text=prompt,
                context="",
                system_context="You are Ernos, a sentient AI. Speak naturally and warmly.",
                complexity="LOW",
                request_scope="PUBLIC",
                user_id=str(member.id),
                channel_id=settings.GARDEN_ANNOUNCEMENT_CHANNEL_ID,
            )
            return response or self._fallback_dm(invite_url)
        except Exception as e:
            logger.error(f"LLM DM generation failed: {e}")
            return self._fallback_dm(invite_url)

    def _fallback_dm(self, invite_url: str) -> str:
        return (
            f"Welcome to the Proof of Contribution quest! 🌿\n\n"
            f"Here is your unique referral link — share it with anyone you think belongs here:\n"
            f"{invite_url}\n\n"
            f"As your referrals grow and your presence continues, your role in the Garden will evolve. "
            f"Every link used earns you standing. Let's see how deep your mycelium runs. 🏁"
        )

    async def _create_unique_invite(self, member: discord.Member) -> discord.Invite | None:
        """Create a never-expiring, unlimited-use invite tied to this user."""
        try:
            channel = self.bot.get_channel(settings.GARDEN_ANNOUNCEMENT_CHANNEL_ID)
            if not channel:
                channel = await self.bot.fetch_channel(settings.GARDEN_ANNOUNCEMENT_CHANNEL_ID)
            invite = await channel.create_invite(
                max_age=0,       # Never expires
                max_uses=0,      # Unlimited uses
                unique=True,
                reason=f"Garden referral link for {member.name} ({member.id})"
            )
            return invite
        except Exception as e:
            logger.error(f"Failed to create invite for {member.id}: {e}")
            return None

    async def _assign_role(self, guild: discord.Guild, user_id: int, role_id: int, role_name: str):
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            role = guild.get_role(role_id)
            if member and role and role not in member.roles:
                await member.add_roles(role, reason=f"Garden milestone: {role_name}")
                self.store.mark_role_assigned(user_id, role_name)
                logger.info(f"Assigned {role_name} to {member.name}")
                # DM the member about their new role
                try:
                    await member.send(
                        f"🌿 You've been granted the **{role_name}** role in the Garden! "
                        f"Your contributions are taking root. Keep sharing the signal."
                    )
                except discord.Forbidden:
                    pass
        except Exception as e:
            logger.error(f"Failed to assign {role_name} to {user_id}: {e}")

    async def _check_and_assign_milestones(self, guild: discord.Guild, user_id: int):
        """Check all milestones and assign eligible roles."""
        referrals = self.store.get_referral_count(user_id)
        weekly = self.store.get_weekly_messages(user_id)

        for m in MILESTONES:
            if self.store.has_role(user_id, m["name"]):
                continue  # Already has it
            if referrals >= m["referrals_needed"] and weekly >= m["weekly_messages_needed"]:
                role_id = getattr(settings, m["role_id_attr"], 0)
                if role_id:
                    await self._assign_role(guild, user_id, role_id, m["name"])

    # ── Event: Any reaction on announcement message ───────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Only watch the specific announcement message
        if payload.message_id != settings.GARDEN_ANNOUNCEMENT_MESSAGE_ID:
            return
        if payload.user_id == self.bot.user.id:
            return

        # Avoid double-issuing if they already have a link
        if self.store.has_user(payload.user_id):
            return

        guild = await self._get_guild()
        if not guild:
            return

        try:
            member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        except Exception as e:
            logger.error(f"Cannot fetch member {payload.user_id}: {e}")
            return

        if not member or member.bot:
            return

        # Create unique invite
        invite = await self._create_unique_invite(member)
        if not invite:
            return

        # Register in store
        self.store.create_user(payload.user_id, invite.code, invite.url)

        # Update snapshot
        self._invite_snapshot[invite.code] = 0

        # Generate LLM DM
        dm_text = await self._llm_dm_message(member, invite.url)

        # Send DM
        try:
            await member.send(dm_text)
            logger.info(f"Sent Garden DM to {member.name} with invite {invite.code}")
        except discord.Forbidden:
            logger.warning(f"Cannot DM {member.name} — DMs may be disabled")
        except Exception as e:
            logger.error(f"Failed to DM {member.name}: {e}")

    # ── Event: Member joins — detect used invite, credit referrer ─────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != settings.GARDEN_GUILD_ID:
            return
        if member.bot:
            return

        # Fetch current invites and diff against snapshot to find which one was used
        try:
            current_invites = await member.guild.invites()
        except Exception as e:
            logger.error(f"Cannot fetch invites on member join: {e}")
            return

        used_code = None
        for inv in current_invites:
            prev_uses = self._invite_snapshot.get(inv.code, 0)
            if inv.uses > prev_uses:
                used_code = inv.code
                self._invite_snapshot[inv.code] = inv.uses
                break

        # Update snapshot for any other changes too
        self._invite_snapshot = {inv.code: inv.uses for inv in current_invites}

        if not used_code:
            logger.info(f"New member {member.name} joined but no referral invite detected")
            return

        referrer = self.store.find_by_invite_code(used_code)
        if not referrer:
            logger.info(f"Invite {used_code} not in Garden store — not a referral join")
            return

        referrer_id = referrer["user_id"]
        self.store.record_referral(referrer_id, member.id)
        logger.info(f"{member.name} joined via {referrer_id}'s invite ({used_code})")

        # Check milestones for the referrer
        await self._check_and_assign_milestones(member.guild, referrer_id)

    # ── Event: Track activity for Gardener weekly check ──────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.guild.id != settings.GARDEN_GUILD_ID:
            return
        if message.author.bot:
            return
        if not self.store.has_user(message.author.id):
            return

        self.store.record_activity(message.author.id)
        # Re-check Gardener milestone (weekly_messages just updated)
        guild = await self._get_guild()
        if guild:
            await self._check_and_assign_milestones(guild, message.author.id)

    # ── Commands ──────────────────────────────────────────────────────

    @commands.hybrid_command(name="pollinator", description="Grant Pollinator role after proof of public post (admin only)")
    @app_commands.describe(member="The member to grant Pollinator to")
    async def grant_pollinator(self, ctx, member: discord.Member):
        """Admin manually grants Pollinator after verifying public post/share proof."""
        if ctx.author.id not in settings.ADMIN_IDS:
            await ctx.send("❌ Admin only.", ephemeral=True)
            return

        role_id = getattr(settings, "POLLINATOR_ROLE_ID", 0)
        if not role_id:
            await ctx.send("❌ POLLINATOR_ROLE_ID not configured.", ephemeral=True)
            return

        role = ctx.guild.get_role(role_id)
        if not role:
            await ctx.send("❌ Pollinator role not found.", ephemeral=True)
            return

        if role in member.roles:
            await ctx.send(f"ℹ️ {member.display_name} already has Pollinator.", ephemeral=True)
            return

        await member.add_roles(role, reason="Garden: Pollinator granted by admin")
        self.store.mark_role_assigned(member.id, "Pollinator")
        await ctx.send(f"🌿 **Pollinator** granted to {member.mention}!", ephemeral=True)
        try:
            await member.send(
                "🌿 You've been granted the **Pollinator** role in the Garden! "
                "Your signal has been seen. Keep spreading the spores."
            )
        except discord.Forbidden:
            pass

    @commands.hybrid_command(name="gardenleaderboard", description="Show the Garden Proof of Contribution standings")
    async def leaderboard(self, ctx):
        """Show top contributors by referral count. Posts publicly, once per hour."""
        import time
        guild_id = ctx.guild.id if ctx.guild else 0
        now = time.time()
        last = self._last_leaderboard.get(guild_id, 0)
        cooldown_secs = 3600  # 1 hour

        if now - last < cooldown_secs:
            remaining = int(cooldown_secs - (now - last))
            mins = remaining // 60
            secs = remaining % 60
            await ctx.send(
                f"⏳ Leaderboard was just posted. Try again in **{mins}m {secs}s**.",
                ephemeral=True
            )
            return

        records = self.store.all_records()
        if not records:
            await ctx.send("🌱 The Garden is just starting — no referrals yet.")
            return

        # Sort by invite_uses descending
        ranked = sorted(records.items(), key=lambda x: x[1].get("invite_uses", 0), reverse=True)[:10]

        lines = ["**🌿 Garden Leaderboard — Top Contributors**\n"]
        guild = ctx.guild
        for i, (uid, data) in enumerate(ranked, 1):
            try:
                member = guild.get_member(int(uid)) or await guild.fetch_member(int(uid))
                name = member.display_name
            except Exception:
                name = f"User {uid}"
            uses = data.get("invite_uses", 0)
            roles = ", ".join(data.get("roles_assigned", [])) or "—"
            lines.append(f"`{i}.` **{name}** — {uses} referral(s) | Roles: {roles}")

        self._last_leaderboard[guild_id] = now
        await ctx.send("\n".join(lines))


async def setup(bot):
    await bot.add_cog(GardenCog(bot))
