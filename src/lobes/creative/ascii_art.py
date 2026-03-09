"""
ASCII Art Ability - Creative Lobe

Ported from Ernos 2.0's ASCII Artist Agent.
Generates ASCII diagrams and art with output protection.

Architecture: Uses AI (LLM) for generation, not heuristics.
"""

import logging
from typing import Optional
from ..base import BaseAbility

logger = logging.getLogger("Lobe.Creative.ASCII")


class ASCIIArtAbility(BaseAbility):
    """
    Specialized ability for generating ASCII art and diagrams.
    Wraps output in code blocks to prevent sanitization stripping.
    """
    
    STYLE_GUIDES = {
        "box": "Use box-drawing characters: ┌ ┐ └ ┘ │ ─ ├ ┤ ┬ ┴ ┼",
        "tree": "Use tree structure: ├── └── │",
        "flow": "Use arrows and boxes: → ← ↑ ↓ ◆ ○ □ ▢",
        "simple": "Use basic ASCII only: + - | / \\ * # @ [ ]"
    }
    
    async def execute(self, context=None):
        """Default execution - generate system architecture diagram."""
        return await self.generate_system_map()
    
    async def generate_diagram(self, subject: str, style: str = "box") -> str:
        """
        Generate an ASCII diagram for a given subject.
        
        Args:
            subject: What to diagram (e.g., "Ernos system architecture")
            style: Diagram style - "box", "tree", "flow", "simple"
        
        Returns:
            ASCII diagram wrapped in code block for protection
        """
        guide = self.STYLE_GUIDES.get(style, self.STYLE_GUIDES["simple"])
        
        prompt = f"""Generate an ASCII diagram for: {subject}

STYLE: {style}
CHARACTER GUIDE: {guide}

RULES:
1. Keep it under 40 characters wide for Discord
2. Use consistent spacing
3. Make it readable and accurate
4. Add labels where needed

Output ONLY the diagram, no explanation before or after."""

        try:
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                return self._protect_output("[No inference engine available]")
            
            response = await self.bot.loop.run_in_executor(
                None, 
                lambda: engine.generate_response(prompt, temperature=0.3)
            )
            
            return self._protect_output(response.strip())
            
        except Exception as e:
            logger.error(f"ASCII diagram generation failed: {e}")
            return f"```\n[ASCII Generation Error: {e}]\n```"
    
    async def generate_system_map(self) -> str:
        """
        Generate a diagram of the Ernos 3.0 system architecture.
        Pre-defined accurate representation to avoid hallucination.
        """
        # Pre-built accurate diagram for v3 architecture
        diagram = """
┌─────────────────────────────────────┐
│          ERNOS 3.0 BRAIN            │
├─────────────────────────────────────┤
│  ┌─────────┐    ┌─────────────────┐ │
│  │ KERNEL  │───▶│  SUPEREGO       │ │
│  │(Immut.) │    │ (Enforcement)   │ │
│  └─────────┘    └─────────────────┘ │
├─────────────────────────────────────┤
│         COGNITIVE LOBES             │
│  ┌────────┐ ┌────────┐ ┌────────┐  │
│  │Creative│ │Strategy│ │Interact│  │
│  │ Lobe   │ │  Lobe  │ │  Lobe  │  │
│  └────────┘ └────────┘ └────────┘  │
│  ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ Memory │ │Superego│ │Daemons │  │
│  │  Lobe  │ │  Lobe  │ │(Async) │  │
│  └────────┘ └────────┘ └────────┘  │
├─────────────────────────────────────┤
│          HIPPOCAMPUS                │
│  ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ Neo4j  │ │ Vector │ │ Lessons│  │
│  │ Graph  │ │ Store  │ │  File  │  │
│  └────────┘ └────────┘ └────────┘  │
│  ┌────────┐ ┌────────┐ ┌────────┐  │
│  │Calendar│ │ Goals  │ │Relation│  │
│  │Manager │ │Manager │ │Manager │  │
│  └────────┘ └────────┘ └────────┘  │
└─────────────────────────────────────┘
"""
        return self._protect_output(diagram.strip())
    
    async def generate_art(self, prompt: str) -> str:
        """
        Generate decorative ASCII art.
        Uses AI (LLM) for creative generation.
        """
        art_prompt = f"""Create ASCII art for: {prompt}

RULES:
1. Keep under 30 lines tall
2. Keep under 50 characters wide
3. Use standard ASCII characters
4. Make it visually appealing

Output ONLY the art, no explanation."""

        try:
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                return self._protect_output("[No inference engine available]")
            
            response = await self.bot.loop.run_in_executor(
                None,
                lambda: engine.generate_response(art_prompt, temperature=0.5)
            )
            return self._protect_output(response.strip())
            
        except Exception as e:
            logger.error(f"ASCII art generation failed: {e}")
            return f"```\n[Art Generation Error: {e}]\n```"
    
    def _protect_output(self, content: str) -> str:
        """
        Wrap content in code block to protect from stripping.
        This tells Discord to preserve formatting and tells
        our filters to skip sanitization.
        """
        # Remove any existing code blocks to avoid nesting
        content = content.replace("```", "")
        
        # Wrap in code block
        return f"```\n{content}\n```"
