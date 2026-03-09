"""
Home Assistant Integration — v3.4 Rhizome.

Enables Ernos to interact with smart home devices
via the Home Assistant REST API.

Physical world awareness for the sovereign AI.
"""
import logging
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Tools.HomeAssistant")


class HomeAssistantClient:
    """
    Home Assistant REST API client.
    
    Provides Ernos with:
    - Smart home state awareness (lights, sensors, climate)
    - Device control (toggle lights, adjust thermostat)
    - Automation triggers
    - Sensor data for perception pipeline
    
    Config:
        HA_URL: Home Assistant instance URL
        HA_TOKEN: Long-lived access token
    """
    
    def __init__(self, url: str = "", token: str = ""):
        self._url = url.rstrip("/") if url else ""
        self._token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self._entity_cache: Dict[str, Dict] = {}
        logger.info(f"HomeAssistant client configured for {self._url or '(not configured)'}")
    
    @property
    def is_configured(self) -> bool:
        """Check if HA connection is configured."""
        return bool(self._url and self._token)
    
    async def get_states(self) -> List[Dict]:
        """Get all entity states from Home Assistant."""
        if not self.is_configured:
            return []
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/states",
                    headers=self._headers
                ) as resp:
                    if resp.status == 200:
                        states = await resp.json()
                        # Cache states
                        for state in states:
                            self._entity_cache[state["entity_id"]] = state
                        return states
                    else:
                        logger.error(f"HA API error: {resp.status}")
                        return []
        except ImportError:
            logger.warning("aiohttp not installed — HA integration unavailable")
            return []
        except Exception as e:
            logger.error(f"HA connection failed: {e}")
            return []
    
    async def get_entity_state(self, entity_id: str) -> Optional[Dict]:
        """Get state of a specific entity."""
        if not self.is_configured:
            return None
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._url}/api/states/{entity_id}",
                    headers=self._headers
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"HA entity query failed: {e}")
        return None
    
    async def call_service(self, domain: str, service: str, 
                           entity_id: str = "", data: Dict = None) -> bool:
        """
        Call a Home Assistant service.
        
        Examples:
            call_service("light", "turn_on", "light.bedroom")
            call_service("climate", "set_temperature", 
                         "climate.thermostat", {"temperature": 72})
        """
        if not self.is_configured:
            return False
        
        payload = data or {}
        if entity_id:
            payload["entity_id"] = entity_id
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._url}/api/services/{domain}/{service}",
                    headers=self._headers,
                    json=payload
                ) as resp:
                    if resp.status in (200, 201):
                        logger.info(f"HA service called: {domain}.{service} on {entity_id}")
                        return True
                    else:
                        logger.error(f"HA service error: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"HA service call failed: {e}")
            return False
    
    async def toggle(self, entity_id: str) -> bool:
        """Toggle an entity (light, switch, etc.)."""
        domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
        return await self.call_service(domain, "toggle", entity_id)
    
    def get_sensor_summary(self) -> str:
        """Get a human-readable summary of cached sensor states."""
        if not self._entity_cache:
            return "No sensor data available"
        
        sensors = []
        for eid, state in self._entity_cache.items():
            if eid.startswith("sensor."):
                name = state.get("attributes", {}).get("friendly_name", eid)
                value = state.get("state", "unknown")
                unit = state.get("attributes", {}).get("unit_of_measurement", "")
                sensors.append(f"{name}: {value}{unit}")
        
        if not sensors:
            return "No sensors found"
        
        return "\n".join(sensors[:20])  # Cap at 20 sensors
    
    def get_room_context(self) -> Dict:
        """
        Build a room-level context from cached states.
        
        Groups entities by area/room for perception pipeline.
        """
        rooms = {}
        for eid, state in self._entity_cache.items():
            area = state.get("attributes", {}).get("area", "unknown")
            if area not in rooms:
                rooms[area] = {"lights": [], "sensors": [], "climate": []}
            
            if eid.startswith("light."):
                rooms[area]["lights"].append({
                    "name": state.get("attributes", {}).get("friendly_name", eid),
                    "state": state.get("state", "off")
                })
            elif eid.startswith("sensor."):
                rooms[area]["sensors"].append({
                    "name": state.get("attributes", {}).get("friendly_name", eid),
                    "value": state.get("state", ""),
                    "unit": state.get("attributes", {}).get("unit_of_measurement", "")
                })
            elif eid.startswith("climate."):
                rooms[area]["climate"].append({
                    "name": state.get("attributes", {}).get("friendly_name", eid),
                    "state": state.get("state", ""),
                    "temperature": state.get("attributes", {}).get("current_temperature")
                })
        
        return rooms
