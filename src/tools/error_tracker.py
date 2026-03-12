"""
Error Tracker - Centralized error logging for tools, agents, and lobes.
All errors are logged to a structured JSON file for debugging and tracking.
"""
import logging
import json
import os
import threading
from datetime import datetime
from typing import Optional, Any
from pathlib import Path

logger = logging.getLogger("ErrorTracker")

class ErrorTracker:
    """
    Centralized error tracking for Ernos.
    Logs all tool failures, agent errors, and lobe issues to a structured file.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.log_dir = Path("./logs/errors")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "error_trace.jsonl"
        self._initialized = True
        logger.info(f"ErrorTracker initialized. Logging to: {self.log_file}")
    
    def log_error(
        self,
        category: str,  # "TOOL", "AGENT", "LOBE", "ENGINE"
        source: str,    # Tool name, agent class, lobe name
        error_type: str,  # Exception type or error code
        error_message: str,
        context: Optional[dict] = None,
        traceback_str: Optional[str] = None,
        user_id: Optional[str] = None,
        request_scope: Optional[str] = None
    ):
        """
        Log a structured error entry.
        
        Args:
            category: TOOL, AGENT, LOBE, or ENGINE
            source: The name of the failing component (e.g., "consult_science_lobe")
            error_type: The exception class or error code (e.g., "SyntaxError")
            error_message: The error message string
            context: Optional dict with additional context (input, params, etc.)
            traceback_str: Optional full traceback
            user_id: Optional user ID for scoped debugging
            request_scope: Optional scope (PUBLIC, PRIVATE, CORE)
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "source": source,
            "error_type": error_type,
            "error_message": str(error_message)[:5000],  # Truncate long messages
            "context": context or {},
            "traceback": traceback_str[:10000] if traceback_str else None,
            "user_id": user_id,
            "scope": request_scope
        }
        
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write error log: {e}")
        
        # Also log to standard Python logger for visibility
        logger.error(f"[{category}] {source}: {error_type} - {error_message}")
    
    def log_tool_failure(
        self,
        tool_name: str,
        error: Exception,
        params: Optional[dict] = None,
        user_id: Optional[str] = None
    ):
        """Convenience method for tool failures."""
        import traceback as tb
        self.log_error(
            category="TOOL",
            source=tool_name,
            error_type=type(error).__name__,
            error_message=str(error),
            context={"params": params} if params else None,
            traceback_str=tb.format_exc(),
            user_id=user_id
        )
    
    def log_lobe_failure(
        self,
        lobe_name: str,
        error: Exception,
        instruction: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Convenience method for lobe failures."""
        import traceback as tb
        self.log_error(
            category="LOBE",
            source=lobe_name,
            error_type=type(error).__name__,
            error_message=str(error),
            context={"instruction": instruction[:500]} if instruction else None,
            traceback_str=tb.format_exc(),
            user_id=user_id
        )
    
    def log_agent_failure(
        self,
        agent_name: str,
        error: Exception,
        input_text: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Convenience method for agent failures."""
        import traceback as tb
        self.log_error(
            category="AGENT",
            source=agent_name,
            error_type=type(error).__name__,
            error_message=str(error),
            context={"input": input_text[:500]} if input_text else None,
            traceback_str=tb.format_exc(),
            user_id=user_id
        )
    
    def get_recent_errors(self, count: int = 20, category: Optional[str] = None) -> list:
        """
        Retrieve recent errors from the log.
        
        Args:
            count: Number of recent errors to retrieve
            category: Optional filter by category (TOOL, LOBE, AGENT, ENGINE)
        
        Returns:
            List of error dicts, most recent first
        """
        errors = []
        try:
            if not self.log_file.exists():
                return []
            
            with open(self.log_file, "r") as f:
                lines = f.readlines()
            
            # Parse from end (most recent)
            for line in reversed(lines):
                if len(errors) >= count:
                    break
                try:
                    entry = json.loads(line.strip())
                    if category is None or entry.get("category") == category:
                        errors.append(entry)
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to read error log: {e}")
        
        return errors
    
    def get_error_summary(self) -> dict:
        """
        Get a summary of errors by category and source.
        Returns counts for quick diagnostics.
        """
        from collections import defaultdict
        summary = {
            "by_category": defaultdict(int),
            "by_source": defaultdict(int),
            "total": 0,
            "last_24h": 0
        }
        
        try:
            if not self.log_file.exists():
                return summary
            
            cutoff = datetime.now().timestamp() - 86400  # 24h ago
            
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        summary["by_category"][entry.get("category", "UNKNOWN")] += 1
                        summary["by_source"][entry.get("source", "UNKNOWN")] += 1
                        summary["total"] += 1
                        
                        # Check if in last 24h
                        ts = datetime.fromisoformat(entry["timestamp"]).timestamp()
                        if ts > cutoff:
                            summary["last_24h"] += 1
                    except Exception as e:
                        logger.warning(f"Suppressed {type(e).__name__}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to generate error summary: {e}")
        
        return summary


# Singleton instance
error_tracker = ErrorTracker()
