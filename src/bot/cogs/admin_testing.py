"""
Admin Testing Cog — /testall command.

Parses MASTER_SYSTEM_TEST.md and auto-executes all tool calls through
the real ToolRegistry, collecting results and generating a diagnostic report.
"""
import discord
from discord.ext import commands
from discord import app_commands
import re
import time
import logging
import asyncio
from typing import Optional
from config import settings

logger = logging.getLogger("AdminCogs.Testing")


# Tests that are documentation-only or require real targets
SKIP_PATTERNS = [
    "Describe ",  # Documentation-only items
]

# Tests that are too heavy or require specific infrastructure
HEAVY_TESTS = {
    "generate_video",      # GPU-expensive
    "generate_image",      # GPU-expensive
    "generate_music",      # GPU-expensive
    "browse_interactive",  # Requires headless browser
    "start_game",          # Requires Minecraft
    "game_command",        # Requires active game
    "stop_game",           # Requires active game
    "timeout_user",        # Requires real target
    "send_direct_message", # Would DM someone
    "create_thread_for_user",  # Would create real thread
    "escalate_ticket",     # Would create real ticket
}


def _parse_test_file(path: str) -> list:
    """
    Parse MASTER_SYSTEM_TEST.md into executable test entries.
    
    Returns list of dicts: {
        "number": int,
        "phase": str,
        "raw": str,
        "tool_name": str or None,
        "args": dict,
        "skip": bool,
        "skip_reason": str or None,
    }
    """
    tests = []
    current_phase = "UNKNOWN"
    
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    
    for line in lines:
        line = line.strip()
        
        # Track phase headers
        phase_match = re.match(r"=== (PHASE \d+: .+?) ===", line)
        if phase_match:
            current_phase = phase_match.group(1)
            continue
        
        # Match test lines: "N. tool_name arg1=val1 arg2=val2"
        test_match = re.match(r"(\d+)\.\s+(.+)", line)
        if not test_match:
            continue
        
        number = int(test_match.group(1))
        raw = test_match.group(2).strip()
        
        # Check if it's a skip (Describe or Verify)
        skip = False
        skip_reason = None
        for pattern in SKIP_PATTERNS:
            if raw.startswith(pattern):
                skip = True
                skip_reason = "Documentation-only"
                break
        
        # Check for Verify lines (manual verification)
        if raw.startswith("Verify "):
            skip = True
            skip_reason = "Manual verification required"
        
        # Parse tool_name and args
        tool_name = None
        args = {}
        
        if not skip:
            # Parse: tool_name key=value key="value" key=value
            tool_match = re.match(r"(\w+)\s*(.*)", raw)
            if tool_match:
                tool_name = tool_match.group(1)
                args_str = tool_match.group(2)
                
                # Parse key=value pairs
                # Handle both key=value and key="value with spaces"
                for m in re.finditer(r'(\w+)=("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^\s]+)', args_str):
                    key = m.group(1)
                    val = m.group(2)
                    # Strip quotes
                    if (val.startswith('"') and val.endswith('"')) or \
                       (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    # Try to convert to appropriate type
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    else:
                        try:
                            val = int(val)
                        except ValueError:
                            try:
                                val = float(val)
                            except ValueError as e:
                                logger.debug(f"Suppressed {type(e).__name__}: {e}")
                    args[key] = val
                
                # Check if this tool is heavy
                if tool_name in HEAVY_TESTS:
                    skip = True
                    skip_reason = f"Resource-heavy ({tool_name})"
        
        tests.append({
            "number": number,
            "phase": current_phase,
            "raw": raw,
            "tool_name": tool_name,
            "args": args,
            "skip": skip,
            "skip_reason": skip_reason,
        })
    
    return tests


class AdminTesting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.author.id in settings.ADMIN_IDS

    @commands.command(name="testall")
    async def testall(self, ctx):
        """
        Run all system tests from MASTER_SYSTEM_TEST.md.
        Auto-executes tool calls through the real ToolRegistry and reports results.
        """
        from src.tools.registry import ToolRegistry

        test_file = "MASTER_SYSTEM_TEST.md"
        tests = _parse_test_file(test_file)
        
        if not tests:
            await ctx.send("❌ Could not parse MASTER_SYSTEM_TEST.md or file not found.")
            return
        
        await ctx.send(
            f"🧪 **MASTER SYSTEM TEST v4.0** — Starting {len(tests)} tests...\n"
            f"Heavy/manual tests will be skipped. Stand by."
        )
        
        results = []
        phase_results = {}
        current_phase = None
        executed = 0
        skipped = 0
        passed = 0
        failed = 0
        warned = 0
        
        start_time = time.time()
        
        for test in tests:
            phase = test["phase"]
            if phase != current_phase:
                current_phase = phase
                if phase not in phase_results:
                    phase_results[phase] = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
            
            if test["skip"]:
                skipped += 1
                phase_results[phase]["skip"] += 1
                results.append({
                    "number": test["number"],
                    "phase": phase,
                    "tool": test["tool_name"] or "N/A",
                    "status": "SKIP",
                    "reason": test["skip_reason"],
                    "time_ms": 0,
                })
                continue
            
            # Execute the tool
            tool_name = test["tool_name"]
            tool = ToolRegistry.get_tool(tool_name)
            
            if not tool:
                failed += 1
                phase_results[phase]["fail"] += 1
                results.append({
                    "number": test["number"],
                    "phase": phase,
                    "tool": tool_name,
                    "status": "FAIL",
                    "reason": f"Tool '{tool_name}' not found in registry",
                    "time_ms": 0,
                })
                continue
            
            # Execute with timing
            t0 = time.time()
            try:
                result = await ToolRegistry.execute(
                    tool_name,
                    user_id="SYSTEM",
                    request_scope="CORE",
                    bot=self.bot,
                    **test["args"]
                )
                elapsed_ms = (time.time() - t0) * 1000
                executed += 1
                
                # Determine status
                result_str = str(result) if result else ""
                if result is None or result_str.startswith("Error") or result_str.startswith("❌"):
                    status = "WARN"
                    warned += 1
                    phase_results[phase]["warn"] += 1
                else:
                    status = "OK"
                    passed += 1
                    phase_results[phase]["ok"] += 1
                
                results.append({
                    "number": test["number"],
                    "phase": phase,
                    "tool": tool_name,
                    "status": status,
                    "reason": result_str[:200] if result_str else "No output",
                    "time_ms": elapsed_ms,
                })
                
            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000
                executed += 1
                failed += 1
                phase_results[phase]["fail"] += 1
                results.append({
                    "number": test["number"],
                    "phase": phase,
                    "tool": tool_name,
                    "status": "FAIL",
                    "reason": f"{type(e).__name__}: {str(e)[:150]}",
                    "time_ms": elapsed_ms,
                })
            
            # Yield to event loop every 5 tests
            if executed % 5 == 0:
                await asyncio.sleep(0.1)
        
        total_time = time.time() - start_time
        
        # Build report
        report = self._build_report(
            results, phase_results,
            executed, skipped, passed, failed, warned,
            total_time
        )
        
        # Send report
        if len(report) > 1900:
            # Send as file
            import io
            file = discord.File(
                io.BytesIO(report.encode("utf-8")),
                filename="system_test_report.md"
            )
            await ctx.send(
                f"🧪 **Test Complete**: {passed}✅ {warned}⚠️ {failed}❌ {skipped}⏭️ "
                f"({total_time:.1f}s)",
                file=file
            )
        else:
            await ctx.send(report)
        
        # Also pass to LLM for natural language summary
        try:
            from src.engines.cognition import CognitionEngine
            engine = CognitionEngine(self.bot)
            summary_prompt = (
                f"Analyze this system test report and give a brief, grounded summary. "
                f"Distinguish between real infrastructure problems (e.g. broken tools, "
                f"failed connections) and minor diagnostic noise (e.g. syntax mismatches, "
                f"missing empty directories, correct scope rejections). "
                f"Be proportional — a 95% pass rate is healthy, not 'degraded'. "
                f"Focus on what IS working and only flag genuinely broken systems:\n\n{report}"
            )
            summary = await engine.think(
                prompt=summary_prompt,
                user_id="SYSTEM",
                complexity="LOW",
            )
            if summary:
                await ctx.send(f"**🤖 LLM Analysis:**\n{summary[:1900]}")
        except Exception as e:
            logger.warning(f"LLM summary failed: {e}")

    def _build_report(self, results, phase_results, executed, skipped, passed, failed, warned, total_time):
        """Build the markdown test report."""
        # Overall status — proportional, not binary
        total_actionable = passed + failed + warned  # Exclude skips
        if total_actionable == 0:
            overall = "NO_DATA"
        else:
            fail_ratio = failed / total_actionable
            if fail_ratio > 0.25:
                overall = "CRITICAL"
            elif fail_ratio > 0.10:
                overall = "DEGRADED"
            elif failed > 0:
                overall = "OPERATIONAL (MINOR ISSUES)"
            elif warned > total_actionable * 0.15:
                overall = "OPERATIONAL (WARNINGS)"
            else:
                overall = "OPERATIONAL"
        
        lines = [
            "# 🧪 ERNOS SYSTEM TEST REPORT",
            f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration**: {total_time:.1f}s",
            f"**Overall**: **{overall}**",
            "",
            "## Phase Summary",
            "",
            "| # | System | OK | WARN | FAIL | SKIP |",
            "|---|--------|:-:|:----:|:----:|:----:|",
        ]
        
        for i, (phase, counts) in enumerate(phase_results.items(), 1):
            phase_short = phase.replace("PHASE ", "").split(":", 1)[-1].strip() if ":" in phase else phase
            lines.append(
                f"| {i} | {phase_short} | {counts['ok']} | {counts['warn']} | {counts['fail']} | {counts['skip']} |"
            )
        
        lines.extend([
            "",
            f"**EXECUTED**: {executed}/{executed + skipped}",
            f"**PASSED**: {passed}  |  **WARNED**: {warned}  |  **FAILED**: {failed}  |  **SKIPPED**: {skipped}",
            "",
        ])
        
        # Failed tests detail
        failures = [r for r in results if r["status"] == "FAIL"]
        if failures:
            lines.extend(["## ❌ Failures", ""])
            for f in failures:
                lines.append(f"- **#{f['number']}** `{f['tool']}`: {f['reason']}")
        
        # Warned tests detail
        warns = [r for r in results if r["status"] == "WARN"]
        if warns:
            lines.extend(["", "## ⚠️ Warnings", ""])
            for w in warns:
                lines.append(f"- **#{w['number']}** `{w['tool']}`: {w['reason'][:100]}")
        
        # Slow tests
        slow = sorted(
            [r for r in results if r["time_ms"] > 2000 and r["status"] != "SKIP"],
            key=lambda r: r["time_ms"],
            reverse=True
        )[:5]
        if slow:
            lines.extend(["", "## 🐌 Slow Tests (>2s)", ""])
            for s in slow:
                lines.append(f"- **#{s['number']}** `{s['tool']}`: {s['time_ms']:.0f}ms")
        
        return "\n".join(lines)


async def setup(bot):
    await bot.add_cog(AdminTesting(bot))
