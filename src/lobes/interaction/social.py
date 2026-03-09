from ..base import BaseAbility
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger("Lobe.Interaction.Social")

class SocialAbility(BaseAbility):
    """
    Relationship Manager.
    Track trust and autonomy invites.
    
    Loads:
    - memory/users/{id}/relationship.json (trust score, history)
    - Calculates trust level based on interactions
    - Tracks granted autonomy permissions
    """
    
    TRUST_LEVELS = {
        (0, 20): "STRANGER",
        (20, 40): "ACQUAINTANCE", 
        (40, 60): "FAMILIAR",
        (60, 80): "TRUSTED",
        (80, 101): "CLOSE"
    }
    
    async def execute(self, user_id: int) -> str:
        logger.info(f"Social analyzing relationship with {user_id}...")
        
        user_silo = Path(f"memory/users/{user_id}")
        rel_file = user_silo / "relationship.json"
        
        # Load or create relationship data
        if rel_file.exists():
            try:
                data = json.loads(rel_file.read_text())
            except json.JSONDecodeError:
                data = self._create_default_relationship(user_id)
        else:
            data = self._create_default_relationship(user_id)
            user_silo.mkdir(parents=True, exist_ok=True)
            rel_file.write_text(json.dumps(data, indent=2))
        
        # Calculate current trust score
        trust_score = self._calculate_trust(data)
        trust_level = self._get_trust_level(trust_score)
        
        # Build response
        result = []
        result.append(f"### Relationship Status: {trust_level} (Connection Strength)")
        result.append(f"- **Trust Score**: {trust_score}/100")
        result.append(f"- **First Interaction**: {data.get('first_seen', 'Unknown')}")
        result.append(f"- **Total Interactions**: {data.get('interaction_count', 0)}")
        
        # Autonomy permissions
        permissions = data.get("autonomy_permissions", [])
        if permissions:
            result.append(f"- **Granted Permissions**: {', '.join(permissions)}")
        else:
            result.append("- **Granted Permissions**: None")
        
        # Recent activity
        last_seen = data.get("last_seen")
        if last_seen:
            try:
                last_dt = datetime.fromisoformat(last_seen)
                days_ago = (datetime.now() - last_dt).days
                result.append(f"- **Last Seen**: {days_ago} days ago")
            except Exception:
                pass
        
        return "\n".join(result)
    
    def _create_default_relationship(self, user_id: int) -> dict:
        """Create default relationship data for new user."""
        return {
            "user_id": user_id,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "interaction_count": 1,
            "positive_interactions": 0,
            "negative_interactions": 0,
            "autonomy_permissions": [],
            "trust_adjustments": []
        }
    
    def _calculate_trust(self, data: dict) -> int:
        """Calculate trust score from 0-100."""
        base_score = 30  # Default starting trust
        
        # Interaction count bonus (max +20)
        interactions = data.get("interaction_count", 0)
        interaction_bonus = min(20, interactions // 5)
        
        # Longevity bonus (max +20)
        first_seen = data.get("first_seen")
        longevity_bonus = 0
        if first_seen:
            try:
                first_dt = datetime.fromisoformat(first_seen)
                days = (datetime.now() - first_dt).days
                longevity_bonus = min(20, days // 7)  # +1 per week
            except Exception:
                pass
        
        # Positive/Negative ratio (max ±15)
        positive = data.get("positive_interactions", 0)
        negative = data.get("negative_interactions", 0)
        if positive + negative > 0:
            ratio = positive / (positive + negative)
            sentiment_bonus = int((ratio - 0.5) * 30)  # -15 to +15
        else:
            sentiment_bonus = 0
        
        # Manual adjustments
        adjustments = sum(a.get("amount", 0) for a in data.get("trust_adjustments", []))
        
        # Permissions bonus (max +15)
        perms = len(data.get("autonomy_permissions", []))
        permission_bonus = min(15, perms * 5)
        
        total = base_score + interaction_bonus + longevity_bonus + sentiment_bonus + adjustments + permission_bonus
        return max(0, min(100, total))
    
    def _get_trust_level(self, score: int) -> str:
        """Map score to trust level."""
        for (low, high), level in self.TRUST_LEVELS.items():
            if low <= score < high:
                return level
        return "UNKNOWN"

    async def process_reaction(self, user_id: int, emoji: str, message_id: int):
        """
        Ingest a reaction event and update relationship stats.
        """
        # Emoji Sentiment Map
        POSITIVE = ["❤️", "🧡", "💛", "💚", "💙", "💜", "👍", "🔥", "✨", "😂", "🥰", "😍", "🎉", "✅", "🫂"]
        NEGATIVE = ["👎", "😠", "😡", "🤬", "🤮", "🤢", "💀", "💔", "❌", "🚫", "😤"]
        
        user_silo = Path(f"memory/users/{user_id}")
        rel_file = user_silo / "relationship.json"
        
        if not rel_file.exists():
            return "UNKNOWN"
            
        try:
            data = json.loads(rel_file.read_text())
        except Exception:
             return "ERROR"

        sentiment = "NEUTRAL"
        str_emoji = str(emoji)
        
        if str_emoji in POSITIVE:
            sentiment = "POSITIVE"
            data["positive_interactions"] = data.get("positive_interactions", 0) + 1
        elif str_emoji in NEGATIVE:
            sentiment = "NEGATIVE"
            data["negative_interactions"] = data.get("negative_interactions", 0) + 1
            
        # Update Last Seen
        data["last_seen"] = datetime.now().isoformat()
        
        try:
            rel_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save relationship update: {e}")
        
        logger.info(f"Social Reaction: User={user_id} Emoji={emoji} Sentiment={sentiment}")
        return sentiment

