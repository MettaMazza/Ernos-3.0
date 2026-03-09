
import json
import time
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

# CONFIGURATION
# 12 Hours in seconds
CYCLE_DURATION = 12 * 60 * 60
DAILY_DURATION = 24 * 60 * 60

# Tier Limits (Messages per cycle)
TIER_LIMITS = {
    0: 20,           # Free: 20 msgs / 12h
    1: 999999,       # Pollinator: "Unlimited" (High Cap)
    2: 999999,       # Planter: Unlimited
    3: 999999,       # Gardener: Unlimited
    4: 999999,       # Terraformer: Unlimited
}

# ═══════════════════════════════════════════════════════════════
# TOOL LIMITS: (tool_name) -> {tier: limit}
# "cycle" = 12h reset, "daily" = 24h reset
# -1 = unlimited
#
# DESIGN PHILOSOPHY:
# - Core grounding tools (search, browse, science, memory, news,
#   coder lobe, KG visualizer) are NEVER limited — they are
#   essential for Ernos to give accurate, grounded responses.
# - Voice/audio is NEVER limited — it's an accessibility feature.
# - propose_prompt_update is internal (not user-facing).
# - Only GPU-expensive, resource-heavy, or spam-risky tools are gated.
# - Any tool NOT listed here is always allowed (free).
# ═══════════════════════════════════════════════════════════════
TOOL_LIMITS = {
    # ── SPAM PREVENTION (cycle-based) ─────────────────────────
    "dm":                   {"period": "cycle",  0: 20,  1: -1, 2: -1, 3: -1, 4: -1},

    # ── RESOURCE-HEAVY (daily-based) ──────────────────────────
    "start_deep_research":  {"period": "daily",  0: 1,  1: 3,  2: 5,  3: 10, 4: -1},
    "browse_interactive":   {"period": "daily",  0: 1,  1: 2,  2: 3,  3: 5,  4: 10},
    "generate_pdf":         {"period": "daily",  0: 1,  1: 3,  2: 5,  3: 10, 4: -1},
    "create_program":       {"period": "daily",  0: 2,  1: 5,  2: 10, 3: -1, 4: -1},

    # ── GPU-EXPENSIVE (daily-based) ───────────────────────────
    "generate_image":       {"period": "daily",  0: 2,  1: 4,  2: 10, 3: 20, 4: 50},
    "generate_video":       {"period": "daily",  0: 0,  1: 0,  2: 2,  3: 5,  4: 10},
    "generate_music":       {"period": "daily",  0: 2,  1: 5,  2: 10, 3: 20, 4: 50},
    "generate_speech":      {"period": "daily",  0: 5,  1: 10, 2: 25, 3: 50, 4: -1},
    "produce_audiobook":    {"period": "daily",  0: 0,  1: 1,  2: 2,  3: 5,  4: -1},

    # ── RESOURCE-HEAVY (daily) ────────────────────────────────
    # start_game is Admin-only (no user limits needed)
}

# Warning Thresholds (Messages remaining)
WARNING_THRESHOLD = 3

logger = logging.getLogger("FluxCapacitor")

