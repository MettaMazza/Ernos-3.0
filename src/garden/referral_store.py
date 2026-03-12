"""
Garden Referral Store
JSON-backed persistence for the Proof of Contribution system.
Tracks per-user invite links, referral counts, weekly activity,
and which milestones/roles have already been awarded.
"""
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from src.core.data_paths import data_dir

logger = logging.getLogger("Garden.ReferralStore")

STORE_PATH = Path(data_dir()) / "garden" / "referrals.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReferralStore:
    """Thread-safe JSON referral store."""

    def __init__(self):
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._data: dict = self._load()

    def _load(self) -> dict:
        if STORE_PATH.exists():
            try:
                with open(STORE_PATH, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load referral store: {e}")
        return {}

    def _save(self):
        try:
            with open(STORE_PATH, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save referral store: {e}")

    # ── Public API ────────────────────────────────────────────────────

    def has_user(self, user_id: int) -> bool:
        return str(user_id) in self._data

    def get_user(self, user_id: int) -> dict | None:
        return self._data.get(str(user_id))

    def create_user(self, user_id: int, invite_code: str, invite_url: str):
        """Register a user with their unique invite code."""
        with self._lock:
            if str(user_id) in self._data:
                return  # Already exists
            self._data[str(user_id)] = {
                "invite_code": invite_code,
                "invite_url": invite_url,
                "invite_uses": 0,
                "invited_users": [],
                "weekly_messages": 0,
                "week_start": _now_iso(),
                "last_active": _now_iso(),
                "roles_assigned": [],
                "joined_at": _now_iso(),
            }
            self._save()
            logger.info(f"Registered user {user_id} with invite {invite_code}")

    def find_by_invite_code(self, invite_code: str) -> dict | None:
        """Find user record by their invite code."""
        for uid, data in self._data.items():
            if data.get("invite_code") == invite_code:
                return {"user_id": int(uid), **data}
        return None

    def record_referral(self, referrer_id: int, new_member_id: int):
        """Credit a referral to referrer_id."""
        with self._lock:
            key = str(referrer_id)
            if key not in self._data:
                return
            rec = self._data[key]
            rec["invite_uses"] += 1
            if new_member_id not in rec["invited_users"]:
                rec["invited_users"].append(new_member_id)
            self._save()
            logger.info(f"Referral credited to {referrer_id} (total: {rec['invite_uses']})")

    def record_activity(self, user_id: int):
        """Tick weekly message count for Gardener tracking."""
        with self._lock:
            key = str(user_id)
            if key not in self._data:
                return
            rec = self._data[key]
            # Reset week if >7 days have passed
            week_start = datetime.fromisoformat(rec.get("week_start", _now_iso()))
            now = datetime.now(timezone.utc)
            if (now - week_start).days >= 7:
                rec["weekly_messages"] = 0
                rec["week_start"] = _now_iso()
            rec["weekly_messages"] = rec.get("weekly_messages", 0) + 1
            rec["last_active"] = _now_iso()
            self._save()

    def mark_role_assigned(self, user_id: int, role_name: str):
        with self._lock:
            key = str(user_id)
            if key in self._data:
                roles = self._data[key].setdefault("roles_assigned", [])
                if role_name not in roles:
                    roles.append(role_name)
                self._save()

    def has_role(self, user_id: int, role_name: str) -> bool:
        rec = self._data.get(str(user_id), {})
        return role_name in rec.get("roles_assigned", [])

    def get_referral_count(self, user_id: int) -> int:
        return self._data.get(str(user_id), {}).get("invite_uses", 0)

    def get_weekly_messages(self, user_id: int) -> int:
        return self._data.get(str(user_id), {}).get("weekly_messages", 0)

    def all_records(self) -> dict:
        return dict(self._data)
