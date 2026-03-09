import discord
import logging
import asyncio
from typing import Dict, Set

logger = logging.getLogger("SiloManager")

class SiloManager:
    """
    Manages 'Silos' - Private threads within public channels.
    Protocol:
    1. User mentions bot + friend.
    2. Bot confirms request.
    3. User/Friend reacts '✅'.
    4. Bot creates Private Thread and adds mentions.
    """
    def __init__(self, bot):
        self.bot = bot
        self.pending_silos: Dict[int, Set[int]] = {} # msg_id -> set(user_ids_required)
        self.active_silos: Set[int] = set() # thread_ids

    async def propose_silo(self, message: discord.Message):
        """
        Check if message is a valid Silo request.
        Request = Mention bot + others + "silo" or implicit?
        Let's go with implicit: Mentions bot + at least 1 other user.
        """
        if len(message.mentions) < 2: # Bot + 1 User
            return

        # Check if bot is mentioned
        if self.bot.user not in message.mentions:
            return
            
        # Propose
        try:
            reaction_msg = await message.reply(
                "🛡️ **Silo Protocol Initiated**\n"
                "Secure channel proposed. React with ✅ to enter the Silo."
            )
            await reaction_msg.add_reaction("✅")
            
            # Store pending state
            # We want consensus from mentioned users
            required_users = {u.id for u in message.mentions if u != self.bot.user}
            required_users.add(message.author.id)
            
            self.pending_silos[reaction_msg.id] = required_users
            
            # Auto-expire after 5 mins
            self.bot.loop.create_task(self._expire_proposal(reaction_msg.id))
            
        except Exception as e:
            logger.error(f"Failed to propose Silo: {e}")

    async def check_quorum(self, payload: discord.RawReactionActionEvent):
        """
        Check if ALL required users have reacted to activate.
        """
        if payload.message_id not in self.pending_silos:
            return
            
        if str(payload.emoji) != "✅":
            return
            
        required_users = self.pending_silos[payload.message_id]
        
        # We need to check WHO has consented.
        # We can't rely just on reaction count anymore.
        
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        # Get all users who reacted
        reaction = discord.utils.get(message.reactions, emoji="✅")
        consented_users = set()
        
        if reaction:
            async for user in reaction.users():
                consented_users.add(user.id)
                
        # Merge with manually tracked text confirmations (if any)
        # For now, let's just rely on reactions. Text confirmations will ADD a reaction.
        
        # Check strict subset
        # Is required_users a subset of consented_users?
        # i.e. Has EVERY required user consented?
        
        if required_users.issubset(consented_users):
             logger.info(f"Silo Quorum Reached for {payload.message_id}")
             await self.activate_silo(message, required_users)
             del self.pending_silos[payload.message_id]
        else:
             missing = required_users - consented_users
             logger.info(f"Silo Pending Consent: Missing {missing}")

    async def check_text_confirmation(self, message: discord.Message) -> bool:
        """
        Check if a text message is a confirmation. If so, ADD A REACTION to the proposal.
        This unifies the logic in check_quorum.
        """
        content = message.content.strip().lower()
        valid_confirmations = ["✅", "yes", "confirm", "accept", "ok", "sure", "👍"]
        
        if content not in valid_confirmations:
            return False
            
        # Find pending proposal
        target_proposal_id = None
        proposal_msg = None
        
        if message.reference:
            target_proposal_id = message.reference.message_id
            if target_proposal_id in self.pending_silos:
                proposal_msg = await message.channel.fetch_message(target_proposal_id)
        
        if not proposal_msg:
             # Iterate pending
             for pid, users in self.pending_silos.items():
                 if message.author.id in users:
                     try:
                         m = await message.channel.fetch_message(pid)
                         if m:
                             proposal_msg = m
                             target_proposal_id = pid
                             break
                     except Exception:
                         continue

        if proposal_msg and target_proposal_id:
             # Track text-based consent confirmations (complements reaction-based consent)
             if not hasattr(self, 'manual_consents'):
                 self.manual_consents = {} # msg_id -> set(user_ids)
                 
             if target_proposal_id not in self.manual_consents:
                 self.manual_consents[target_proposal_id] = set()
                 
             self.manual_consents[target_proposal_id].add(message.author.id)
             await message.add_reaction("✅") # Ack
             
             # Trigger check logic manually
             # We can construct a fake payload or extract logic.
             # Let's extract logic to _check_consensus(msg, required)
             
             await self._check_consensus(proposal_msg, self.pending_silos[target_proposal_id])
             return True
             
        return False

    async def _check_consensus(self, message, required_users):
        """Helper to check consensus combining reactions + manual text."""
        # 1. Reactions
        consented_users = set()
        reaction = discord.utils.get(message.reactions, emoji="✅")
        if reaction:
            async for user in reaction.users():
                consented_users.add(user.id)
                
        # 2. Text Consents
        if hasattr(self, 'manual_consents') and message.id in self.manual_consents:
            consented_users.update(self.manual_consents[message.id])
            
        # 3. Check
        if required_users.issubset(consented_users):
             logger.info(f"Silo Quorum Reached for {message.id}")
             await self.activate_silo(message, required_users)
             
             # Cleanup
             del self.pending_silos[message.id]
             if hasattr(self, 'manual_consents'):
                 self.manual_consents.pop(message.id, None)
        else:
             missing = required_users - consented_users
             logger.info(f"Silo Waiting: Missing {missing}")

    async def activate_silo(self, origin_message: discord.Message, participants: Set[int]):
        """Create the private thread and add members."""
        try:
            # Use channel.create_thread for Private Threads (GUILD_PRIVATE_THREAD)
            thread = await origin_message.channel.create_thread(
                name=f"Silo-{origin_message.id}",
                auto_archive_duration=60,
                type=discord.ChannelType.private_thread
            )
            
            # Add members
            # CRITICAL: Only add validated participants (Strict Consent)
            # The 'participants' arg contains the set of user IDs who have consented.
            
            # 1. Add Consented Users
            for uid in participants:
                 if uid == self.bot.user.id:
                     continue
                 try:
                     await thread.add_user(discord.Object(id=uid))
                 except Exception as e:
                     logger.warning(f"Failed to add user {uid} to Silo: {e}")

            # 2. Add Author (Implicitly consented by proposing)
            if origin_message.author.id not in participants:
                 await thread.add_user(origin_message.author)
            
            await thread.send("🔒 **Silo Active**. Context is isolated. Use `/leave` or just leave the thread to exit. Thread deletes when empty.")
            self.active_silos.add(thread.id)
            logger.info(f"Silo created: {thread.id}")
            
        except Exception as e:
            logger.error(f"Silo Activation Failed: {e}")

    async def check_empty_silo(self, thread: discord.Thread):
        """Delete thread if empty (only bot remains)."""
        try:
            # member_count includes Bot. So <= 1 means empty of humans.
            if thread.member_count <= 1:
                logger.info(f"Silo {thread.id} is empty. Deleting.")
                await thread.delete()
                self.active_silos.discard(thread.id)
        except Exception as e:
            logger.error(f"Failed to check/delete Silo {thread.id}: {e}")

    async def should_bot_reply(self, message: discord.Message) -> bool:
        """
        Round Robin Turn Taking Logic.
        Bot replies ONLY if all other human participants have spoken since the last bot message.
        """
        # 1. Check if this is an active Silo
        if message.channel.id not in self.active_silos:
            return True # Not a silo, normal rules apply

        try:
            thread = message.channel
            
            # 2. Get Thread Members (Humans)
            members = await thread.fetch_members()
            human_ids = {m.id for m in members if m.id != self.bot.user.id}
            
            if not human_ids:
                return True # Should be handled by empty check, but just in case
                
            # 3. Scan History
            # We want to find the last message by the BOT.
            # Then count distinct human authors after it.
            last_bot_msg = None
            human_speakers_since_bot = set()
            
            # Scan last 20 messages (should be enough covers recent context)
            async for msg in thread.history(limit=20):
                if msg.author.id == self.bot.user.id:
                    # Found bot's last turn
                    break
                
                # It's a human message
                human_speakers_since_bot.add(msg.author.id)
                
            # 4. Check Turn Condition
            # Bot Speaks IF: Set of speakers since last bot msg == Set of human members
            # OR if explicitly mentioned (Override)
            if self.bot.user in message.mentions:
                return True
                
            if human_speakers_since_bot >= human_ids:
                return True
            else:
                logger.info(f"Silo Turn Wait: Speakers={len(human_speakers_since_bot)}/{len(human_ids)} (Missing: {human_ids - human_speakers_since_bot})")
                return False

        except Exception as e:
            logger.error(f"Turn logic failed: {e}")
            return True # Fail open

    async def _expire_proposal(self, msg_id):
        await asyncio.sleep(300)
        self.pending_silos.pop(msg_id, None)
