"""
Discord Channel Adapter — Converts discord.py types to/from UnifiedMessage.
Extracted from ChatCog to decouple the cognitive pipeline from Discord.
"""
import logging
import os
import re
from typing import Any

import discord

from src.channels.base import ChannelAdapter
from src.channels.types import Attachment, OutboundResponse, UnifiedMessage

logger = logging.getLogger("Channels.Discord")


class DiscordChannelAdapter(ChannelAdapter):
    """
    Concrete adapter for Discord via discord.py.
    
    Handles all Discord-specific message conversion, chunking,
    file attachment, and mention formatting.
    """

    def __init__(self, bot):
        self.bot = bot

    @property
    def platform_name(self) -> str:
        return "discord"

    async def normalize(self, raw_message: discord.Message) -> UnifiedMessage:
        """
        Convert a discord.Message into a UnifiedMessage.
        
        Extracts author info, channel type, and normalizes attachments
        into platform-agnostic Attachment objects.
        """
        # Determine DM status (DM, private threads, or guildless)
        is_dm = (
            isinstance(raw_message.channel, discord.DMChannel)
            or (
                isinstance(raw_message.channel, discord.Thread)
                and raw_message.channel.type == discord.ChannelType.private_thread
            )
            or (str(raw_message.channel.type) == "private")
            or (not raw_message.guild)
        )

        # Normalize attachments
        attachments = []
        for att in raw_message.attachments:
            attachments.append(
                Attachment(
                    filename=att.filename,
                    content_type=att.content_type or "application/octet-stream",
                    size=att.size,
                    url=att.url,
                    data=None,  # Lazy — fetched on demand via fetch_attachment_data
                )
            )

        return UnifiedMessage(
            content=raw_message.content,
            author_id=str(raw_message.author.id),
            author_name=raw_message.author.display_name or raw_message.author.name,
            channel_id=str(raw_message.channel.id),
            is_dm=is_dm,
            is_bot=raw_message.author.bot,
            attachments=attachments,
            reply_to=str(raw_message.reference.message_id) if raw_message.reference else None,
            platform="discord",
            raw=raw_message,
        )

    async def send_response(
        self, response: OutboundResponse, channel_ref: discord.Message
    ) -> None:
        """
        Send an OutboundResponse as a Discord reply.
        
        Handles:
        - 2000-char chunking
        - discord.File wrapping
        - Reply threading
        - Optional view attachment (passed via channel_ref metadata)
        """
        text = await self.format_mentions(response.content)

        # Prepare files
        discord_files = []
        for fpath in response.files:
            if os.path.exists(fpath):
                try:
                    discord_files.append(discord.File(str(fpath)))
                except Exception as e:
                    logger.error(f"Failed to attach {fpath}: {e}")

        # Add reactions
        for emoji in response.reactions:
            try:
                await channel_ref.add_reaction(emoji)
            except Exception as e:
                logger.warning(f"Failed to add reaction {emoji}: {e}")

        # Chunk and send
        if len(text) > 2000:
            chunks = [text[i : i + 2000] for i in range(0, len(text), 2000)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await channel_ref.reply(chunk, files=discord_files)
                else:
                    await channel_ref.reply(chunk)
        else:
            await channel_ref.reply(text, files=discord_files)

    async def add_reaction(self, message_ref: discord.Message, emoji: str) -> None:
        """Add an emoji reaction to a Discord message."""
        try:
            await message_ref.add_reaction(emoji)
        except Exception as e:
            logger.warning(f"Failed to add reaction {emoji}: {e}")

    async def fetch_attachment_data(self, attachment: Attachment) -> bytes:
        """
        Download attachment content from Discord CDN.
        
        Uses the raw discord.Attachment.read() if available on the
        original message, otherwise falls back to URL fetch.
        """
        if attachment.data is not None:
            return attachment.data

        # Discord attachments can be read directly via the discord.py API
        # but we only have our normalized Attachment here.
        # The caller should use the raw message's attachment.read() instead.
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    return await resp.read()
                raise RuntimeError(
                    f"Failed to download attachment {attachment.filename}: HTTP {resp.status}"
                )

    async def format_mentions(self, text: str) -> str:
        """
        Convert bare @userID mentions to Discord's <@userID> format.
        
        The LLM outputs @764896542170939443 but Discord needs <@764896542170939443>
        to render as a clickable user mention. Uses negative lookbehind to avoid
        double-wrapping mentions already in <@...> format.
        """
        return re.sub(r"(?<!<)@(\d{17,20})", r"<@\1>", text)
