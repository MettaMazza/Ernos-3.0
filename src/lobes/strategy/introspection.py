"""
Introspection Module — v3.5 Photosynthesis.

Architectural self-reflection. Ernos can analyze its own
cognitive architecture, identify bottlenecks, and report
on system health trends.
"""
import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from src.core.data_paths import data_dir

logger = logging.getLogger("Lobe.Strategy.Introspection")


class IntrospectionEngine:
    """
    Self-reflective architectural analysis engine.
    
    Capabilities:
    - Analyze lobe utilization patterns
    - Identify underused or overloaded components
    - Track response latency trends
    - Monitor memory growth
    - Generate architecture health reports
    - Suggest optimization opportunities
    
    No auto-modification — introspection is read-only.
    All suggestions go through SkillForge/PromptTuner approval.
    """
    
    REPORT_DIR = data_dir() / "system/introspection"
    METRICS_FILE = data_dir() / "system/introspection/metrics.json"
    
    def __init__(self):
        self._metrics: Dict[str, Any] = self._load_metrics()
    
    def _load_metrics(self) -> Dict[str, Any]:
        """Load historical metrics."""
        if self.METRICS_FILE.exists():
            try:
                return json.loads(self.METRICS_FILE.read_text())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
        return {
            "lobe_calls": {},
            "response_times": [],
            "memory_sizes": [],
            "error_counts": {},
            "snapshots": []
        }
    
    def _save_metrics(self):
        """Persist metrics."""
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        # Cap historical data
        self._metrics["response_times"] = self._metrics["response_times"][-1000:]
        self._metrics["memory_sizes"] = self._metrics["memory_sizes"][-100:]
        self._metrics["snapshots"] = self._metrics["snapshots"][-50:]
        self.METRICS_FILE.write_text(json.dumps(self._metrics, indent=2))
    
    def record_lobe_call(self, lobe_name: str, duration_ms: float = 0):
        """Track how often each lobe is called."""
        if lobe_name not in self._metrics["lobe_calls"]:
            self._metrics["lobe_calls"][lobe_name] = {"count": 0, "total_ms": 0}
        
        self._metrics["lobe_calls"][lobe_name]["count"] += 1
        self._metrics["lobe_calls"][lobe_name]["total_ms"] += duration_ms
        self._save_metrics()
    
    def record_response_time(self, duration_ms: float, context: str = ""):
        """Record a response latency measurement."""
        # Use explicit string construction to satisfy strict slicer
        s_context = str(context)
        self._metrics["response_times"].append({
            "ms": duration_ms,
            "context": s_context[slice(0, 500)],  # type: ignore
            "timestamp": datetime.now().isoformat()
        })
        self._save_metrics()
    
    def record_error(self, component: str, error_type: str):
        """Track error frequency per component."""
        key = f"{component}:{error_type}"
        self._metrics["error_counts"][key] = self._metrics["error_counts"].get(key, 0) + 1
        self._save_metrics()
    
    def take_snapshot(self) -> Dict[str, Any]:
        """
        Take a system health snapshot.
        
        Captures current memory sizes, file counts, and
        component status for trend analysis.
        """
        snapshot: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "memory_usage": {}
        }
        
        # Memory directory sizes
        memory_dir = data_dir()
        if memory_dir.exists():
            for sub in ["users", "system", "core"]:
                sub_dir = memory_dir / sub
                if sub_dir.exists():
                    total = sum(f.stat().st_size for f in sub_dir.rglob("*") if f.is_file())
                    # Explicit cast for linter
                    mem_usage: Dict[str, int] = snapshot["memory_usage"]  # type: ignore
                    mem_usage[sub] = total
        
        # Count users
        users_dir = data_dir() / "users"
        if users_dir.exists():
            snapshot["user_count"] = len([d for d in users_dir.iterdir() if d.is_dir()])
        else:
            snapshot["user_count"] = 0
        
        # Lobe utilization
        snapshot["lobe_utilization"] = dict(self._metrics["lobe_calls"])
        
        self._metrics["snapshots"].append(snapshot)
        self._save_metrics()
        
        logger.info("Introspection: Health snapshot captured")
        return snapshot
    
    def get_health_report(self) -> str:
        """
        Generate a human-readable health report.
        
        Returns markdown-formatted report.
        """
        lines = ["## System Health Report"]
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
        
        # Lobe utilization
        if self._metrics["lobe_calls"]:
            lines.append("### Lobe Utilization")
            sorted_lobes = sorted(
                self._metrics["lobe_calls"].items(),
                key=lambda x: x[1]["count"], reverse=True
            )
            # Explicit list cast/slice for linter
            top_lobes: List = list(sorted_lobes)
            for name, data in top_lobes[:10]:  # type: ignore
                avg_ms = data["total_ms"] / data["count"] if data["count"] > 0 else 0
                lines.append(f"- **{name}**: {data['count']} calls, avg {avg_ms:.0f}ms")
        
        # Response times
        if self._metrics["response_times"]:
            times = [r["ms"] for r in self._metrics["response_times"][-100:]]
            avg = sum(times) / len(times)
            p95 = sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else avg
            lines.append(f"\n### Response Latency")
            lines.append(f"- Average: {avg:.0f}ms")
            lines.append(f"- P95: {p95:.0f}ms")
            lines.append(f"- Sample size: {len(times)}")
        
        # Errors
        if self._metrics["error_counts"]:
            lines.append(f"\n### Error Summary")
            sorted_errors = sorted(
                self._metrics["error_counts"].items(),
                key=lambda x: x[1], reverse=True
            )
            top_errors: List = list(sorted_errors)
            for error, count in top_errors[:10]:  # type: ignore
                lines.append(f"- {error}: {count}")
        
        # Memory
        if self._metrics["snapshots"]:
            latest = self._metrics["snapshots"][-1]
            lines.append(f"\n### Memory Usage")
            for area, size in latest.get("memory_usage", {}).items():
                size_mb = size / (1024 * 1024)
                lines.append(f"- {area}: {size_mb:.1f} MB")
            lines.append(f"- Active users: {latest.get('user_count', 0)}")
        
        return "\n".join(lines)
    
    def identify_bottlenecks(self) -> List[Dict]:
        """
        Identify potential performance bottlenecks.
        
        Returns list of issues with severity and suggestions.
        """
        issues = []
        
        # Slow lobes
        for name, data in self._metrics["lobe_calls"].items():
            if data["count"] > 0:
                avg_ms = data["total_ms"] / data["count"]
                if avg_ms > 5000:  # > 5 seconds average
                    issues.append({
                        "component": name,
                        "severity": "high",
                        "issue": f"Slow response: {avg_ms:.0f}ms average",
                        "suggestion": "Consider caching or breaking into async steps"
                    })
        
        # Error-prone components
        for error_key, count in self._metrics["error_counts"].items():
            if count > 10:
                issues.append({
                    "component": error_key.split(":")[0],
                    "severity": "medium",
                    "issue": f"Frequent errors: {count} occurrences",
                    "suggestion": "Review error handling and add resilience"
                })
        
        return issues
    
    def get_summary(self) -> str:
        """Quick one-line summary."""
        lobes = len(self._metrics["lobe_calls"])
        snapshots = len(self._metrics["snapshots"])
        errors = sum(self._metrics["error_counts"].values())
        return f"Introspection: {lobes} lobes tracked, {snapshots} snapshots, {errors} errors logged"