class FluxCapacitor:
    """
    Manages user energy (rate limits) and tiers.
    "It's what makes time travel possible." - Doc Brown
    
    Persists data to memory/users/{user_id}/flux.json
    
    Tracks:
    - Message consumption (12h cycle)
    - Tool-specific usage (cycle or daily)
    - Tier status
    """
    
    def __init__(self, bot=None):
        self.bot = bot # Optional check for admin overrides via bot settings

    @staticmethod
    def _patreon_url() -> str:
        try:
            from config import settings
            return getattr(settings, 'PATREON_URL', 'https://www.patreon.com/c/TheErnOSGardens')
        except Exception:
            return 'https://www.patreon.com/c/TheErnOSGardens'

        
    def _get_path(self, user_id: int) -> Path:
        from src.privacy.scopes import ScopeManager
        try:
             user_home = ScopeManager.get_user_home(user_id)
        except Exception:
             user_home = Path(f"memory/users/{user_id}")
             
        return user_home / "flux.json"

    def _load(self, user_id: int) -> Dict[str, Any]:
        path = self._get_path(user_id)
        if not path.exists():
            return {
                "tier": 0,
                "msg_count": 0,
                "last_reset": time.time(),
                "warned": False,
                "tool_usage": {},
                "tool_daily_reset": time.time(),
            }
        
        try:
            data = json.loads(path.read_text())
            # Migration: ensure new fields exist
            if "tool_usage" not in data:
                data["tool_usage"] = {}
            if "tool_daily_reset" not in data:
                data["tool_daily_reset"] = time.time()
            return data
        except Exception as e:
            logger.error(f"Failed to load flux data for {user_id}: {e}")
            return {"tier": 0, "msg_count": 0, "last_reset": time.time(), "warned": False, "tool_usage": {}, "tool_daily_reset": time.time()}

    def _save(self, user_id: int, data: Dict[str, Any]):
        path = self._get_path(user_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to save flux data for {user_id}: {e}")

    def get_tier(self, user_id: int) -> int:
        data = self._load(user_id)
        return data.get("tier", 0)

    def set_tier(self, user_id: int, tier: int):
        data = self._load(user_id)
        data["tier"] = tier
        logger.info(f"User {user_id} tier updated to {tier}")
        self._save(user_id, data)

    def consume(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Consume 1 message credit.
        Returns: (allowed, warning_message)
        """
        # Admin bypass
        try:
            from config import settings
            if str(user_id) in {str(aid) for aid in settings.ADMIN_IDS}:
                return True, None
        except Exception as e:
            logger.debug(f"Rate limit check suppressed: {e}")
        
        data = self._load(user_id)
        tier = data.get("tier", 0)
        
        limit = TIER_LIMITS.get(tier, 20)
        now = time.time()
        
        # Check Reset (12h cycle)
        time_since_reset = now - data["last_reset"]
        if time_since_reset > CYCLE_DURATION:
            data["msg_count"] = 0
            data["last_reset"] = now
            data["warned"] = False
            # Also reset cycle-based tool usage
            self._reset_cycle_tools(data)
        
        # Check daily reset for tools
        time_since_daily = now - data.get("tool_daily_reset", 0)
        if time_since_daily > DAILY_DURATION:
            self._reset_daily_tools(data)
            data["tool_daily_reset"] = now
        
        # Check Limit
        if data["msg_count"] >= limit:
            self._save(user_id, data)
            time_left = int(CYCLE_DURATION - time_since_reset)
            hours_left = time_left // 3600
            mins_left = (time_left % 3600) // 60
            return False, f"Energy depleted. Systems recharging in {hours_left}h {mins_left}m. 🌱 Upgrade your tier for more access: {self._patreon_url()}"

        # Increment
        data["msg_count"] += 1
        
        # Check Warning
        remaining = limit - data["msg_count"]
        warning = None
        
        if remaining <= WARNING_THRESHOLD and not data.get("warned", False) and tier == 0:
            warning = f"⚠️ **Low Energy Warning**: {remaining} messages remaining in this cycle."
            data["warned"] = True
            
        self._save(user_id, data)
        return True, warning

    def consume_tool(self, user_id: int, tool_name: str) -> Tuple[bool, Optional[str]]:
        """
        Consume 1 tool credit for a specific tool.
        Returns: (allowed, rejection_message)
        
        If the tool is not in TOOL_LIMITS, it's always allowed (free tool).
        """
        if tool_name not in TOOL_LIMITS:
            return True, None  # Unlisted = free
        
        # Admin & System bypass
        if str(user_id) in ["CORE", "SYSTEM"]:
            return True, None

        try:
            from config import settings
            if str(user_id) in {str(aid) for aid in settings.ADMIN_IDS}:
                return True, None
        except Exception as e:
            logger.debug(f"Content filter check suppressed: {e}")
        
        data = self._load(user_id)
        tier = data.get("tier", 0)
        now = time.time()
        
        tool_config = TOOL_LIMITS[tool_name]
        period = tool_config.get("period", "cycle")
        limit = tool_config.get(tier, tool_config.get(0, 0))  # Fallback to tier 0
        
        # Unlimited
        if limit == -1:
            return True, None
        
        # Check resets
        time_since_reset = now - data.get("last_reset", 0)
        if time_since_reset > CYCLE_DURATION:
            data["msg_count"] = 0
            data["last_reset"] = now
            data["warned"] = False
            self._reset_cycle_tools(data)
        
        time_since_daily = now - data.get("tool_daily_reset", 0)
        if time_since_daily > DAILY_DURATION:
            self._reset_daily_tools(data)
            data["tool_daily_reset"] = now
        
        # Get current usage
        tool_usage = data.get("tool_usage", {})
        current = tool_usage.get(tool_name, 0)
        
        if current >= limit:
            if limit == 0:
                msg = f"🔒 `{tool_name}` is not available at your current tier. Upgrade to unlock: {self._patreon_url()}"
            else:
                period_label = "12-hour cycle" if period == "cycle" else "day"
                msg = f"⚡ `{tool_name}` limit reached ({current}/{limit} per {period_label}). Upgrade for more: {self._patreon_url()}"
            self._save(user_id, data)
            return False, msg
        
        # Increment and save
        tool_usage[tool_name] = current + 1
        data["tool_usage"] = tool_usage
        self._save(user_id, data)
        
        remaining = limit - (current + 1)
        info = None
        if remaining <= 1 and limit > 1:
            period_label = "12-hour cycle" if period == "cycle" else "day"
            info = f"⚡ `{tool_name}`: {remaining} use(s) remaining this {period_label}."
        
        return True, info

    def _reset_cycle_tools(self, data: Dict[str, Any]):
        """Reset tool usage for cycle-based tools."""
        tool_usage = data.get("tool_usage", {})
        for tool_name, config in TOOL_LIMITS.items():
            if config.get("period") == "cycle":
                tool_usage.pop(tool_name, None)
        data["tool_usage"] = tool_usage

    def _reset_daily_tools(self, data: Dict[str, Any]):
        """Reset tool usage for daily-based tools."""
        tool_usage = data.get("tool_usage", {})
        for tool_name, config in TOOL_LIMITS.items():
            if config.get("period") == "daily":
                tool_usage.pop(tool_name, None)
        data["tool_usage"] = tool_usage

    def get_status(self, user_id: int) -> Dict[str, Any]:
        """Get displayable status for UI."""
        data = self._load(user_id)
        now = time.time()
        time_since_reset = now - data.get("last_reset", 0)
        
        msg_count = data.get("msg_count", 0)
        if time_since_reset > CYCLE_DURATION:
            msg_count = 0
            time_since_reset = 0
            
        tier = data.get("tier", 0)
        limit = TIER_LIMITS.get(tier, 20)
        
        return {
            "tier": tier,
            "used": msg_count,
            "limit": limit,
            "remaining": max(0, limit - msg_count),
            "next_reset": int(now + (CYCLE_DURATION - time_since_reset)),
            "tool_usage": data.get("tool_usage", {}),
        }
