"""
Perception Module — v3.4 Rhizome.

Unified sensory integration layer. Aggregates inputs from
multiple modalities (text, images, voice, game world) into
a structured perception context for cognitive processing.
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("Lobe.Interaction.Perception")


@dataclass
class PerceptualInput:
    """A single sensory input from any modality."""
    modality: str  # text, image, audio, game_state, sensor
    source: str    # discord, telegram, minecraft, home_assistant
    data: Any      # Raw modality data
    timestamp: str = ""
    confidence: float = 1.0  # How reliable is this input
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class PerceptionContext:
    """
    Aggregated perception context for a single processing cycle.
    
    This is the "what Ernos sees right now" snapshot, combining
    all active sensory streams into a coherent picture.
    """
    inputs: List[PerceptualInput] = field(default_factory=list)
    dominant_modality: str = "text"
    emotional_valence: float = 0.0  # -1 (negative) to 1 (positive)
    attention_focus: str = ""       # What Ernos is currently focused on
    context_summary: str = ""       # Brief narrative of current perception
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class PerceptionEngine:
    """
    Multi-modal perception aggregator.
    
    Collects sensory inputs from various sources and produces
    a unified PerceptionContext that the cognitive architecture
    can use for decision-making.
    
    Input streams:
    - Text messages (Discord, Telegram, Matrix, Web)
    - Image content (attachments, generated images)
    - Audio (voice channel input)
    - Game state (Minecraft world state)
    - Sensor data (Home Assistant)
    
    Output: PerceptionContext
    """
    
    def __init__(self):
        self._input_buffer: List[PerceptualInput] = []
        self._max_buffer = 50
        self._attention_weights = {
            "text": 0.4,
            "image": 0.2,
            "audio": 0.2,
            "game_state": 0.1,
            "sensor": 0.1
        }
    
    def ingest(self, modality: str, source: str, data: Any, 
               confidence: float = 1.0, metadata: Dict = None) -> PerceptualInput:
        """
        Ingest a raw sensory input.
        
        Args:
            modality: Type of input (text, image, audio, game_state, sensor)
            source: Where it came from (discord, minecraft, etc.)
            data: The raw data
            confidence: Reliability score 0-1
            metadata: Additional context
        
        Returns:
            The created PerceptualInput
        """
        inp = PerceptualInput(
            modality=modality,
            source=source,
            data=data,
            confidence=confidence,
            metadata=metadata or {}
        )
        self._input_buffer.append(inp)
        
        # Cap buffer
        if len(self._input_buffer) > self._max_buffer:
            self._input_buffer = self._input_buffer[-self._max_buffer:]
        
        return inp
    
    def get_context(self, window_seconds: int = 30) -> PerceptionContext:
        """
        Build a PerceptionContext from recent inputs.
        
        Args:
            window_seconds: How far back to look for inputs
        
        Returns:
            Aggregated PerceptionContext
        """
        now = datetime.now()
        recent = []
        
        for inp in self._input_buffer:
            try:
                inp_time = datetime.fromisoformat(inp.timestamp)
                if (now - inp_time).total_seconds() <= window_seconds:
                    recent.append(inp)
            except Exception:
                recent.append(inp)  # Include if timestamp is unparseable
        
        if not recent:
            return PerceptionContext()
        
        # Determine dominant modality
        modality_counts = {}
        for inp in recent:
            modality_counts[inp.modality] = modality_counts.get(inp.modality, 0) + 1
        
        dominant = max(modality_counts, key=modality_counts.get)
        
        # Build context summary
        summaries = []
        for mod, count in modality_counts.items():
            summaries.append(f"{count} {mod} input(s)")
        
        return PerceptionContext(
            inputs=recent,
            dominant_modality=dominant,
            attention_focus=recent[-1].source if recent else "",
            context_summary=f"Perceiving: {', '.join(summaries)} from {len(set(i.source for i in recent))} source(s)"
        )
    
    def clear_buffer(self):
        """Clear the input buffer."""
        self._input_buffer.clear()
    
    def get_buffer_summary(self) -> str:
        """Get a summary of buffered inputs."""
        if not self._input_buffer:
            return "No inputs buffered"
        
        modalities = {}
        for inp in self._input_buffer:
            modalities[inp.modality] = modalities.get(inp.modality, 0) + 1
        
        parts = [f"{count} {mod}" for mod, count in modalities.items()]
        return f"Buffer: {', '.join(parts)} ({len(self._input_buffer)} total)"
