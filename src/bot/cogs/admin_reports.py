"""
Admin Reports Cog — User reporting and town hall topic suggestions.

Split from admin.py per <300 line modularity standard.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import settings

logger = logging.getLogger("AdminCogs")


class AdminReports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.author.id in settings.ADMIN_IDS

    @commands.hybrid_command(name="townhall_suggest", description="Suggest 3 topics for the next town hall discussion")
    @app_commands.describe(
        topic1="First topic suggestion",
        topic2="Second topic suggestion", 
        topic3="Third topic suggestion"
    )
    async def townhall_suggest(self, ctx, topic1: str, topic2: str, topic3: str):
        """Suggest 3 topics for the next town hall discussion."""
        town_hall = getattr(self.bot, 'town_hall', None)
        if not town_hall:
            await ctx.send("❌ Town Hall daemon is not active.", ephemeral=True)
            return
        
        topics = [topic1, topic2, topic3]
        added = town_hall.add_suggestion(str(ctx.author.id), topics)
        
        if added > 0:
            topic_list = "\n".join([f"  {i+1}. {t}" for i, t in enumerate(topics) if t.strip()])
            queue_size = len(town_hall._suggested_topics)
            await ctx.send(
                f"✅ **{added} topic(s) submitted to Town Hall!**\n{topic_list}\n\n"
                f"📋 Queue size: {queue_size} topic(s) pending",
                ephemeral=True
            )
        else:
            await ctx.send("❌ No valid topics provided. Topics must be at least 4 characters.", ephemeral=True)

    @commands.hybrid_command(name="report", description="ADMIN: Generate a detailed user report (DM only)")
    @app_commands.describe(
        username="Optional: specific username or user ID. Leave blank for all users."
    )
    async def user_report(self, ctx, username: str = None):
        """
        Generate a comprehensive report on user DM activity and context.
        
        - /report → Report on ALL users with DM context
        - /report <username or ID> → Detailed report on one user
        
        DM ONLY. ADMIN ONLY.
        """
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("❌ `/report` can only be used in DMs with me.", ephemeral=True)
            return
        
        await ctx.defer()
        
        import json
        from pathlib import Path
        from datetime import datetime
        
        users_dir = Path("memory/users")
        if not users_dir.exists():
            await ctx.send("❌ No user data found.")
            return
        
        # Resolve target user(s)
        target_ids = []
        if username:
            if username.isdigit():
                target_ids = [username]
            else:
                clean = username.lstrip('@').strip().lower()
                for guild in self.bot.guilds:
                    for member in guild.members:
                        if (member.name.lower() == clean or
                            member.display_name.lower() == clean or
                            (hasattr(member, 'global_name') and member.global_name and
                             member.global_name.lower() == clean)):
                            target_ids = [str(member.id)]
                            break
                    if target_ids:
                        break
                
                if not target_ids:
                    for guild in self.bot.guilds:
                        try:
                            members = await guild.query_members(query=clean, limit=5)
                            for m in members:
                                if (m.name.lower() == clean or
                                    m.display_name.lower() == clean):
                                    target_ids = [str(m.id)]
                                    break
                        except Exception:
                            pass
                        if target_ids:
                            break
                
                if not target_ids:
                    await ctx.send(f"❌ Could not find user: `{username}`")
                    return
        else:
            target_ids = [d.name for d in users_dir.iterdir() 
                         if d.is_dir() and d.name.isdigit()]
        
        # Gather context data
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor(self.bot)
        
        reports = []
        for uid in target_ids:
            user_dir = users_dir / uid
            if not user_dir.exists():
                continue
            
            display_name = f"User {uid}"
            try:
                user_obj = await self.bot.fetch_user(int(uid))
                display_name = f"{user_obj.display_name} ({user_obj.name})"
            except Exception:
                pass
            
            try:
                tier = flux.get_tier(int(uid))
            except Exception:
                tier = 0
            
            dm_context = []
            public_context = []
            
            private_file = user_dir / "context_private.jsonl"
            public_file = user_dir / "context_public.jsonl"
            
            if private_file.exists():
                try:
                    lines = private_file.read_text(encoding="utf-8").strip().split("\n")
                    for line in lines[-50:]:
                        try:
                            dm_context.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                except Exception as e:
                    logger.warning(f"Failed to read DM context for {uid}: {e}")
            
            if public_file.exists():
                try:
                    lines = public_file.read_text(encoding="utf-8").strip().split("\n")
                    for line in lines[-30:]:
                        try:
                            public_context.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                except Exception as e:
                    logger.warning(f"Failed to read public context for {uid}: {e}")
            
            usage_file = user_dir / "usage.json"
            usage_data = {}
            if usage_file.exists():
                try:
                    usage_data = json.loads(usage_file.read_text())
                except Exception:
                    pass
            
            media_count = 0
            media_dir = user_dir / "media"
            if media_dir.exists():
                media_count = sum(1 for _ in media_dir.rglob("*") if _.is_file())
            
            report_entry = {
                "user_id": uid,
                "display_name": display_name,
                "tier": tier,
                "dm_message_count": len(dm_context),
                "public_message_count": len(public_context),
                "media_files": media_count,
                "usage": usage_data,
                "dm_conversations": dm_context,
                "public_conversations": public_context,
            }
            reports.append(report_entry)
        
        if not reports:
            await ctx.send("❌ No user data found for the specified target(s).")
            return
        
        report_data = json.dumps(reports, indent=2, default=str)
        
        if len(report_data) > 80000:
            report_data = report_data[:80000] + "\n... [truncated]"
        
        if username:
            prompt = f"""Analyze this user's complete interaction data and generate a detailed admin report.

