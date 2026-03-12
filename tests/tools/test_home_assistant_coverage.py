"""Tests for HomeAssistantClient — 8 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.tools.home_assistant import HomeAssistantClient


@pytest.fixture
def client():
    return HomeAssistantClient(url="http://localhost:8123", token="test_token")


@pytest.fixture
def unconfigured():
    return HomeAssistantClient()


class TestInit:
    def test_configured(self, client):
        assert client.is_configured is True

    def test_unconfigured(self, unconfigured):
        assert unconfigured.is_configured is False


class TestGetStates:
    @pytest.mark.asyncio
    async def test_not_configured(self, unconfigured):
        result = await unconfigured.get_states()
        assert result == []

    @pytest.mark.asyncio
    async def test_success(self, client):
        import sys
        mock_aiohttp = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[
            {"entity_id": "light.bedroom", "state": "on", "attributes": {}}
        ])
        # Build async context managers
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_get_ctx.__aexit__ = AsyncMock()
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_ctx)
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session_ctx)
        with patch.dict(sys.modules, {"aiohttp": mock_aiohttp}):
            result = await client.get_states()
            assert len(result) == 1


class TestCallService:
    @pytest.mark.asyncio
    async def test_not_configured(self, unconfigured):
        result = await unconfigured.call_service("light", "turn_on", "light.bedroom")
        assert result is False


class TestToggle:
    @pytest.mark.asyncio
    async def test_delegates_to_call_service(self, client):
        with patch.object(client, "call_service", new_callable=AsyncMock, return_value=True):
            result = await client.toggle("light.bedroom")
            assert result is True
            client.call_service.assert_called_once_with("light", "toggle", "light.bedroom")


class TestGetSensorSummary:
    def test_empty_cache(self, client):
        result = client.get_sensor_summary()
        assert "No sensor data" in result

    def test_with_sensors(self, client):
        client._entity_cache = {
            "sensor.temp": {
                "state": "72",
                "attributes": {"friendly_name": "Temperature", "unit_of_measurement": "°F"}
            }
        }
        result = client.get_sensor_summary()
        assert "Temperature" in result
        assert "72" in result


class TestGetRoomContext:
    def test_empty(self, client):
        result = client.get_room_context()
        assert result == {}

    def test_groups_by_area(self, client):
        client._entity_cache = {
            "light.bedroom": {
                "state": "on",
                "attributes": {"area": "bedroom", "friendly_name": "Bedroom Light"}
            },
            "sensor.bedroom_temp": {
                "state": "72",
                "attributes": {"area": "bedroom", "friendly_name": "Temp", "unit_of_measurement": "°F"}
            }
        }
        result = client.get_room_context()
        assert "bedroom" in result
        assert len(result["bedroom"]["lights"]) == 1
        assert len(result["bedroom"]["sensors"]) == 1
