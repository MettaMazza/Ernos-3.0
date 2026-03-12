"""
Ernos Patreon Integration — OAuth2 flow + tier mapping.

Handles:
1. OAuth2 authorization URL generation
2. Callback processing (exchange code for token)
3. Fetching user's pledge tier from Patreon API
4. Mapping Patreon tier → Ernos tier (0-4)

Requires env vars:
  PATREON_CLIENT_ID
  PATREON_CLIENT_SECRET
  PATREON_REDIRECT_URI (default: http://localhost:8420/api/auth/patreon/callback)
"""
import os
import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("Web.Patreon")

# Patreon OAuth2 config
PATREON_CLIENT_ID = os.environ.get("PATREON_CLIENT_ID", "")
PATREON_CLIENT_SECRET = os.environ.get("PATREON_CLIENT_SECRET", "")
PATREON_REDIRECT_URI = os.environ.get(
    "PATREON_REDIRECT_URI",
    "http://localhost:8420/api/auth/patreon/callback"
)

PATREON_AUTH_URL = "https://www.patreon.com/oauth2/authorize"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
PATREON_IDENTITY_URL = "https://www.patreon.com/api/oauth2/v2/identity"
PATREON_CAMPAIGN_URL = "https://www.patreon.com/api/oauth2/v2/campaigns"

# ═══════════════════════════════════════════════════════════
# Tier Mapping
# ═══════════════════════════════════════════════════════════
# Map Patreon tier names/amounts to Ernos tiers.
# Update these to match your actual Patreon tier names.

PATREON_TIER_MAP = {
    # By tier name (case-insensitive)
    "pollinator": 1,
    "planter": 2,
    "gardener": 3,
    "terraformer": 4,
    # Fallback by amount (cents per month)
    # Adjust these to your actual tier prices
}

# Amount thresholds in cents (fallback if name matching fails)
AMOUNT_THRESHOLDS = [
    (100, 1),    # $1+ → Pollinator
    (500, 2),    # $5+ → Planter
    (1500, 3),   # $15+ → Gardener
    (5000, 4),   # $50+ → Terraformer
]


def is_configured() -> bool:
    """Check if Patreon OAuth is configured."""
    return bool(PATREON_CLIENT_ID and PATREON_CLIENT_SECRET)


def get_auth_url(state: str = "") -> str:
    """
    Generate the Patreon OAuth2 authorization URL.

    Args:
        state: CSRF state token (should be the user's JWT or session ID)

    Returns:
        URL to redirect the user to for Patreon authorization.
    """
    if not is_configured():
        return ""

    params = {
        "response_type": "code",
        "client_id": PATREON_CLIENT_ID,
        "redirect_uri": PATREON_REDIRECT_URI,
        "scope": "identity identity.memberships",
        "state": state,
    }

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{PATREON_AUTH_URL}?{query}"


async def exchange_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Exchange an authorization code for an access token.

    Returns:
        Token response dict or None on failure.
    """
    if not is_configured():
        logger.error("Patreon OAuth not configured")
        return None

    import aiohttp

    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": PATREON_CLIENT_ID,
        "client_secret": PATREON_CLIENT_SECRET,
        "redirect_uri": PATREON_REDIRECT_URI,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(PATREON_TOKEN_URL, data=data) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Patreon token exchange failed ({resp.status}): {body}")
                    return None
                return await resp.json()
    except Exception as e:
        logger.error(f"Patreon token exchange error: {e}")
        return None


async def get_user_tier(access_token: str) -> Tuple[Optional[str], int]:
    """
    Fetch the user's Patreon identity and determine their Ernos tier.

    Args:
        access_token: Patreon OAuth access token

    Returns:
        (patreon_user_id, ernos_tier)
    """
    import aiohttp

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "include": "memberships,memberships.currently_entitled_tiers",
        "fields[member]": "patron_status,currently_entitled_amount_cents",
        "fields[tier]": "title,amount_cents",
        "fields[user]": "full_name,email",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                PATREON_IDENTITY_URL,
                headers=headers,
                params=params,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Patreon identity fetch failed ({resp.status}): {body}")
                    return None, 0

                data = await resp.json()

        # Extract user ID
        patreon_user_id = data.get("data", {}).get("id")

        # Find active membership
        included = data.get("included", [])
        tier = 0

        for item in included:
            if item.get("type") == "tier":
                title = item.get("attributes", {}).get("title", "").lower()
                amount = item.get("attributes", {}).get("amount_cents", 0)

                # Try name matching first
                if title in PATREON_TIER_MAP:
                    tier = max(tier, PATREON_TIER_MAP[title])
                else:
                    # Fall back to amount thresholds
                    for threshold, mapped_tier in sorted(AMOUNT_THRESHOLDS, reverse=True):
                        if amount >= threshold:
                            tier = max(tier, mapped_tier)
                            break

            elif item.get("type") == "member":
                status = item.get("attributes", {}).get("patron_status")
                if status != "active_patron":
                    # Not an active patron — tier stays 0
                    tier = 0
                    break

                # Check amount as fallback
                amount = item.get("attributes", {}).get("currently_entitled_amount_cents", 0)
                if tier == 0 and amount > 0:
                    for threshold, mapped_tier in sorted(AMOUNT_THRESHOLDS, reverse=True):
                        if amount >= threshold:
                            tier = mapped_tier
                            break

        logger.info(f"Patreon user {patreon_user_id}: tier {tier}")
        return patreon_user_id, tier

    except Exception as e:
        logger.error(f"Patreon tier fetch error: {e}")
        return None, 0


async def process_callback(
    code: str,
    user_id: str,
) -> Tuple[bool, str, int]:
    """
    Full Patreon OAuth callback processing.

    1. Exchange code for token
    2. Fetch user's tier
    3. Link Patreon to web account
    4. Update flux capacitor tier

    Args:
        code: OAuth authorization code
        user_id: Ernos web user ID

    Returns:
        (success, message, tier)
    """
    # Exchange code
    token_data = await exchange_code(code)
    if not token_data:
        return False, "Failed to connect to Patreon. Please try again.", 0

    access_token = token_data.get("access_token")
    if not access_token:
        return False, "Invalid response from Patreon.", 0

    # Get tier
    patreon_user_id, tier = await get_user_tier(access_token)
    if not patreon_user_id:
        return False, "Could not retrieve your Patreon account.", 0

    # Link account
    from src.web.accounts import link_patreon
    link_patreon(user_id, patreon_user_id, tier)

    tier_names = {0: "Free", 1: "Pollinator", 2: "Planter", 3: "Gardener", 4: "Terraformer"}
    tier_name = tier_names.get(tier, f"Tier {tier}")

    return True, f"Patreon linked! Your tier: {tier_name} 🌱", tier
