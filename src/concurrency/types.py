"""
Lane types and policies for the Lane Queue system.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Coroutine, Optional
import uuid
import time


class LanePriority(Enum):
    """Task priority levels."""
    CRITICAL = 1
    NORMAL = 2
    BACKGROUND = 3


@dataclass
class LanePolicy:
    """
    Configuration policy for a lane.
    
    Controls how tasks are executed within this lane.
    """
    max_parallel: int = 1          # Default=1 means serial execution
    timeout_seconds: int = 120     # Per-task timeout
    retry_on_failure: bool = False # Auto-retry on exception
    max_queue_depth: int = 10      # Backpressure threshold


@dataclass
class LaneTask:
    """
    A task submitted to a lane for execution.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    lane_name: str = ""
    priority: LanePriority = LanePriority.NORMAL
    user_id: str = ""
    channel_id: str = ""
    created_at: float = field(default_factory=time.time)
    status: str = "queued"   # queued, running, done, failed, cancelled
    result: Any = None
    error: Optional[str] = None

    def __repr__(self):
        return f"Task({self.id} lane={self.lane_name} status={self.status} user={self.user_id})"
