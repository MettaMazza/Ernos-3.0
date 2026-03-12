"""
Group Dynamics Engine — v3.3 Mycelium Network.

Tracks conversation dynamics in group channels:
- Who dominates conversation
- Turn-taking patterns
- Sentiment flow
- Topic shifts

Feeds data to the social graph and relationship manager.
"""
import logging
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.core.data_paths import data_dir

logger = logging.getLogger("Lobe.Interaction.GroupDynamics")


class GroupDynamicsEngine:
    """
    Analyzes multi-user conversation dynamics.
    
    Tracks per-channel:
    - Message counts per user
    - Turn-taking patterns (who replies to whom)
    - Topic keywords
    - Activity windows
    
    Used by the autonomy system to determine when to participate
    and how to balance attention across users.
    """
    
    # Persist dynamics data per channel
    DYNAMICS_DIR = data_dir() / "system/group_dynamics"
    
    def __init__(self):
        self._channel_data = {}
        self._load_all()
    
    def _load_all(self):
        """Load persisted dynamics data."""
        if not self.DYNAMICS_DIR.exists():
            return
        for f in self.DYNAMICS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                self._channel_data[data.get("channel_id", f.stem)] = data
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
    
    def _save_channel(self, channel_id: int):
        """Persist channel dynamics to disk."""
        ch_key = str(channel_id)
        if ch_key not in self._channel_data:
            return
        try:
            self.DYNAMICS_DIR.mkdir(parents=True, exist_ok=True)
            path = self.DYNAMICS_DIR / f"{channel_id}.json"
            path.write_text(json.dumps(self._channel_data[ch_key], indent=2))
        except Exception as e:
            logger.warning(f"Failed to save dynamics for {channel_id}: {e}")
    
    def record_message(self, channel_id: int, user_id: int, 
                       message_length: int, has_mention: bool = False,
                       reply_to: Optional[int] = None):
        """
        Record a message event for dynamics analysis.
        
        Args:
            channel_id: Channel where message was sent
            user_id: User who sent the message
            message_length: Character count of message
            has_mention: Whether the message mentions another user
            reply_to: User ID being replied to (if applicable)
        """
        ch_key = str(channel_id)
        
        if ch_key not in self._channel_data:
            self._channel_data[ch_key] = {
                "channel_id": channel_id,
                "user_counts": {},
                "turn_pairs": [],
                "total_messages": 0,
                "last_active": datetime.now().isoformat(),
                "window_start": datetime.now().isoformat()
            }
        
        data = self._channel_data[ch_key]
        uid_key = str(user_id)
        
        # Update message counts
        if uid_key not in data["user_counts"]:
            data["user_counts"][uid_key] = {
                "messages": 0,
                "total_chars": 0,
                "mentions_made": 0
            }
        
        data["user_counts"][uid_key]["messages"] += 1
        data["user_counts"][uid_key]["total_chars"] += message_length
        if has_mention:
            data["user_counts"][uid_key]["mentions_made"] += 1
        
        data["total_messages"] += 1
        data["last_active"] = datetime.now().isoformat()
        
        # Track turn-taking if this is a reply
        if reply_to:
            data["turn_pairs"].append({
                "from": user_id,
                "to": reply_to,
                "ts": datetime.now().isoformat()
            })
            # Cap turn pairs
            if len(data["turn_pairs"]) > 1000:
                data["turn_pairs"] = data["turn_pairs"][-500:]
        
        self._save_channel(channel_id)
    
    def get_dominant_speaker(self, channel_id: int) -> Optional[int]:
        """Get the most active user in a channel."""
        ch_key = str(channel_id)
        data = self._channel_data.get(ch_key)
        if not data or not data["user_counts"]:
            return None
        
        most_active = max(
            data["user_counts"].items(),
            key=lambda x: x[1]["messages"]
        )
        return int(most_active[0])
    
    def get_quiet_users(self, channel_id: int, threshold: int = 3) -> List[int]:
        """
        Get users who have been relatively quiet.
        
        Useful for Ernos to proactively engage quieter users.
        """
        ch_key = str(channel_id)
        data = self._channel_data.get(ch_key)
        if not data or not data["user_counts"]:
            return []
        
        quiet = []
        avg = data["total_messages"] / max(len(data["user_counts"]), 1)
        
        for uid_key, counts in data["user_counts"].items():
            if counts["messages"] < avg * 0.3 and counts["messages"] <= threshold:
                quiet.append(int(uid_key))
        
        return quiet
    
    def get_channel_dynamics(self, channel_id: int) -> Dict:
        """
        Get a summary of channel dynamics.
        
        Returns dict with:
        - total_messages, active_users, dominant_speaker
        - balance_ratio (0-1, 1 = perfectly balanced)
        """
        ch_key = str(channel_id)
        data = self._channel_data.get(ch_key)
        if not data:
            return {"total_messages": 0, "active_users": 0, "balance_ratio": 1.0}
        
        user_counts = data.get("user_counts", {})
        num_users = len(user_counts)
        total = data.get("total_messages", 0)
        
        if num_users == 0 or total == 0:
            return {"total_messages": 0, "active_users": 0, "balance_ratio": 1.0}
        
        # Calculate balance (Gini-like coefficient)
        counts = [c["messages"] for c in user_counts.values()]
        mean = total / num_users
        if mean == 0:
            balance = 1.0
        else:
            deviations = sum(abs(c - mean) for c in counts)
            balance = max(0, 1.0 - (deviations / (2 * total)))
        
        dominant = self.get_dominant_speaker(channel_id)
        
        return {
            "total_messages": total,
            "active_users": num_users,
            "dominant_speaker": dominant,
            "balance_ratio": round(balance, 2),
            "last_active": data.get("last_active", "Unknown")
        }
    
    def get_turn_taking_pairs(self, channel_id: int) -> List[Dict]:
        """Get the most common conversation pairs."""
        ch_key = str(channel_id)
        data = self._channel_data.get(ch_key)
        if not data:
            return []
        
        pair_counter = Counter()
        for turn in data.get("turn_pairs", []):
            pair = tuple(sorted([turn["from"], turn["to"]]))
            pair_counter[pair] += 1
        
        return [
            {"users": list(pair), "exchanges": count}
            for pair, count in pair_counter.most_common(10)
        ]
