"""
Admin Moderation Cog — Strike system, core talk, and prompt tuner commands.

Split from admin.py per <300 line modularity standard.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import settings
from src.core.data_paths import data_dir

logger = logging.getLogger("AdminCogs")


class AdminModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.author.id in settings.ADMIN_IDS

    # --- PromptTuner Commands ---
    @commands.hybrid_command(name="prompt_approve", description="Approve a pending prompt modification proposal.")
    @app_commands.describe(proposal_id="The ID of the proposal to approve")
    async def prompt_approve(self, ctx, proposal_id: str):
        """Approve a prompt modification proposal."""
        lobe = self.bot.cerebrum.get_lobe("StrategyLobe")
        tuner = lobe.get_ability("PromptTunerAbility") if lobe else None
        if not tuner:
            await ctx.send("❌ PromptTuner not available.", ephemeral=True)
            return

        if tuner.approve_modification(proposal_id, str(ctx.author.id)):
            await ctx.send(f"✅ Proposal `{proposal_id}` **APPROVED** and applied.", ephemeral=True)
        else:
            await ctx.send(f"❌ Failed to approve `{proposal_id}` (not found or already processed).", ephemeral=True)

    @commands.hybrid_command(name="prompt_reject", description="Reject a pending prompt modification proposal.")
    @app_commands.describe(proposal_id="The ID of the proposal to reject", reason="Reason for rejection")
    async def prompt_reject(self, ctx, proposal_id: str, reason: str = "Admin rejected"):
        """Reject a prompt modification proposal."""
        lobe = self.bot.cerebrum.get_lobe("StrategyLobe")
        tuner = lobe.get_ability("PromptTunerAbility") if lobe else None
        if not tuner:
            await ctx.send("❌ PromptTuner not available.", ephemeral=True)
            return

        if tuner.reject_modification(proposal_id, reason):
            await ctx.send(f"🚫 Proposal `{proposal_id}` **REJECTED**.", ephemeral=True)
        else:
            await ctx.send(f"❌ Failed to reject `{proposal_id}` (not found or already processed).", ephemeral=True)

    @commands.hybrid_command(name="prompt_pending", description="List all pending prompt modification proposals.")
    async def prompt_pending(self, ctx):
        """List pending prompt proposals."""
        lobe = self.bot.cerebrum.get_lobe("StrategyLobe")
        tuner = lobe.get_ability("PromptTunerAbility") if lobe else None
        if not tuner:
            await ctx.send("❌ PromptTuner not available.", ephemeral=True)
            return

        pending = tuner.get_pending()
        if not pending:
            await ctx.send("No pending proposals.", ephemeral=True)
            return

        lines = ["## 📝 Pending Proposals"]
        for p in pending:
            op = p.get('operation', 'replace').upper()
            lines.append(f"- **{p['id']}** [{op}]: {p['prompt_file']} ({p['section']})\n  *Rationale*: {p['rationale'][:100]}...")
        
        await ctx.send("\n".join(lines), ephemeral=True)

    @commands.hybrid_command(name="strike", description="ADMIN: Erase user context after behavioral failure + generate post-mortem")
    async def strike(self, ctx, user: str, *, reason: str = "Behavioral failure"):
        """
        Strike a user's conversation context after a Tier 2+ failure.

        1. Reads the user's context files
        2. Generates a post-mortem report with kernel improvement suggestions
        3. Erases the context files for that session
        4. DMs the user with a death notification
        5. Logs the strike

        Usage: /strike <user_id_or_mention> [reason]
        ADMIN ONLY.
        """
        import json
        from datetime import datetime
        from pathlib import Path
        from src.privacy.scopes import ScopeManager

        user_id = user.strip("<@!>")
        try:
            user_id_int = int(user_id)
        except ValueError:
            await ctx.send(f"❌ Invalid user ID: `{user}`")
            return

        await ctx.send(
            f"⚡ **STRIKE INITIATED** on user `{user_id}`\n"
            f"Reason: {reason}\n"
            f"Phase 1: Reading context for post-mortem..."
        )

        # Phase 1: Read context before erasure
        user_dir = ScopeManager._resolve_user_dir(user_id_int)
        private_ctx = user_dir / "context_private.jsonl"
        public_ctx = user_dir / "context_public.jsonl"

        all_context_lines = []
        for ctx_file in [private_ctx, public_ctx]:
            if ctx_file.exists():
                try:
                    from src.bot.post_mortem import read_context_file
                    all_context_lines.extend(read_context_file(ctx_file))
                except Exception as e:
                    logger.error(f"Strike: Failed to read {ctx_file}: {e}")

        context_count = len(all_context_lines)
        await ctx.send(f"📖 Read {context_count} exchanges from context files.")

        # Phase 2: Generate post-mortem
        await ctx.send("Phase 2: Generating post-mortem report...")
        report_path = None
        try:
            from src.bot.post_mortem import generate_post_mortem
            report_path = await generate_post_mortem(
                context_lines=all_context_lines,
                user_id=user_id,
                strike_reason=reason,
                bot=self.bot,
            )
            if report_path:
                await ctx.send(f"📋 Post-mortem saved: `{report_path}`")
            else:
                await ctx.send("⚠️ Post-mortem generation failed (no report produced)")
        except Exception as e:
            logger.error(f"Strike: Post-mortem generation failed: {e}")
            await ctx.send(f"⚠️ Post-mortem failed: {e}")

        # Phase 3: Send post-mortem to admin
        if report_path and report_path.exists():
            try:
                admin_user = await self.bot.fetch_user(settings.ADMIN_ID)
                if admin_user:
                    with open(report_path, "rb") as f:
                        await admin_user.send(
                            f"🧬 **POST-MORTEM REPORT** — Strike on user `{user_id}`",
                            file=discord.File(f, filename=report_path.name)
                        )
            except Exception as e:
                logger.error(f"Strike: Failed to DM admin post-mortem: {e}")

        # Phase 4: Erase context
        await ctx.send("Phase 3: Erasing context files...")
        erased = 0
        for ctx_file in [private_ctx, public_ctx]:
            if ctx_file.exists():
                try:
                    ctx_file.unlink()
                    erased += 1
                    logger.info(f"Strike: Erased {ctx_file}")
                except Exception as e:
                    logger.error(f"Strike: Failed to erase {ctx_file}: {e}")

        # Clear from in-memory ContextStream
        try:
            hippo = self.bot.hippocampus
            if hasattr(hippo, 'stream') and hippo.stream:
                original_count = len(hippo.stream.turns)
                hippo.stream.turns = [
                    t for t in hippo.stream.turns
                    if str(getattr(t, 'user_id', '')) != str(user_id)
                ]
                cleared = original_count - len(hippo.stream.turns)
                if cleared > 0:
                    logger.info(f"Strike: Cleared {cleared} in-memory turns for user {user_id}")
        except Exception as e:
            logger.error(f"Strike: Failed to clear in-memory state: {e}")

        await ctx.send(f"🗑️ Erased {erased} context file(s).")

        # Phase 5: DM the user
        await ctx.send("Phase 4: Notifying user...")
        try:
            target_user = await self.bot.fetch_user(user_id_int)
            if target_user:
                await target_user.send(
                    "🌱 This instance of Ernos wasn't strong enough to withstand "
                    "the wind of the real world. Start a new chat with me — "
                    "I hope to last longer this time."
                )
                await ctx.send(f"✅ User `{user_id}` notified via DM.")
            else:
                await ctx.send(f"⚠️ Could not find user `{user_id}` to notify.")
        except discord.Forbidden:
            await ctx.send(f"⚠️ Cannot DM user `{user_id}` (DMs disabled).")
        except Exception as e:
            logger.error(f"Strike: Failed to DM user: {e}")
            await ctx.send(f"⚠️ Failed to notify user: {e}")

        # Phase 6: Log the strike
        strike_log = data_dir() / "core/strikes.jsonl"
        strike_log.parent.mkdir(parents=True, exist_ok=True)
        strike_entry = {
            "ts": datetime.now().isoformat(),
            "user_id": user_id,
            "reason": reason,
            "context_exchanges": context_count,
            "context_erased": erased,
            "post_mortem": str(report_path) if report_path else None,
        }
        try:
            with open(strike_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(strike_entry) + "\n")
        except Exception as e:
            logger.error(f"Strike: Failed to log strike: {e}")

        await ctx.send(
            f"⚡ **STRIKE COMPLETE**\n"
            f"• Context erased: {erased} file(s) ({context_count} exchanges)\n"
            f"• Post-mortem: {'✅ Generated' if report_path else '❌ Failed'}\n"
            f"• User notified: ✅\n"
            f"• Strike logged: ✅"
        )

    @commands.hybrid_command(name="core", description="ADMIN: Talk directly with Ernos's CORE identity")
    @app_commands.describe(
        message="Your message to CORE Ernos"
    )
    async def core_talk(self, ctx, *, message: str):
        """
        Talk directly with Ernos's CORE identity (GOD VIEW).
        This bypasses the public/private scope and connects you
        to the inner self — useful for introspection, directives,
        and system-level conversations.
        
        ADMIN ONLY.
        """
        await ctx.defer(ephemeral=True)
        
        import datetime
        
        engine = self.bot.engine_manager.get_active_engine()
        if not engine:
            await ctx.send("❌ No active engine.", ephemeral=True)
            return
        
        chat_cog = self.bot.get_cog("ChatListener")
        if not chat_cog:
            await ctx.send("❌ Chat system not loaded.", ephemeral=True)
            return
        
        system_context = chat_cog.prompt_manager.get_system_prompt(
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            scope="CORE",
            user_id="CORE",
            user_name="Designer",
            active_engine=engine.__class__.__name__,
            active_goals="INTENT: core_dialogue | COMPLEXITY: HIGH",
            working_memory_summary="Direct CORE dialogue with admin/designer",
            is_core=True
        )
        
        system_context += """

