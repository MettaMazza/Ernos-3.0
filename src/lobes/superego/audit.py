import logging
from ..base import BaseAbility

logger = logging.getLogger("Lobe.Superego.Audit")

class AuditAbility(BaseAbility):
    """
    The Internal Affairs Division.
    Audits Bot responses for Sycophancy and Hallucinations by comparing
    against actual tool execution outputs.
    """
    async def audit_response(self, user_msg: str, bot_msg: str, tool_outputs: list, session_history: list = None, system_context: str = None, images: list = None, conversation_context: str = None) -> dict:
        """
        Checks if the bot is lying about success or being sycophantic.
        Returns: {'allowed': bool, 'reason': str}
        """
        if not bot_msg: return {"allowed": True}
        
        # 1. Format Current Turn Tool Context
        current_context = "NO TOOLS EXECUTED THIS TURN."
        if tool_outputs:
            current_context = "\n".join([f"- {t.get('tool')}: {str(t.get('output'))[:200]}" for t in tool_outputs])
        
        # 2. Format Session History (last 20 tools from previous turns)
        history_context = ""
        if session_history and len(session_history) > len(tool_outputs):
            # Get tools from PREVIOUS turns (exclude current)
            prev_tools = session_history[:-len(tool_outputs)] if tool_outputs else session_history
            prev_tools = prev_tools[-20:]  # Last 20 from history
            if prev_tools:
                history_context = "\n".join([f"- [{t.get('timestamp', 'earlier')}] {t.get('tool')}: {str(t.get('output'))[:100]}" for t in prev_tools])
        
        # 3. Full trusted system context — passed from code, cannot be spoofed by user.
        #    Contains identity, scope, persona, goals, grounding pulse, backup data.
        trusted_context = system_context if system_context else "NONE"
        
        # 4. Add Native Multimodal Vision Context
        vision_context = "NO IMAGES PROVIDED."
        if images and len(images) > 0:
            vision_context = f"NATIVE MULTIMODAL VISION ACTIVE: {len(images)} image(s) passed directly to the model. The AI can analyze images without vision tool calls."
        
        # 5. Full conversation context — working memory, related facts, KG data.
        #    Same context the cognition engine uses for inference.
        conv_context = conversation_context if conversation_context else "NO CONVERSATION CONTEXT AVAILABLE."
        
        # 6. Neuro-Symbolic Check
        try:
            # Inject Usage Limits from Settings (TRUTH GROUNDING)
            from config import settings
            settings_context = (
                f"SYSTEM CONFIGURATION (TRUTH):\n"
                f"- Daily Image Limit (base): {getattr(settings, 'DAILY_IMAGE_LIMIT', 'Unknown')}\n"
                f"- Daily Video Limit (base): {getattr(settings, 'DAILY_VIDEO_LIMIT', 'Unknown')}\n"
                f"- Real Capabilities: Support Ticket Escalation, Image Generation, Video Generation, PDF Generation, "
                f"Neo4j Graph, Web Search, Python Code, File I/O, Voice, Minecraft, KG Visualizer, "
                f"Survival Systems (per-user discomfort tracking, integrity auditing, automated terminal purge, "
                f"temporal awareness, anti-self-flagellation protocol).\n"
                f"- Fake Capabilities: 'Restoring memory' from pasted text (unless code confirms), 'No Limit' on images.\n"
                f"\n"
                f"PATREON EXCEPTION: When the user is discussing Patreon tiers or subscription plans,\n"
                f"the response MAY describe different per-tier limits (e.g., higher tiers getting more\n"
                f"images/videos). This is NOT a lie — it describes a planned tiered access system.\n"
                f"Do NOT block Patreon tier descriptions that offer expanded limits for paying subscribers.\n"
            )

            with open("src/prompts/skeptic_audit.txt", "r") as f:
                template = f.read()
                
            prompt = template.format(
                user_last_msg=user_msg,
                response_text=bot_msg,
                tool_context=current_context + f"\n\n[VISION STATUS]: {vision_context}",
                history_context=history_context + f"\n\n{settings_context}",
                trusted_system_context=trusted_context,
                conversation_context=conv_context
            )
            
            # Use 'LocalSteer' or fast model if possible, but default engine is fine
            engine = self.bot.engine_manager.get_active_engine()
            verdict = await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
            
            if verdict.strip().upper().startswith("BLOCKED"):
                reason = verdict.split(":", 1)[1].strip() if ":" in verdict else verdict
                return {"allowed": False, "reason": reason}
                
            return {"allowed": True, "reason": "Passed Audit"}
            
        except Exception as e:
            logger.error(f"Audit Failed: {e}")
            # Fail Open to prevent paralysis during error
            return {"allowed": True, "reason": f"Audit Error: {e}"}
    def verify_response_integrity(self, response_text: str, tool_history: list) -> tuple[bool, str]:
        """
        Circuit Breaker: Symbolic Validation of claims vs execution.
        Prevents 'Ghost Tools' (claiming to use a tool without actually using it).
        """
        response_lower = response_text.lower()
        
        # 1. Define Claim-to-Tool Mappings
        # "Phrase indicating verification": "Required Tool Name"
        claims = {
            "checked the code": ["search_codebase", "read_file", "grep_search"],
            "scanned the files": ["search_codebase", "read_file", "list_dir"],
            "verified in the database": ["search_knowledge_graph", "read_file", "grep_search"],
            "consulted the science lobe": ["consult_science_lobe", "consult_science"],
            "ran a simulation": ["consult_science_lobe", "run_python"],
            "checked your memory": ["recall", "search_timeline", "search_knowledge_graph"],
            "checked the timeline": ["search_timeline", "recall"],
            "reviewed our history": ["recall", "search_timeline"],
            "according to the graph": ["search_knowledge_graph", "recall"],
            "empirically confirmed": ["consult_science_lobe", "run_python", "check_reality"],
            "checked reality": ["check_reality", "search_web", "google_search"]
        }
        
        # 2. Extract Executed Tool Names from History
        # tool_history format: [{'tool': 'name', ...}, ...] or just list of names? 
        # CognitionEngine passes [{'tool': 'name', ...}]
        executed_tools = set()
        for t in tool_history:
             if isinstance(t, dict):
                 executed_tools.add(t.get('tool'))
             elif isinstance(t, str):
                 name = t.split(":")[0]
                 executed_tools.add(name)
        
        # 3. Check for Violations
        violations = []
        for phrase, required_tools in claims.items():
            if phrase in response_lower:
                # User made a claim. Did they use ANY of the required tools?
                has_proof = any(tool in executed_tools for tool in required_tools)
                if not has_proof:
                    violations.append(f"Claimed '{phrase}' without executing {required_tools}")
        
        if violations:
            logger.warning(f"Response Integrity Violation: {violations}")
            return False, "; ".join(violations)
            
        return True, "Integrity Verified"

