import discord
import logging

logger = logging.getLogger("UI.Views")

class ResponseFeedbackView(discord.ui.View):
    def __init__(self, bot, response_text: str):
        super().__init__(timeout=None) # Persistent? No, dynamic.
        self.bot = bot
        self.response_text = response_text
        self.audio_msg = None # Track uploaded file message

    @discord.ui.button(emoji="👍", style=discord.ButtonStyle.gray, custom_id="fb_up")
    async def like_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Thanks for the feedback! (Logged: Positive)", ephemeral=True)
        # Log positive RLHF
        self._log_feedback(interaction.user.id, "positive", self.response_text)

    @discord.ui.button(emoji="👎", style=discord.ButtonStyle.gray, custom_id="fb_down")
    async def dislike_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Feedback received. I'll do better. (Logged: Negative)", ephemeral=True)
        # Log negative RLHF
        self._log_feedback(interaction.user.id, "negative", self.response_text)

    def _log_feedback(self, user_id: int, sentiment: str, response_text: str):
        """
        Log RLHF feedback to file for training data collection.
        NOTE: This is a CORE-only system operation.
        RLHF data is system training data, not user-accessible data.
        """
        import json
        from pathlib import Path
        from datetime import datetime
        
        # CORE-only write (RLHF is internal system data)
        feedback_path = Path("memory/core/rlhf_feedback.jsonl")
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": str(user_id),
            "sentiment": sentiment,
            "response": response_text[:500]  # Truncate for storage
        }
        
        try:
            with open(feedback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info(f"RLHF Feedback logged: {sentiment} from {user_id}")
        except Exception as e:
            logger.error(f"Failed to log RLHF feedback: {e}")

    @discord.ui.button(emoji="🗣️", style=discord.ButtonStyle.secondary, custom_id="fb_tts")
    async def tts_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check Voice System
        if not hasattr(self.bot, 'voice_manager') or not self.bot.voice_manager:
             await interaction.response.send_message("❌ Voice System Unavailable (PyNaCl missing).", ephemeral=True)
             return

        # Toggle Logic (remove previous audio if exists)
        if self.audio_msg:
            try:
                await self.audio_msg.delete()
                await interaction.response.send_message("Audio file removed.", ephemeral=True)
            except discord.NotFound:
                logger.debug("Message not found for view update")
            self.audio_msg = None
            return

        await interaction.response.defer(ephemeral=True)
        
        # 1. Get Audio Path
        audio_path = await self.bot.voice_manager.get_audio_path(self.response_text)
        
        # 2. Play in Voice Channel (guild only — DMs have no voice channels)
        if interaction.guild:
            if interaction.user.voice:
                if interaction.guild.id not in self.bot.voice_manager.active_connections:
                    await self.bot.voice_manager.join_channel(interaction.user.voice.channel)
            if interaction.guild.id in self.bot.voice_manager.active_connections:
                await self.bot.voice_manager.speak(interaction.guild.id, self.response_text)
        
        # 3. Upload audio file to chat (works in both DMs and guilds)
        if audio_path:
             self.audio_msg = await interaction.followup.send(
                 content="🎙️ Voice Generation:", 
                 file=discord.File(audio_path, filename="speech.wav"),
                 ephemeral=False
             )
             await interaction.followup.send("Audio uploaded.", ephemeral=True)
        else:
             await interaction.followup.send("❌ Failed to generate audio.", ephemeral=True)
