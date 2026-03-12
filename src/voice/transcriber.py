import logging
import asyncio
import speech_recognition as sr

logger = logging.getLogger("Voice.Transcriber")

class AudioTranscriber:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        logger.info("AudioTranscriber initialized.")

    async def transcribe(self, audio_path: str) -> str:
        """
        Transcribes audio file to text.
        """
        if not audio_path:
            return ""
            
        logger.info(f"Transcribing {audio_path}...")
        
        try:
            # Correct usage for AudioFile
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)
            
            # Use Google Web Speech API (Free, default)
            # Run in executor to prevent blocking
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self.recognizer.recognize_google, audio)
            return text
            
        except sr.UnknownValueError:
            return "[Audio Unintelligible]"
        except sr.RequestError as e:
            return f"[Transcription Service Error: {e}]"
        except Exception as e:
            logger.error(f"Transcription Failed: {e}")
            return f"[Transcription Failed: {e}]"
