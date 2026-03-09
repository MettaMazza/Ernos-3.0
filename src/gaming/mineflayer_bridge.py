"""
Mineflayer Bridge - Python IPC to JavaScript bot.

Manages subprocess and JSON communication.
"""
import asyncio
import subprocess
import json
import os
import uuid
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("Gaming.Bridge")


@dataclass
class BridgeResponse:
    """Response from Mineflayer command."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MineflayerBridge:
    """
    Python bridge to Mineflayer JavaScript bot.
    Communicates via JSON IPC through subprocess stdin/stdout.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 25565,
        username: str = "Ernos",
        on_event=None
    ):
        self.host = host
        self.port = port
        self.username = username
        self.on_event = on_event
        
        self.process: Optional[subprocess.Popen] = None
        self.pending: Dict[str, asyncio.Future] = {}
        self._reader_task = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Start the Mineflayer bot and wait for spawn."""
        bot_path = os.path.join(os.path.dirname(__file__), "mineflayer", "bot.js")
        
        logger.info(f"BRIDGE_CONNECT_START | host={self.host} port={self.port} user={self.username}")
        
        env = os.environ.copy()
        env["MC_HOST"] = self.host
        env["MC_PORT"] = str(self.port)
        env["MC_USERNAME"] = self.username
        
        self.process = subprocess.Popen(
            ["node", bot_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # Start stderr reader for JS errors
        self._stderr_task = asyncio.create_task(self._read_stderr())
        
        self._reader_task = asyncio.create_task(self._read_responses())
        
        # Wait for spawn event
        spawn_future = asyncio.get_event_loop().create_future()
        
        def on_spawn(data):
            spawn_future.set_result(True)
        
        self._spawn_callback = on_spawn
        
        try:
            await asyncio.wait_for(spawn_future, timeout=30)
            self._connected = True
            logger.info(f"BRIDGE_CONNECTED | username={self.username}")
            return True
        except asyncio.TimeoutError:
            logger.error("BRIDGE_CONNECT_TIMEOUT | 30 seconds elapsed")
            await self.disconnect()
            return False
    
    async def _read_stderr(self):
        """Read stderr from Node process and log it."""
        while self.process and self.process.stderr:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stderr.readline
                )
                if not line:
                    break
                logger.warning(f"MINEFLAYER_STDERR: {line.strip()}")
            except Exception:
                break
    
    async def disconnect(self):
        """Stop the bot."""
        if self.process:
            try:
                await self.execute("disconnect", timeout=5)
            except:
                pass
            self.process.terminate()
            self.process = None
        
        if self._reader_task:
            self._reader_task.cancel()
        
        self._connected = False
        logger.info("Bot disconnected")
    
    async def _read_responses(self):
        """Background task to read responses from bot."""
        while self.process and self.process.stdout:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdout.readline
                )
                
                if not line:
                    break
                
                data = json.loads(line.strip())
                
                # Handle events
                if "event" in data:
                    event_type = data["event"]
                    event_data = data.get("data", {})
                    
                    if event_type == "spawn" and hasattr(self, "_spawn_callback"):
                        self._spawn_callback(event_data)
                    
                    if self.on_event:
                        self.on_event(event_type, event_data)
                    continue
                
                # Handle command responses
                if "id" in data:
                    request_id = data["id"]
                    if request_id in self.pending:
                        future = self.pending.pop(request_id)
                        if data.get("success"):
                            future.set_result(BridgeResponse(True, data.get("data")))
                        else:
                            future.set_result(BridgeResponse(False, error=data.get("error")))
                            
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"Reader error: {e}")
                break
    
    async def execute(
        self,
        command: str,
        params: Dict = None,
        timeout: float = 10.0  # Reduced default timeout
    ) -> BridgeResponse:
        """Execute a command and wait for response."""
        if not self.process:
            logger.warning(f"BRIDGE_EXECUTE_FAIL | process=None | cmd={command}")
            return BridgeResponse(False, error="Not connected")
        
        # Check if process is still alive
        if self.process.poll() is not None:
            logger.error(f"BRIDGE_PROCESS_DEAD | exit_code={self.process.poll()} | cmd={command}")
            self._connected = False
            return BridgeResponse(False, error=f"Process died with code {self.process.poll()}")
        
        request_id = str(uuid.uuid4())[:8]
        request = json.dumps({
            "id": request_id,
            "command": command,
            "params": params or {}
        })
        
        future = asyncio.get_event_loop().create_future()
        self.pending[request_id] = future
        
        try:
            logger.debug(f"BRIDGE_SEND | cmd={command} | id={request_id}")
            self.process.stdin.write(request + "\n")
            self.process.stdin.flush()
            
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.debug(f"BRIDGE_RECV | cmd={command} | success={result.success}")
            return result
        except asyncio.TimeoutError:
            self.pending.pop(request_id, None)
            logger.warning(f"BRIDGE_TIMEOUT | cmd={command} | timeout={timeout}s")
            # Check if process died during wait
            if self.process.poll() is not None:
                logger.error(f"BRIDGE_PROCESS_DIED_DURING | cmd={command}")
                self._connected = False
            return BridgeResponse(False, error=f"Command timeout ({timeout}s)")
    
    # === High-level commands ===
    
    async def goto(self, x: float, y: float, z: float, range: int = 1):
        """Navigate to position."""
        return await self.execute("goto", {"x": x, "y": y, "z": z, "range": range})
    
    async def follow(self, username: str, range: int = 3):
        """Follow a player."""
        return await self.execute("follow", {"username": username, "range": range})
    
    async def stop_follow(self):
        """Stop following."""
        return await self.execute("stop_follow")
    
    async def collect(self, block_type: str, count: int = 1):
        """Collect blocks."""
        return await self.execute("collect", {"block_type": block_type, "count": count}, timeout=120)
    
    async def attack(self, entity_type: str = "hostile"):
        """Attack entity."""
        return await self.execute("attack", {"entity_type": entity_type})
    
    async def craft(self, item: str, count: int = 1):
        """Craft item."""
        return await self.execute("craft", {"item": item, "count": count})
    
    async def get_status(self):
        """Get bot status."""
        return await self.execute("status")
    
    async def chat(self, message: str):
        """Send chat message."""
        return await self.execute("chat", {"message": message})
    
    async def protect(self, username: str, radius: int = 50, x: int = None, y: int = None, z: int = None):
        """Create a protected zone. If x,y,z not specified, uses bot's current position."""
        params = {"username": username, "radius": radius}
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        if z is not None:
            params["z"] = z
        return await self.execute("protect", params)
    
    async def list_protected_zones(self):
        """List all protected zones."""
        return await self.execute("list_protected_zones")
    
    async def get_screenshot(self) -> Optional[str]:
        """
        Capture a screenshot from visual perception.
        Returns base64-encoded JPEG image, or None if not available.
        """
        result = await self.execute("get_screenshot", timeout=10)
        if result.success and result.data:
            return result.data.get("image")
        logger.warning(f"Screenshot failed: {result.error}")
        return None
    
    # === PHASE 1: Combat Survival ===
    
    async def equip(self, item: str, slot: str = "hand"):
        """Equip item to specified slot (hand, off-hand, head, torso, legs, feet)."""
        return await self.execute("equip", {"item": item, "slot": slot})
    
    async def shield(self, activate: bool = True):
        """Activate or deactivate shield blocking."""
        return await self.execute("shield", {"activate": activate})
    
    async def sleep(self):
        """Sleep in nearby bed (skips night, sets spawn)."""
        return await self.execute("sleep")
    
    async def wake(self):
        """Wake up from bed."""
        return await self.execute("wake")
    
    # === PHASE 2: Resource Management ===
    
    async def smelt(self, input_item: str, fuel: str = "coal", count: int = 1):
        """Smelt item in nearby furnace."""
        return await self.execute("smelt", {"input": input_item, "fuel": fuel, "count": count}, timeout=120)
    
    async def store(self, item: str = None, count: int = None):
        """Store items in nearby chest."""
        params = {}
        if item:
            params["item"] = item
        if count:
            params["count"] = count
        return await self.execute("store", params)
    
    async def take(self, item: str = None, count: int = None):
        """Take items from nearby chest."""
        params = {}
        if item:
            params["item"] = item
        if count:
            params["count"] = count
        return await self.execute("take", params)
    
    async def place(self, block: str, x: int = None, y: int = None, z: int = None):
        """Place a block. If coordinates given, place there; otherwise place in front."""
        params = {"block": block}
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        if z is not None:
            params["z"] = z
        return await self.execute("place", params)
    
    # === PHASE 3: Farming & Sustainability ===
    
    async def farm(self, crop: str = "wheat", radius: int = 3):
        """Till soil and plant crops in radius."""
        return await self.execute("farm", {"crop": crop, "radius": radius}, timeout=60)
    
    async def harvest(self, radius: int = 5):
        """Harvest mature crops in radius."""
        return await self.execute("harvest", {"radius": radius}, timeout=30)
    
    async def plant(self, seed: str = "wheat_seeds", count: int = 1):
        """Plant seeds on farmland."""
        return await self.execute("plant", {"seed": seed, "count": count})
    
    async def fish(self, duration: int = 30):
        """Fish with rod for specified duration in seconds."""
        return await self.execute("fish", {"duration": duration}, timeout=duration + 10)
    
    # === PHASE 4: Location & Building ===
    
    async def save_location(self, name: str):
        """Save current position with a name."""
        return await self.execute("save_location", {"name": name})
    
    async def goto_location(self, name: str = None):
        """Navigate to a saved location. If no name, returns list of locations."""
        params = {"name": name} if name else {}
        return await self.execute("goto_location", params, timeout=120)
    
    async def copy_build(self, name: str, radius: int = 5, height: int = 10):
        """Scan and save area as a blueprint."""
        return await self.execute("copy_build", {"name": name, "radius": radius, "height": height})
    
    async def build(self, name: str, gather_resources: bool = True):
        """Build a saved blueprint. Optionally gathers missing resources first."""
        return await self.execute("build", {"name": name, "gatherResources": gather_resources}, timeout=300)
    
    async def list_locations(self):
        """Get list of saved locations."""
        return await self.execute("list_locations")
    
    async def list_blueprints(self):
        """Get list of saved blueprints."""
        return await self.execute("list_blueprints")
    
    # === PHASE 5: Co-op Mode ===
    
    async def drop(self, item: str, count: int = 1):
        """Drop item on ground."""
        return await self.execute("drop", {"item": item, "count": count})
    
    async def give(self, player: str, item: str, count: int = 1):
        """Give item to player (drop at their feet)."""
        return await self.execute("give", {"player": player, "item": item, "count": count}, timeout=60)
    
    async def find(self, block: str, go: bool = False, radius: int = 64):
        """Find block type. If go=True, navigate there."""
        return await self.execute("find", {"block": block, "go": go, "radius": radius}, timeout=60 if go else 10)
    
    async def eat(self, food: str = None):
        """Eat food item."""
        params = {"food": food} if food else {}
        return await self.execute("eat", params)
    
    async def share(self, item: str):
        """Share half of item stack with teammate."""
        return await self.execute("share", {"item": item})
    
    async def scan(self, radius: int = 32):
        """Scan for nearby valuable resources."""
        return await self.execute("scan", {"radius": radius})
    
    async def coop_mode(self, player: str, mode: str = "on"):
        """Enable co-op mode - follow player at distance and help."""
        return await self.execute("coop_mode", {"player": player, "mode": mode})
    
    @property
    def is_connected(self) -> bool:
        return self._connected
