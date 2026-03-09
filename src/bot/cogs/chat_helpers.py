"""
Chat Helpers - Attachment processing and reaction handling.
Extracted from ChatListener for modularity.
"""
import io
import logging
from typing import Optional

logger = logging.getLogger("ChatCog.Helpers")


class AttachmentProcessor:
    """Handles text extraction from various document formats."""
    
    @staticmethod
    async def extract_text(attachment) -> str:
        """Extract text from various document formats."""
        filename = attachment.filename.lower()
        file_bytes = await attachment.read()
        file_stream = io.BytesIO(file_bytes)
        
        text = ""
        
        # PDF Handling — pdfplumber primary (handles malformed PDFs), pypdf fallback
        if filename.endswith(".pdf"):
            # Try pdfplumber first (robust against malformed cross-references)
            try:
                import pdfplumber
                with pdfplumber.open(file_stream) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                if text.strip():
                    return text
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"pdfplumber extraction failed, trying pypdf fallback: {e}")
            
            # Fallback to pypdf
            file_stream.seek(0)
            try:
                import pypdf
                reader = pypdf.PdfReader(file_stream)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            except ImportError:
                return "[Error: No PDF library installed (need pdfplumber or pypdf)]"
            except Exception as e:
                return f"[Error parsing PDF: {e}]"
        
        # DOCX Handling
        elif filename.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(file_stream)
                text = "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                return "[Error: python-docx not installed]"
            except Exception as e:
                return f"[Error parsing DOCX: {e}]"
                
        # Plain Text & Code Handling
        else:
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = file_bytes.decode("latin-1")
                except Exception:
                    return "[Error: Unknown text encoding]"
                    
        return text


class ReactionHandler:
    """Handles reaction events and social signal processing."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process_reaction(self, payload):
        """Check for Silo Quorum and Ingest Social Signals."""
        if payload.user_id == self.bot.user.id:
            return
            
        # 1. Silo Quorum
        await self.bot.silo_manager.check_quorum(payload)
        
        # 2. Social Signal Ingestion (MRN Phase 3)
        try:
            # Check safely if cerebrum is loaded
            if hasattr(self.bot, 'cerebrum'):
                interaction_lobe = self.bot.cerebrum.lobes.get("InteractionLobe")
                if interaction_lobe:
                    social = interaction_lobe.get_ability("SocialAbility")
                    if social:
                        # Process Sentiment & Update Stats
                        sentiment = await social.process_reaction(
                            payload.user_id, 
                            str(payload.emoji), 
                            payload.message_id
                        )
                        
                        # Log to Memory (Timeline)
                        is_dm = (payload.guild_id is None)
                        if hasattr(self.bot, 'hippocampus'):
                            self.bot.hippocampus.observe_reaction(
                                user_id=str(payload.user_id),
                                emoji=str(payload.emoji),
                                sentiment=sentiment,
                                message_id=payload.message_id,
                                channel_id=payload.channel_id,
                                is_dm=is_dm
                            )
        except Exception as e:
            logger.error(f"Failed to process reaction signal: {e}")
