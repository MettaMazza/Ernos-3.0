"""
Global reference to the active ErnosBot instance.
Used by Tools to access the Cerebrum/Lobes.
"""
import contextvars

bot = None
active_message = contextvars.ContextVar("active_message", default=None)
active_channel = contextvars.ContextVar("active_channel", default=None)

# System Awareness
from collections import deque
recent_errors = deque(maxlen=10)
activity_log = deque(maxlen=100) # Global Event Stream


