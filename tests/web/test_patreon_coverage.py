"""
Tests for src/web/patreon.py — Patreon OAuth integration.

Covers: is_configured, get_auth_url, exchange_code, get_user_tier, process_callback,
        tier mapping by name and amount, error handling.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ── Configuration Check ──────────────────────────────────

class TestIsConfigured:
    def test_returns_false_when_unconfigured(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", ""):
            from src.web.patreon import is_configured
            assert is_configured() is False

    def test_returns_true_when_configured(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", "test_id"):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", "test_secret"):
                from src.web.patreon import is_configured
                assert is_configured() is True

    def test_returns_false_when_only_id(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", "test_id"):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", ""):
                from src.web.patreon import is_configured
                assert is_configured() is False


# ── Auth URL ──────────────────────────────────────────────

class TestGetAuthUrl:
    def test_returns_empty_when_unconfigured(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", ""):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", ""):
                from src.web.patreon import get_auth_url
                assert get_auth_url() == ""

    def test_returns_valid_url(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", "test_id"):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", "test_secret"):
                from src.web.patreon import get_auth_url
                url = get_auth_url(state="user-123")
                assert "patreon.com/oauth2/authorize" in url
                assert "client_id=test_id" in url
                assert "state=user-123" in url
                assert "scope=identity" in url


# ── Exchange Code ─────────────────────────────────────────

class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_returns_none_when_unconfigured(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", ""):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", ""):
                from src.web.patreon import exchange_code
                result = await exchange_code("test_code")
                assert result is None

    @pytest.mark.asyncio
    async def test_successful_exchange(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", "id"):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", "secret"):
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value={"access_token": "tok123"})

                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=False)
                mock_session.post = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_resp),
                    __aexit__=AsyncMock(return_value=False),
                ))

                with patch("aiohttp.ClientSession", return_value=mock_session):
                    from src.web.patreon import exchange_code
                    result = await exchange_code("auth_code")
                    assert result == {"access_token": "tok123"}

    @pytest.mark.asyncio
    async def test_failed_exchange_status(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", "id"):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", "secret"):
                mock_resp = AsyncMock()
                mock_resp.status = 400
                mock_resp.text = AsyncMock(return_value="Bad request")

                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=False)
                mock_session.post = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_resp),
                    __aexit__=AsyncMock(return_value=False),
                ))

                with patch("aiohttp.ClientSession", return_value=mock_session):
                    from src.web.patreon import exchange_code
                    result = await exchange_code("bad_code")
                    assert result is None

    @pytest.mark.asyncio
    async def test_exchange_network_error(self):
        with patch("src.web.patreon.PATREON_CLIENT_ID", "id"):
            with patch("src.web.patreon.PATREON_CLIENT_SECRET", "secret"):
                with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
                    from src.web.patreon import exchange_code
                    result = await exchange_code("code")
                    assert result is None


# ── Get User Tier ─────────────────────────────────────────

class TestGetUserTier:
    @pytest.mark.asyncio
    async def test_successful_tier_by_name(self):
        mock_data = {
            "data": {"id": "patreon-user-1"},
            "included": [
                {
                    "type": "member",
                    "attributes": {"patron_status": "active_patron", "currently_entitled_amount_cents": 500}
                },
                {
                    "type": "tier",
                    "attributes": {"title": "Gardener", "amount_cents": 1500}
                },
            ]
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from src.web.patreon import get_user_tier
            patreon_id, tier = await get_user_tier("test_token")
            assert patreon_id == "patreon-user-1"
            assert tier == 3  # Gardener = tier 3

    @pytest.mark.asyncio
    async def test_tier_by_amount_fallback(self):
        mock_data = {
            "data": {"id": "user-2"},
            "included": [
                {
                    "type": "member",
                    "attributes": {"patron_status": "active_patron", "currently_entitled_amount_cents": 500}
                },
                {
                    "type": "tier",
                    "attributes": {"title": "Unknown Tier Name", "amount_cents": 500}
                },
            ]
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from src.web.patreon import get_user_tier
            _, tier = await get_user_tier("token")
            assert tier == 2  # $5 = Planter = tier 2

    @pytest.mark.asyncio
    async def test_inactive_patron_gets_tier_zero(self):
        mock_data = {
            "data": {"id": "user-3"},
            "included": [
                {
                    "type": "member",
                    "attributes": {"patron_status": "declined_patron", "currently_entitled_amount_cents": 0}
                },
            ]
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from src.web.patreon import get_user_tier
            _, tier = await get_user_tier("token")
            assert tier == 0

    @pytest.mark.asyncio
    async def test_api_error_returns_none_zero(self):
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_resp.text = AsyncMock(return_value="Unauthorized")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from src.web.patreon import get_user_tier
            patreon_id, tier = await get_user_tier("bad_token")
            assert patreon_id is None
            assert tier == 0

    @pytest.mark.asyncio
    async def test_network_error_returns_none_zero(self):
        with patch("aiohttp.ClientSession", side_effect=Exception("Connection refused")):
            from src.web.patreon import get_user_tier
            patreon_id, tier = await get_user_tier("token")
            assert patreon_id is None
            assert tier == 0

    @pytest.mark.asyncio
    async def test_member_with_amount_fallback(self):
        """Active patron with amount but no tier object → uses member amount."""
        mock_data = {
            "data": {"id": "user-4"},
            "included": [
                {
                    "type": "member",
                    "attributes": {"patron_status": "active_patron", "currently_entitled_amount_cents": 5000}
                },
            ]
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_data)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_resp),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from src.web.patreon import get_user_tier
            _, tier = await get_user_tier("token")
            assert tier == 4  # $50 = Terraformer


# ── Process Callback ──────────────────────────────────────

class TestProcessCallback:
    @pytest.mark.asyncio
    async def test_successful_callback(self):
        from src.web.patreon import process_callback
        with patch("src.web.patreon.exchange_code", new_callable=AsyncMock, return_value={"access_token": "tok123"}):
            with patch("src.web.patreon.get_user_tier", new_callable=AsyncMock, return_value=("patreon-1", 3)):
                with patch("src.web.accounts.link_patreon") as mock_link:
                    success, message, tier = await process_callback("code", "user-1")
                    assert success is True
                    assert tier == 3
                    assert "linked" in message.lower()
                    mock_link.assert_called_once_with("user-1", "patreon-1", 3)

    @pytest.mark.asyncio
    async def test_exchange_failure(self):
        from src.web.patreon import process_callback
        with patch("src.web.patreon.exchange_code", new_callable=AsyncMock, return_value=None):
            success, message, tier = await process_callback("code", "user-1")
            assert success is False
            assert tier == 0

    @pytest.mark.asyncio
    async def test_missing_access_token(self):
        from src.web.patreon import process_callback
        with patch("src.web.patreon.exchange_code", new_callable=AsyncMock, return_value={"no_token": True}):
            success, message, tier = await process_callback("code", "user-1")
            assert success is False
            assert tier == 0

    @pytest.mark.asyncio
    async def test_tier_fetch_failure(self):
        from src.web.patreon import process_callback
        with patch("src.web.patreon.exchange_code", new_callable=AsyncMock, return_value={"access_token": "tok"}):
            with patch("src.web.patreon.get_user_tier", new_callable=AsyncMock, return_value=(None, 0)):
                success, message, tier = await process_callback("code", "user-1")
                assert success is False
                assert tier == 0
