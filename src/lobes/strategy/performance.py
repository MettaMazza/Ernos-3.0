from ..base import BaseAbility
import logging
import time
import psutil

logger = logging.getLogger("Lobe.Strategy.Performance")

class PerformanceAbility(BaseAbility):
    """
    The Performance Lobe monitors system health.
    """
    def __init__(self, lobe):
        super().__init__(lobe)
    
    async def execute(self, instruction: str = "status") -> str:
        logger.info(f"Performance monitor checking: {instruction}")
        
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        
        # Get uptime from Bot via Cerebrum
        uptime = "Unknown"
        if self.lobe and self.lobe.cerebrum and self.lobe.cerebrum.bot:
            elapsed = time.time() - self.lobe.cerebrum.bot.start_time
            uptime = f"{elapsed / 3600:.2f} hours"
            
        return (
            f"### System Diagnostics\n"
            f"- **CPU Load**: {cpu}%\n"
            f"- **Memory Usage**: {mem}%\n"
            f"- **Uptime**: {uptime}\n"
            f"- **Status**: {'HEALTHY' if cpu < 80 else 'LOAD_HIGH'}"
        )
