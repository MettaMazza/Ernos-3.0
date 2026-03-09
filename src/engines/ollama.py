from .base import BaseEngine
import ollama
import logging

logger = logging.getLogger("OllamaEngine")

class OllamaEngine(BaseEngine):
    def __init__(self, model_name: str, base_url: str = None):
        self._model = model_name
        self._client = ollama.Client(host=base_url) if base_url else ollama.Client()

    @property
    def context_limit(self) -> int:
        from config import settings
        if self._model == settings.OLLAMA_CLOUD_MODEL:
            return settings.CONTEXT_CHAR_LIMIT_CLOUD
        return settings.CONTEXT_CHAR_LIMIT_LOCAL

    @property
    def _num_predict(self) -> int:
        """Max output tokens. Higher for cloud models, conservative for local."""
        from config import settings
        if self._model == settings.OLLAMA_CLOUD_MODEL:
            return getattr(settings, 'OUTPUT_TOKEN_LIMIT_CLOUD', 32768)
        return getattr(settings, 'OUTPUT_TOKEN_LIMIT_LOCAL', 8192)

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    def generate_response(self, prompt: str, context: any = None, system_prompt: str = None, images: list[bytes] = None) -> str:
        logger.info(f"Generating with Ollama model: {self._model} (Images: {len(images) if images else 0})")
        try:
            # Pass system prompt if available
            response = self._client.generate(
                model=self._model, 
                prompt=prompt,
                system=system_prompt,  # Added system prompt support
                images=images, # Multimodal support
                options={
                    "num_predict": self._num_predict,
                }
            )
            return response['response']
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return "Ollama engine failure."