Include:
- User overview (name, ID, tier, activity level)
- DM conversation themes and topics discussed
- Engagement patterns (frequency, depth of conversations)
- Any notable requests, concerns, or feedback they've shared
- Media generation usage
- Overall relationship/engagement assessment
- Any flags or concerns worth noting

USER DATA:
{report_data}"""
        else:
            prompt = f"""Generate an admin overview report for all users.

Include:
- Total user count and tier breakdown
- Most active users (by message count)
- Users with DM conversations vs public-only
- Key themes across user conversations
- Media generation usage summary
- Users with notable activity or concerns
- Overall community health assessment

USER DATA:
{report_data}"""
        
        try:
            import datetime as dt
            
            engine = self.bot.engine_manager.get_active_engine()
            chat_cog = self.bot.get_cog("ChatListener")
            
            if not engine or not chat_cog:
                await ctx.send("⚠️ Engine unavailable — sending raw data.")
                for i in range(0, len(report_data), 1900):
                    await ctx.send(f"```json\n{report_data[i:i+1900]}\n```")
                return
            
            system_context = chat_cog.prompt_manager.get_system_prompt(
                timestamp=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                scope="CORE",
                user_id="CORE",
                user_name="Admin",
                active_engine=engine.__class__.__name__,
                active_goals="INTENT: admin_report | COMPLEXITY: HIGH",
                working_memory_summary="Generating admin user report",
                is_core=True
            )
            
            system_context += """

[ADMIN REPORT MODE]
You are generating a confidential admin report. Be thorough, analytical, and objective.
Use markdown formatting. Include specific quotes from conversations where relevant.
Do NOT editorialize or add emotional commentary — be factual and precise.
This report is for the system administrator's eyes only.
[END REPORT MODE]"""
            
            cognition = self.bot.cognition
            if not cognition:
                from src.engines.cognition import CognitionEngine
                self.bot.cognition = CognitionEngine(self.bot)
                cognition = self.bot.cognition
            
            final_response, files, *_ = await cognition.process(
                input_text=prompt,
                context="Admin report generation — analyze user data comprehensively.",
                system_context=system_context,
                images=[],
                complexity="HIGH",
                request_scope="CORE",
                user_id="CORE",
                skip_defenses=True
            )
            
            if not final_response:
                await ctx.send("❌ Report generation failed — empty response.")
                return
            
            header = f"📊 **ADMIN REPORT** — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            if username:
                header += f"Target: **{reports[0]['display_name']}** (ID: {reports[0]['user_id']})\n"
            else:
                header += f"Scope: **All Users** ({len(reports)} total)\n"
            header += "---\n"
            
            full_report = header + final_response
            
            if len(full_report) > 2000:
                chunks = [full_report[i:i+1990] for i in range(0, len(full_report), 1990)]
                for chunk in chunks:
                    await ctx.send(chunk)
            else:
                await ctx.send(full_report)
            
            logger.info(f"Admin report generated: {len(reports)} users, {len(final_response)} chars")
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            await ctx.send(f"❌ Report failed: {e}")


async def setup(bot):
    await bot.add_cog(AdminReports(bot))
