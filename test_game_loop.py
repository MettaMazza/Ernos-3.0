import asyncio
from unittest.mock import MagicMock, Mock, patch, AsyncMock
import sys

from src.gaming.agent import GamingAgent

async def run_test():
    agent = GamingAgent("dummy_bot")
    agent.is_running = True
    agent.bridge = MagicMock()
    agent.bridge.is_connected = True
    
    agent._precognition_queue = [
        {"command": "precog_action", "params": {"action": "collect stone"}},
        {"command": "precog_action", "params": {"action": "collect stone"}},
        {"command": "precog_action", "params": {"action": "collect stone"}},
        {"command": "precog_action", "params": {"action": "collect stone"}}
    ]
    agent._following_player = None
    agent._pending_chats = [{"username": "mazz", "message": "collect the resources!"}]
    
    call_count = [0]
    async def observe_chaining():
        call_count[0] += 1
        if call_count[0] >= 2:
            agent.is_running = False
        print(f"[DEBUG] observe_chaining. len(chats): {len(agent._pending_chats)}")
        return {"health": 20, "food": 20, "position": {"x": 0, "y": 64, "z": 0}, "hostiles_nearby": False, "nearby_entities": []}

    agent._observe = observe_chaining
    
    real_sleep = asyncio.sleep
    async def yielding_act(*args, **kwargs):
        print(f"[DEBUG] yielding_act called with args={args}. len(chats): {len(agent._pending_chats)}")
        await real_sleep(0.01)
        return True
    
    agent._act = yielding_act
    
    async def fast_think(state):
        print("[DEBUG] fast_think running")
        return (["follow mazz"], [{"command": "precog_action", "params": {"action": "place dirt"}}])
        
    agent._think = fast_think
    agent._precognition_to_chain = Mock(return_value=[{"command": "precog_action", "params": {"action": "place dirt"}}])
    
    async def mock_sleep_yield(seconds):
        print(f"[DEBUG] mock_sleep_yield({seconds})")
        await real_sleep(0)

    with patch("asyncio.sleep", side_effect=mock_sleep_yield):
        with patch("src.gaming.agent.log_embodiment"):
            await agent._game_loop()

if __name__ == "__main__":
    asyncio.run(run_test())
