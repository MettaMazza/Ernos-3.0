from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("Engine")

class BaseEngine(ABC):
    """Abstract base class for all inference engines."""
    
    @abstractmethod
    def generate_response(self, prompt: str, context: any = None, system_prompt: str = None, images: list[bytes] = None) -> str:
        """
        Generate a response based on the prompt.
        
        Args:
            prompt (str): User input.
            context (any, optional): Additional context (e.g. conversation history).
            system_prompt (str, optional): The system prompt/instructions.
            images (list[bytes], optional): List of image bytes for multimodal models.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def context_limit(self) -> int:
        """Returns the character limit for the context window."""
        pass

class EngineManager:
    """Manages the active model engine (Singleton-ish)."""
    
    def __init__(self):
        self._current_engine: BaseEngine = None
        self._engines: dict[str, BaseEngine] = {}

    def register_engine(self, name: str, engine: BaseEngine):
        self._engines[name] = engine
        if not self._current_engine:
            self._current_engine = engine

    def set_active_engine(self, name: str) -> bool:
        if name in self._engines:
            self._current_engine = self._engines[name]
            logger.info(f"Switched engine to: {name}")
            return True
        logger.warning(f"Engine {name} not found.")
        return False

    def get_active_engine(self) -> BaseEngine:
        return self._current_engine
