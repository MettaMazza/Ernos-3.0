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
        self._reader_alive = False
        self._consecutive_timeouts = 0
    
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
            bufsize=1,
            start_new_session=True  # Own process group — so disconnect() can kill all children
        )
        
        # Start stderr reader for JS errors
        self._stderr_task = asyncio.create_task(self._read_stderr())
        
        self._reader_alive = True
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
        """Read stderr from Node process and forward to log.
        
        Critical for visibility: visual.js and other Node modules log
        initialization errors to stderr via console.error().
        """
        while self.process and self.process.stderr:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stderr.readline
                )
                if not line:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                # Route Visual/viewer messages at INFO so they're visible
                if '[Visual]' in stripped or '[FATAL]' in stripped:
                    logger.warning(f"NODE_STDERR: {stripped}")
                else:
                    logger.debug(f"NODE_STDERR: {stripped}")
            except Exception:
                break
    
    async def disconnect(self):
        """Stop the bot and ALL child processes (viewer, puppeteer, chrome)."""
        if self.process:
            try:
                await self.execute("disconnect", timeout=5)
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
            
            # Kill entire process tree — not just the parent
            pid = self.process.pid
            try:
                import signal
                # Kill process group to get all children (viewer, puppeteer, chrome)
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                logger.info(f"Killed process group for pid {pid}")
            except (ProcessLookupError, PermissionError, OSError) as e:
                logger.debug(f"Process group kill: {e}, falling back to terminate")
                try:
                    self.process.terminate()
                except Exception:
                    pass
            
            # Also force-kill any leftover processes on the viewer port
            try:
                import subprocess as sp
                result = sp.run(
                    ["lsof", "-ti", f":{3007}"],
                    capture_output=True, text=True, timeout=3
                )
                if result.stdout.strip():
                    stale_pids = result.stdout.strip().split('\n')
                    for p in stale_pids:
                        try:
                            os.kill(int(p), signal.SIGKILL)
                        except (ProcessLookupError, ValueError):
                            pass
                    logger.info(f"Cleaned up stale port 3007 processes: {stale_pids}")
            except Exception as e:
                logger.debug(f"Port cleanup: {e}")
            
            self.process = None
        
        if self._reader_task:
            self._reader_task.cancel()
        
        self._connected = False
        self._reader_alive = False
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
                        try:
                            if data.get("success"):
                                future.set_result(BridgeResponse(True, data.get("data")))
                            else:
                                future.set_result(BridgeResponse(False, error=data.get("error")))
                        except asyncio.InvalidStateError:
                            # Future was already cancelled/resolved by a timeout — safe to ignore
                            logger.debug(f"READER_STALE_RESPONSE | id={request_id} (future already resolved)")
                    else:
                        # Response arrived for a timed-out request — just drop it
                        logger.debug(f"READER_ORPHAN_RESPONSE | id={request_id}")
                            
            except json.JSONDecodeError as e:
                logger.debug(f"Suppressed {type(e).__name__}: {e}")
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reader error: {e} — continuing")
                continue  # Keep reading, don't kill the reader
        
        self._reader_alive = False
        logger.warning("BRIDGE_READER_STOPPED")
    
    async def execute(
        self,
        command: str,
        params: Dict = None,
        timeout: float = 60.0  # Default timeout — must be generous for navigation
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
        
        # Fail-fast if reader is dead — no point waiting for a response nobody will deliver
        if not self._reader_alive:
            logger.warning(f"BRIDGE_READER_DEAD | cmd={command} | skipping")
            return BridgeResponse(False, error="Bridge reader is dead — cannot receive responses")
        
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
            self._consecutive_timeouts = 0  # Reset on success
            return result
        except asyncio.TimeoutError:
            self.pending.pop(request_id, None)
            self._consecutive_timeouts += 1
            logger.warning(f"BRIDGE_TIMEOUT | cmd={command} | timeout={timeout}s | consecutive={self._consecutive_timeouts}")
            # Check if process died during wait
            if self.process.poll() is not None:
                logger.error(f"BRIDGE_PROCESS_DIED_DURING | cmd={command}")
                self._connected = False
            return BridgeResponse(False, error=f"Command timeout ({timeout}s)")
    
    # === High-level commands ===
    
    async def goto(self, x: float, y: float, z: float, range: int = 1):
        """Navigate to position."""
        return await self.execute("goto", {"x": x, "y": y, "z": z, "range": range}, timeout=120)
    
    async def follow(self, username: str, range: int = 3):
        """Follow a player."""
        return await self.execute("follow", {"username": username, "range": range}, timeout=30)
    
    async def stop_follow(self):
        """Stop following."""
        return await self.execute("stop_follow")
    
    async def collect(self, block_type: str, count: int = 1):
        """Collect blocks."""
        return await self.execute("collect", {"block_type": block_type, "count": count}, timeout=120)
    
    async def attack(self, entity_type: str = "hostile"):
        """Attack entity — loops until dead, up to 30s."""
        return await self.execute("attack", {"entity_type": entity_type}, timeout=35)
    
    async def craft(self, item: str, count: int = 1):
        """Craft item — may need to place table + navigate to it."""
        return await self.execute("craft", {"item": item, "count": count}, timeout=60)
    
    async def get_status(self):
        """Get bot status."""
        return await self.execute("status")
    
    async def chat(self, message: str):
        """Send chat message."""
        return await self.execute("chat", {"message": message})

    async def ping(self) -> bool:
        """Check if bridge event loop is responsive."""
        res = await self.execute("ping", timeout=5.0)
        return res.success
    
    async def protect(self, username: str, radius: int = 50, x: int = None, y: int = None, z: int = None):
        """Create a protected zone. If x,y,z not specified, uses bot's current position."""
        params = {"username": username, "radius": radius}
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        if z is not None:
            params["z"] = z
        return await self.execute("protect", params, timeout=30)
    
    async def list_protected_zones(self):
        """List all protected zones."""
        return await self.execute("list_protected_zones")
    
    async def get_screenshot(self) -> Optional[str]:
        """
        Capture a screenshot from visual perception.
        Returns base64-encoded JPEG image, or None if not available.
        """
        result = await self.execute("get_screenshot", timeout=10)
        if not result.success:
            logger.warning(f"Screenshot failed: {result.error}")
            return None
        if result.data and result.data.get("image"):
            return result.data["image"]
        # success=True but no image data — log the data for debugging
        logger.warning(f"Screenshot returned no image data: {result.data}")
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
        return await self.execute("store", params, timeout=30)
    
    async def take(self, item: str = None, count: int = None):
        """Take items from nearby chest."""
        params = {}
        if item:
            params["item"] = item
        if count:
            params["count"] = count
        return await self.execute("take", params, timeout=30)
    
    async def place(self, block: str, x: int = None, y: int = None, z: int = None):
        """Place a block. If coordinates given, place there; otherwise place in front."""
        params = {"block": block}
        if x is not None:
            params["x"] = x
        if y is not None:
            params["y"] = y
        if z is not None:
            params["z"] = z
        return await self.execute("place", params, timeout=30)
    
    # === PHASE 3: Farming & Sustainability ===
    
    async def farm(self, crop: str = "wheat", radius: int = 8):
        """Till soil and plant crops in radius."""
        return await self.execute("farm", {"crop": crop, "radius": radius}, timeout=60)
    
    async def harvest(self, radius: int = 10):
        """Harvest mature crops in radius."""
        return await self.execute("harvest", {"radius": radius}, timeout=30)
    
    async def plant(self, seed: str = "wheat_seeds", count: int = 1):
        """Plant seeds on farmland."""
        return await self.execute("plant", {"seed": seed, "count": count}, timeout=30)
    
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
    
    async def find(self, block: str, go: bool = False, radius: int = 256):
        """Find block type. If go=True, navigate there."""
        return await self.execute("find", {"block": block, "go": go, "radius": radius}, timeout=120 if go else 30)
    
    async def eat(self, food: str = None):
        """Eat food item."""
        params = {"food": food} if food else {}
        return await self.execute("eat", params)
    
    async def share(self, item: str):
        """Share half of item stack with teammate."""
        return await self.execute("share", {"item": item})
    
    async def scan(self, radius: int = 128):
        """Scan for nearby valuable resources."""
        return await self.execute("scan", {"radius": radius})
    
    async def coop_mode(self, player: str, mode: str = "on"):
        """Enable co-op mode - follow player at distance and help."""
        return await self.execute("coop_mode", {"player": player, "mode": mode})
    
    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        # Reader died but process still alive = zombie bridge
        if not self._reader_alive:
            logger.warning("BRIDGE_ZOMBIE | reader dead but process alive")
            return False
        # Too many consecutive timeouts = bridge unresponsive
        if self._consecutive_timeouts >= 5:
            logger.warning(f"BRIDGE_UNRESPONSIVE | {self._consecutive_timeouts} consecutive timeouts")
            return False
        return True
