import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.creative.autonomy import AutonomyAbility

async def main():
    print("STARTING")
    lobe = MagicMock()
    bot = MagicMock()
    bot.is_processing = False
    bot.last_interaction = 0
    bot.loop.run_in_executor = AsyncMock(side_effect=['[TOOL: start_work_session()]', None])
    bot.engine_manager.get_active_engine.return_value = MagicMock()
    bot.hippocampus.observe = AsyncMock()
    lobe.cerebrum.bot = bot
    a = AutonomyAbility(lobe)
    
    async def sleep_side(d):
        print(f"SLEEP {d}")
        if d == 10: raise asyncio.CancelledError()
        return
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        with patch("asyncio.sleep", side_effect=sleep_side):
             with patch("src.lobes.creative.autonomy.ToolRegistry.execute", new_callable=AsyncMock) as mock_tr:
                 await a.execute()
                 print(f"TOOL TR CALLS: {mock_tr.call_count}")
                 print(f"HISTORY: {a.autonomy_log_buffer}")

asyncio.run(main())
