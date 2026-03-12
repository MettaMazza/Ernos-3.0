from .base import BaseEngine
import ollama
import logging

logger = logging.getLogger("OllamaEngine")


class DormantAPIError(Exception):
    """Raised when the Ollama cloud API returns a 429 rate-limit response.

    Bubbles up through the engine stack to the chat handler,
    which sends a dormancy notification to the user.
    """
    pass


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

    def generate_response(self, prompt: str, context: any = None, system_prompt: str = None, images: list[bytes] = None, strict_prompt: bool = False, caller: str = None) -> str:
        prefix = f"[{caller}] " if caller else ""
        logger.info(f"{prefix}Generating with Ollama model: {self._model} (Images: {len(images) if images else 0})")
        try:
            # Pass system prompt if available
            response = self._client.generate(
                model=self._model,
                prompt=prompt,
                system=system_prompt,  # Added system prompt support
                images=images,         # Multimodal support
                options={
                    "num_predict": self._num_predict,
                }
            )
            # Extract text — handles object/dict and thinking models
            if not isinstance(response, dict):
                result = response.response or getattr(response, 'thinking', '') or ''
            else:
                result = response.get('response') or response.get('thinking', '') or ''

            return result
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate limit" in err_str.lower() or "too many requests" in err_str.lower():
                logger.warning(f"Ollama cloud API rate limit hit (429): {e}")
                raise DormantAPIError("Ollama cloud API rate limit reached.") from e
            logger.error(f"Error calling Ollama: {e}")
            return "Ollama engine failure."
