import discord
import logging
import asyncio
from typing import Dict, Set

logger = logging.getLogger('SiloManager')

class SiloManager:
    '''
    Manages Silos - Private threads within public channels.
    Strictly follows §14.3: Triggered by Bot + 2 or more Humans (excluding bot).
    '''
    def __init__(self, bot):
        self.bot = bot
        self.pending_silos: Dict[int, Set[int]] = {}
        self.active_silos: Set[int] = set()
        self.manual_consents: Dict[int, Set[int]] = {}

    async def propose_silo(self, message: discord.Message):
        # Unique human participants: Author + any mentioned humans who aren't bots.
        human_participants = {message.author.id}
        human_mentions = {u.id for u in message.mentions if u.id != self.bot.user.id}
        human_participants.update(human_mentions)

        bot_mentioned = any(u.id == self.bot.user.id for u in message.mentions)

        # §14.3 Requirement: Bot + 2 or more Humans.
        if not bot_mentioned or len(human_participants) < 2:
            return

        try:
            reaction_msg = await message.reply(
                '🛡️ **Silo Protocol Initiated**\n'
                'Secure group context proposed. React with ✅ to enter the Silo.'
            )
            await reaction_msg.add_reaction('✅')
            self.pending_silos[reaction_msg.id] = human_participants
            self.bot.loop.create_task(self._expire_proposal(reaction_msg.id))
        except Exception as e:
            logger.error(f'Failed to propose Silo: {e}')

    async def check_quorum(self, payload: discord.RawReactionActionEvent):
        '''Verifies if all required participants have reacted with ✅.'''
        if str(payload.emoji) != '✅' or payload.message_id not in self.pending_silos:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            msg = await channel.fetch_message(payload.message_id)
            reaction = discord.utils.get(msg.reactions, emoji='✅')
            if not reaction:
                return

            users = [u async for u in reaction.users()]
            user_ids = {u.id for u in users}
            required_ids = self.pending_silos[payload.message_id]

            if required_ids.issubset(user_ids):
                await self.activate_silo(msg, required_ids)
                self.pending_silos.pop(payload.message_id, None)
        except Exception as e:
            logger.error(f'Error checking Silo quorum: {e}')

    async def activate_silo(self, message: discord.Message, participants: Set[int]):
        '''Creates the private thread and registers it as an active Silo.'''
        try:
            thread = await message.channel.create_thread(name='🛡️ Secure Silo Context')
            self.active_silos.add(thread.id)
            # Add each participant (skip bot)
            for uid in participants:
                if uid != self.bot.user.id:
                    try:
                        user = await self.bot.fetch_user(uid)
                        await thread.add_user(user)
                    except Exception:
                        pass
            await thread.send(
                f'Silo established. Participants: <@' +
                '>, <@'.join(str(uid) for uid in participants if uid != self.bot.user.id) +
                '>.'
            )
        except Exception as e:
            logger.error(f'Failed to activate Silo: {e}')

    async def check_text_confirmation(self, message: discord.Message) -> bool:
        '''
        Check if a message is a text-based confirmation for a pending silo proposal.
        Returns True if the message was a silo confirmation (caller should stop processing).
        '''
        if not self.pending_silos:
            return False

        content_lower = message.content.strip().lower()
        if content_lower not in ('yes', 'confirm', '✅', 'join', 'accept', 'ok'):
            return False

        # If message is a direct reply to a proposal
        if message.reference and message.reference.message_id in self.pending_silos:
            msg_id = message.reference.message_id
            required_ids = self.pending_silos[msg_id]
            if message.author.id in required_ids:
                # Track manual consent
                if msg_id not in self.manual_consents:
                    self.manual_consents[msg_id] = set()
                self.manual_consents[msg_id].add(message.author.id)
                try:
                    await message.add_reaction('✅')
                    proposal_msg = await message.channel.fetch_message(msg_id)
                    await self._check_consensus(proposal_msg, required_ids)
                except Exception as e:
                    logger.error(f'Error processing text confirmation: {e}')
                return True
            return False

        # No reference — iterate through pending proposals
        for msg_id, required_ids in list(self.pending_silos.items()):
            if message.author.id in required_ids:
                if msg_id not in self.manual_consents:
                    self.manual_consents[msg_id] = set()
                self.manual_consents[msg_id].add(message.author.id)
                try:
                    await message.add_reaction('✅')
                    proposal_msg = await message.channel.fetch_message(msg_id)
                    await self._check_consensus(proposal_msg, required_ids)
                except Exception as e:
                    logger.error(f'Error processing text confirmation: {e}')
                return True

        return False

    async def _check_consensus(self, message: discord.Message, required_ids: Set[int]):
        '''Check combined reactions + manual consents to see if quorum is reached.'''
        confirmed = set()
        msg_id = message.id

        # Gather reaction confirmations
        reaction = discord.utils.get(message.reactions, emoji='✅')
        if reaction:
            users = [u async for u in reaction.users()]
            confirmed.update(u.id for u in users)

        # Add manual text consents
        confirmed.update(self.manual_consents.get(msg_id, set()))

        if required_ids.issubset(confirmed):
            await self.activate_silo(message, required_ids)
            self.pending_silos.pop(msg_id, None)
            self.manual_consents.pop(msg_id, None)

    async def should_bot_reply(self, message: discord.Message) -> bool:
        '''Turn-taking logic: Bot only replies if it is in a Silo and all humans have spoken.'''
        if message.channel.id not in self.active_silos:
            return True  # Normal behavior outside silos

        # If bot is directly mentioned, always reply
        if any(u.id == self.bot.user.id for u in message.mentions):
            return True

        try:
            thread = message.channel
            members = await thread.fetch_members()
            human_ids = {m.id for m in members if m.id != self.bot.user.id}

            # Check recent history for speaker coverage
            recent_speakers = set()
            async for msg in thread.history(limit=20):
                recent_speakers.add(msg.author.id)

            # Bot replies only if all human members have contributed
            return human_ids.issubset(recent_speakers)
        except Exception as e:
            logger.error(f'Error in Silo turn-taking logic: {e}')
            return True

    async def check_empty_silo(self, thread: discord.Thread):
        '''Deletes the Silo thread if no humans remain.'''
        if thread.id not in self.active_silos:
            return

        if thread.member_count is not None and thread.member_count <= 1:
            self.active_silos.discard(thread.id)
            try:
                await thread.delete()
            except Exception:
                pass

    async def _expire_proposal(self, msg_id: int):
        '''Cleanup for unconfirmed proposals.'''
        await asyncio.sleep(300)
        self.pending_silos.pop(msg_id, None)
        self.manual_consents.pop(msg_id, None)
