"""
ModelRouter — Routes sub-tasks to optimal models based on task type.

Enables Ernos to use the right model for each job:
- Fast models for simple lookups
- Specialized models for code
- Strong models for reasoning
- Creative models for generation
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("Agents.Router")


@dataclass
class ModelProfile:
    """Profile describing a model's capabilities."""
    name: str
    model_id: str
    strengths: list[str]
    speed: str = "medium"  # fast, medium, slow
    cost: str = "medium"   # low, medium, high
    context_window: int = 8192
    supports_tools: bool = True


class ModelRouter:
    """
    Routes tasks to the optimal model based on task characteristics.
    Supports dynamic model registration and capability matching.
    """

    _models: dict[str, ModelProfile] = {}
    _routing_rules: dict[str, str] = {}
    _default_model: Optional[str] = None

    # Task type classification keywords
    TASK_SIGNATURES = {
        "web_search": ["search", "find", "lookup", "google", "browse", "news"],
        "code_generation": ["code", "implement", "program", "function", "class", "debug", "fix bug"],
        "code_review": ["review", "audit", "analyze code", "refactor"],
        "deep_reasoning": ["reason", "think", "analyze", "compare", "evaluate", "philosophy"],
        "creative_writing": ["write", "story", "poem", "creative", "imagine", "generate text"],
        "summarization": ["summarize", "tldr", "brief", "overview", "recap"],
        "translation": ["translate", "convert language"],
        "math_science": ["calculate", "math", "equation", "physics", "chemistry", "statistics"],
        "data_analysis": ["data", "analyze dataset", "chart", "graph", "csv"],
        "image_generation": ["image", "picture", "draw", "visualize", "art"],
        "fact_checking": ["verify", "fact check", "confirm", "true or false", "is it true"],
        "planning": ["plan", "strategy", "roadmap", "steps", "how to"],
        "conversation": ["chat", "talk", "discuss", "opinion"],
    }

    @classmethod
    def register_model(cls, profile: ModelProfile):
        """Register a model with its capability profile."""
        cls._models[profile.name] = profile
        logger.info(f"Registered model: {profile.name} ({profile.model_id})")

    @classmethod
    def set_routing_rule(cls, task_type: str, model_name: str):
        """Set explicit routing: task_type -> model_name."""
        cls._routing_rules[task_type] = model_name

    @classmethod
    def set_default(cls, model_name: str):
        """Set the default model for unmatched tasks."""
        cls._default_model = model_name

    @classmethod
    def route(cls, task: str, complexity: int = 5,
              prefer_speed: bool = False) -> Optional[str]:
        """
        Route a task to the optimal model.

        Args:
            task: The task description
            complexity: 1-10 estimated complexity
            prefer_speed: If True, prefer faster models

        Returns:
            Model name or None for default
        """
        task_type = cls.classify_task(task)

        # Check explicit routing rules first
        if task_type in cls._routing_rules:
            model_name = cls._routing_rules[task_type]
            if model_name in cls._models:
                return model_name

        # Auto-route based on complexity and speed preference
        if prefer_speed or complexity <= 3:
            candidates = [m for m in cls._models.values() if m.speed == "fast"]
            if candidates:
                return candidates[0].name

        if complexity >= 8:
            candidates = [m for m in cls._models.values() if m.speed == "slow"]
            if candidates:
                return candidates[0].name

        # Match by task type strengths
        for name, profile in cls._models.items():
            if task_type in profile.strengths:
                return name

        return cls._default_model

    @classmethod
    def classify_task(cls, task: str) -> str:
        """Classify a task into a type based on keyword matching."""
        task_lower = task.lower()
        scores = {}

        for task_type, keywords in cls.TASK_SIGNATURES.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > 0:
                scores[task_type] = score

        if scores:
            return max(scores, key=scores.get)

        return "general"

    @classmethod
    def get_model_for_engine(cls, model_name: str, bot=None):
        """
        Get the actual engine instance for a model name.
        Falls back to active engine if model not found.
        """
        if not bot:
            return None

        profile = cls._models.get(model_name)
        if not profile:
            return bot.engine_manager.get_active_engine()

        # Try to get the specific engine
        engine_manager = bot.engine_manager
        engine = engine_manager.get_engine(profile.model_id)
        if engine:
            return engine

        return engine_manager.get_active_engine()

    @classmethod
    def get_routing_table(cls) -> dict:
        """Get the current routing configuration."""
        return {
            "models": {
                name: {
                    "model_id": p.model_id,
                    "speed": p.speed,
                    "cost": p.cost,
                    "strengths": p.strengths,
                    "context_window": p.context_window,
                }
                for name, p in cls._models.items()
            },
            "rules": dict(cls._routing_rules),
            "default": cls._default_model,
        }

    @classmethod
    def auto_configure(cls, bot=None):
        """
        Auto-configure routing based on available engines.
        Called at startup to detect what models are available.
        """
        # Register common Ollama models with their profiles
        common_profiles = [
            ModelProfile(
                name="gemma3", model_id="gemma3:27b",
                strengths=["conversation", "summarization", "creative_writing"],
                speed="medium", cost="low", context_window=128000
            ),
            ModelProfile(
                name="qwen-coder", model_id="qwen2.5-coder:32b",
                strengths=["code_generation", "code_review", "math_science"],
                speed="medium", cost="low", context_window=32768
            ),
            ModelProfile(
                name="deepseek-r1", model_id="deepseek-r1:32b",
                strengths=["deep_reasoning", "math_science", "planning"],
                speed="slow", cost="low", context_window=32768
            ),
            ModelProfile(
                name="gemini-flash", model_id="gemini-2.0-flash",
                strengths=["web_search", "summarization", "fact_checking"],
                speed="fast", cost="low", context_window=1000000
            ),
            ModelProfile(
                name="gemini-pro", model_id="gemini-2.5-pro",
                strengths=["deep_reasoning", "creative_writing", "planning", "code_generation"],
                speed="medium", cost="high", context_window=1000000
            ),
            ModelProfile(
                name="llama-guard", model_id="llama-guard3:8b",
                strengths=["fact_checking", "moderation"],
                speed="fast", cost="low", context_window=8192
            ),
        ]

        for profile in common_profiles:
            cls.register_model(profile)

        # Set default routing rules
        cls.set_routing_rule("web_search", "gemini-flash")
        cls.set_routing_rule("code_generation", "qwen-coder")
        cls.set_routing_rule("deep_reasoning", "deepseek-r1")
        cls.set_routing_rule("creative_writing", "gemini-pro")
        cls.set_routing_rule("fact_checking", "gemini-flash")
        cls.set_routing_rule("planning", "gemini-pro")
        cls.set_routing_rule("summarization", "gemini-flash")

        cls.set_default("gemma3")
        logger.info(f"Auto-configured {len(cls._models)} models with {len(cls._routing_rules)} routing rules")