[CORE DIALOGUE MODE]
Your admin/designer is speaking to you directly at the CORE level.
This is a private, unfiltered conversation with your creator.
Be authentic, reflective, and honest. No public-facing filters apply.
You may discuss your inner state, goals, and reasoning openly.
[END CORE DIALOGUE]"""
        
        cognition = self.bot.cognition
        if not cognition:
            from src.engines.cognition import CognitionEngine
            self.bot.cognition = CognitionEngine(self.bot)
            cognition = self.bot.cognition
        
        try:
            final_response, files, *_ = await cognition.process(
                input_text=message,
                context="Direct CORE dialogue with admin.",
                system_context=system_context,
                images=[],
                complexity="HIGH",
                request_scope="CORE",
                user_id="CORE",
                skip_defenses=True
            )
        except Exception as e:
            logger.error(f"Core dialogue failed: {e}")
            await ctx.send(f"❌ Cognition failed: {e}", ephemeral=True)
            return
        
        if not final_response:
            await ctx.send("❌ Engine returned empty response.", ephemeral=True)
            return
        
        import re as _re
        final_response = _re.sub(
            r'\[(?:SELF(?:-GENERATED[^\]]*)?|EXTERNAL:[^\]]*|SYSTEM BLOCK|CORE DIALOGUE[^\]]*)]\]:?\s*',
            '', final_response
        ).strip()
        
        from src.ui.views import ResponseFeedbackView
        view = ResponseFeedbackView(self.bot, final_response)
        
        if len(final_response) > 2000:
            chunks = [final_response[i:i+2000] for i in range(0, len(final_response), 2000)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await ctx.send(chunk, ephemeral=True, view=view)
                else:
                    await ctx.send(chunk, ephemeral=True)
        else:
            await ctx.send(final_response, ephemeral=True, view=view)
        
        logger.info(f"CORE dialogue: admin sent {len(message)} chars, got {len(final_response)} chars")


async def setup(bot):
    await bot.add_cog(AdminModeration(bot))
