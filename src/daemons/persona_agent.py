"""
PersonaAgent — A fully realized persona agent with its own memory silo.

Extracted from town_hall.py per <300 line modularity standard.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from src.core.data_paths import data_dir

logger = logging.getLogger("Daemon.TownHall")


class PersonaAgent:
    """
    A fully realized persona agent with its own memory silo.
    
    Each persona has:
    - persona.txt (character definition)
    - context.jsonl (conversation history in town hall)
    - lessons.json (things they've learned)
    - opinions.json (views formed through discussion)
    - relationships.json (how they feel about other personas)
    """
    
    TOWN_HALL_DIR = data_dir() / "system/town_hall/personas"
    
    def __init__(self, name: str, owner_id: Optional[str] = None):
        self.name = name.lower()
        self.display_name = name.title()
        self.owner_id = owner_id  # User who created this persona (None = system)
        self._home = self.TOWN_HALL_DIR / self.name
        self._home.mkdir(parents=True, exist_ok=True)
        self._init_silo()
    
    def _init_silo(self):
        """Initialize persona memory silo if empty."""
        # Context history
        ctx = self._home / "context.jsonl"
        if not ctx.exists():
            ctx.touch()
        
        # Identity core — required by CognitionEngine
        identity = self._home / ".identity_core.txt"
        if not identity.exists():
            # Generate default identity from persona character definition
            character = self.get_character()
            identity.write_text(character)
        
        # Lessons
        lessons = self._home / "lessons.json"
        if not lessons.exists():
            lessons.write_text("[]")
        
        # Opinions formed in town hall
        opinions = self._home / "opinions.json"
        if not opinions.exists():
            opinions.write_text("{}")
        
        # Relationships with other personas
        rels = self._home / "relationships.json"
        if not rels.exists():
            rels.write_text("{}")
    
    def get_character(self) -> str:
        """
        Load persona character definition.
        
        Priority: user's persona file > town hall silo > public persona registry > fallback.
        """
        # Check user's persona file
        if self.owner_id:
            user_persona = (
                data_dir() / "users" / str(self.owner_id) 
                / "personas" / self.name / "persona.txt"
            )
            if user_persona.exists():
                content = user_persona.read_text()
                if len(content.strip()) > 50:
                    return content
        
        # Check town hall silo
        local_persona = self._home / "persona.txt"
        if local_persona.exists():
            content = local_persona.read_text()
            if len(content.strip()) > 50:
                return content
        
        # Check public persona registry (where rich persona files live)
        public_persona = Path(f"memory/public/personas/{self.name}/persona.txt")
        if public_persona.exists():
            content = public_persona.read_text()
            if len(content.strip()) > 50:
                return content
        
        return f"You are {self.display_name}. You are a unique AI character with your own personality."
    
    def get_context(self, limit: int = 20) -> List[Dict]:
        """Get recent town hall conversation context."""
        ctx_file = self._home / "context.jsonl"
        if not ctx_file.exists():
            return []
        lines = ctx_file.read_text().strip().split("\n") if ctx_file.stat().st_size > 0 else []
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception as e:
                logger.debug(f"Town hall loop suppressed: {e}")
        return entries
    
    def record_message(self, speaker: str, content: str):
        """Record a message to this persona's context."""
        ctx_file = self._home / "context.jsonl"
        entry = {
            "speaker": speaker,
            "content": content[:5000],
            "timestamp": datetime.now().isoformat()
        }
        with open(ctx_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Trim to last 200 entries
        lines = ctx_file.read_text().strip().split("\n")
        if len(lines) > 200:
            ctx_file.write_text("\n".join(lines[-200:]) + "\n")
    
    def get_opinions(self) -> Dict:
        """Load persona's opinions."""
        path = self._home / "opinions.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    
    def save_opinion(self, topic: str, opinion: str):
        """Save an opinion formed during conversation."""
        opinions = self.get_opinions()
        opinions[topic] = {
            "opinion": opinion[:2000],
            "formed_at": datetime.now().isoformat()
        }
        # Keep last 50 opinions
        if len(opinions) > 50:
            sorted_ops = sorted(opinions.items(), key=lambda x: x[1].get("formed_at", ""))
            opinions = dict(sorted_ops[-50:])
        (self._home / "opinions.json").write_text(json.dumps(opinions, indent=2))
    
    def get_relationships(self) -> Dict:
        """Load relationships with other personas."""
        path = self._home / "relationships.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    
    def update_relationship(self, other_persona: str, sentiment: str):
        """Update how this persona feels about another."""
        rels = self.get_relationships()
        rels[other_persona.lower()] = {
            "sentiment": sentiment[:200],
            "updated": datetime.now().isoformat()
        }
        (self._home / "relationships.json").write_text(json.dumps(rels, indent=2))
    
    def get_lessons(self) -> List[str]:
        """Load lessons learned."""
        path = self._home / "lessons.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    
    def add_lesson(self, lesson: str):
        """Add a lesson learned."""
        lessons = self.get_lessons()
        lessons.append(lesson[:1000])
        lessons = lessons[-50:]  # Keep last 50
        (self._home / "lessons.json").write_text(json.dumps(lessons, indent=2))
