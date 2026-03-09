"""
Skill Sandbox — Execution boundary for skill invocations.

Enforces tool whitelisting, scope gates, execution logging,
and rate limiting to prevent misuse of user-defined skills.
"""
import logging
import time
from typing import Optional

from src.skills.types import SkillDefinition, SkillExecutionResult

logger = logging.getLogger("Skills.Sandbox")


class SkillSandbox:
    """
    Enforces security boundaries when executing skills.
    
    Unlike OpenClaw's ClawHub, skills in Ernos CANNOT execute arbitrary code.
    They are natural-language instructions that guide the LLM's tool usage
    within a whitelisted boundary. This sandbox exists as a hard gate.
    """

    # Maximum skill executions per user per hour
    RATE_LIMIT_PER_HOUR = 30

    def __init__(self):
        self._execution_log = []       # List of (timestamp, user_id, skill_name)
        self._rate_tracker = {}        # {user_id: [timestamps]}

    def check_permissions(
        self,
        skill: SkillDefinition,
        user_id: str,
        request_scope: str,
        requested_tools: Optional[list] = None,
    ) -> tuple:
        """
        Validate that this skill execution is permitted.
        
        Checks:
        1. Scope gate — request scope must meet or exceed skill's required scope
        2. Tool whitelist — requested tools must be in skill's allowed_tools
        3. Rate limit — user hasn't exceeded hourly limit
        
        Args:
            skill: The skill being invoked
            user_id: Who is invoking it
            request_scope: The scope of the request (CORE, PRIVATE, PUBLIC)
            requested_tools: Tools the skill wants to invoke (if known)
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # 1. Scope Gate
        scope_hierarchy = {"CORE": 1, "PRIVATE": 2, "PUBLIC": 3, "OPEN": 4}
        request_level = scope_hierarchy.get(request_scope, 4)
        skill_level = scope_hierarchy.get(skill.scope, 3)

        if request_level > skill_level:
            reason = (
                f"Scope denied: skill '{skill.name}' requires {skill.scope} scope, "
                f"but request has {request_scope} scope"
            )
            logger.warning(f"SECURITY: {reason}")
            return False, reason

        # 2. Tool Whitelist
        if requested_tools:
            blocked = [t for t in requested_tools if t not in skill.allowed_tools]
            if blocked:
                reason = (
                    f"Tool denied: skill '{skill.name}' tried to invoke "
                    f"non-whitelisted tools: {blocked}"
                )
                logger.warning(f"SECURITY: {reason}")
                return False, reason

        # 3. Rate Limit
        now = time.time()
        one_hour_ago = now - 3600

        if user_id not in self._rate_tracker:
            self._rate_tracker[user_id] = []

        # Prune old entries
        self._rate_tracker[user_id] = [
            ts for ts in self._rate_tracker[user_id] if ts > one_hour_ago
        ]

        if len(self._rate_tracker[user_id]) >= self.RATE_LIMIT_PER_HOUR:
            reason = (
                f"Rate limit exceeded: user {user_id} has made "
                f"{len(self._rate_tracker[user_id])} skill calls in the last hour "
                f"(limit: {self.RATE_LIMIT_PER_HOUR})"
            )
            logger.warning(f"SECURITY: {reason}")
            return False, reason

        return True, "OK"

    def log_execution(
        self,
        skill: SkillDefinition,
        user_id: str,
        scope: str,
        tools_used: list,
        success: bool,
    ) -> None:
        """
        Record a skill execution for audit trail.
        
        Args:
            skill: The skill that was executed
            user_id: Who executed it
            scope: The scope context
            tools_used: Which tools were actually invoked
            success: Whether execution completed without error
        """
        now = time.time()

        entry = {
            "timestamp": now,
            "skill_name": skill.name,
            "user_id": user_id,
            "scope": scope,
            "tools_used": tools_used,
            "success": success,
            "skill_version": skill.version,
            "skill_checksum": skill.checksum[:12],  # Short hash for log readability
        }

        self._execution_log.append(entry)

        # Track for rate limiting
        if user_id not in self._rate_tracker:
            self._rate_tracker[user_id] = []
        self._rate_tracker[user_id].append(now)

        logger.info(
            f"Skill execution logged: {skill.name} by {user_id} "
            f"(scope={scope}, tools={tools_used}, success={success})"
        )

    def execute(
        self,
        skill: SkillDefinition,
        context: str,
        user_id: str,
        scope: str,
    ) -> SkillExecutionResult:
        """
        Execute a skill within the sandbox.
        
        NOTE: This does NOT run arbitrary code. It returns the skill's
        instructions formatted for injection into the LLM's context.
        The LLM then uses the instructions to guide its tool usage,
        which is still governed by the ToolRegistry's own security.
        
        Args:
            skill: The skill to execute
            context: Additional context for the LLM
            user_id: Who is requesting execution
            scope: The privacy scope
            
        Returns:
            SkillExecutionResult with the formatted instructions
        """
        # Permission check
        allowed, reason = self.check_permissions(skill, user_id, scope)
        if not allowed:
            return SkillExecutionResult(
                success=False,
                output="",
                error=reason,
                skill_name=skill.name,
                user_id=user_id,
                scope=scope,
            )

        # Build the formatted instructions block with structured boundary
        tool_list = ", ".join(skill.allowed_tools) if skill.allowed_tools else "none"
        instructions_block = (
            f"[SKILL EXECUTION: {skill.name} v{skill.version}]\n"
            f"[AUTHOR: {skill.author}]\n"
            f"[ALLOWED TOOLS: {tool_list}]\n"
            f"[CONTEXT: {context}]\n\n"
            f"INSTRUCTIONS:\n{skill.instructions}\n\n"
            f"[END SKILL: {skill.name}]\n"
            f"IMPORTANT: You may ONLY use the tools listed in ALLOWED TOOLS above. "
            f"Do not invoke any other tools during this skill execution.\n\n"
            # Structured boundary for programmatic enforcement
            f"[SKILL_BOUNDARY_START]\n"
            f"ACTIVE_SKILL={skill.name}\n"
            f"ALLOWED_TOOLS={','.join(skill.allowed_tools)}\n"
            f"CHECKSUM={skill.checksum[:12]}\n"
            f"UNAUTHORIZED_TOOL_CALLS_WILL_BE_BLOCKED=TRUE\n"
            f"[SKILL_BOUNDARY_END]"
        )

        # Log the execution
        self.log_execution(
            skill=skill,
            user_id=user_id,
            scope=scope,
            tools_used=[],  # Tools will be tracked by ToolRegistry during actual execution
            success=True,
        )

        return SkillExecutionResult(
            success=True,
            output=instructions_block,
            skill_name=skill.name,
            user_id=user_id,
            scope=scope,
        )

    def verify_tool_compliance(
        self, skill: SkillDefinition, tools_used: list
    ) -> list:
        """
        Post-execution audit: check if tools used during skill execution
        were all in the skill's allowed_tools whitelist.
        
        Returns list of unauthorized tools used (empty = compliant).
        """
        if not skill.allowed_tools:
            return []  # No whitelist = unrestricted (system skills only)

        violations = [t for t in tools_used if t not in skill.allowed_tools]

        if violations:
            logger.warning(
                f"SECURITY: Skill '{skill.name}' used unauthorized tools: {violations}. "
                f"Allowed: {skill.allowed_tools}"
            )

        return violations

    def get_audit_log(self, limit: int = 50) -> list:
        """Return the most recent execution log entries."""
        return self._execution_log[-limit:]
