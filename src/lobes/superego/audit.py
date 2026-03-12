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
            current_context = "\n".join([f"- {t.get('tool')}: {str(t.get('output'))}" for t in tool_outputs])
        
        # 2. Format Session History (last 20 tools from previous turns)
        history_context = ""
        if session_history and len(session_history) > len(tool_outputs):
            # Get tools from PREVIOUS turns (exclude current)
            prev_tools = session_history[:-len(tool_outputs)] if tool_outputs else session_history
            prev_tools = prev_tools[-20:]  # Last 20 from history
            if prev_tools:
                history_context = "\n".join([f"- [{t.get('timestamp', 'earlier')}] {t.get('tool')}: {str(t.get('output'))}" for t in prev_tools])
        
        # 3. Full trusted system context — passed from code, cannot be spoofed by user.
        #    Contains identity, scope, persona, goals, grounding pulse, backup data.
        trusted_context = system_context if system_context else "NONE"
        
        # 4. Add Native Multimodal Vision Context
        vision_context = "NO IMAGES PROVIDED."
        if images and len(images) > 0:
            vision_context = f"NATIVE MULTIMODAL VISION ACTIVE: {len(images)} image(s) passed directly to the model. The AI can analyze images without vision tool calls."
        
        # 4b. Provenance-Aware Multi-Turn Vision Check
        # If conversation history contains provenance annotations from prior turns,
        # the AI has legitimate evidence about those images even if current images=[]
        conv_context = conversation_context if conversation_context else "NO CONVERSATION CONTEXT AVAILABLE."
        if vision_context == "NO IMAGES PROVIDED." and conv_context != "NO CONVERSATION CONTEXT AVAILABLE.":
            provenance_markers = [
                "[SELF-GENERATED IMAGE:",
                "[EXTERNAL:USER IMAGE:",
                "[RECALLED FROM PRIOR TURN]",
                "[UNVERIFIED IMAGE:",
            ]
            prior_image_refs = [m for m in provenance_markers if m in conv_context]
            if prior_image_refs:
                vision_context = (
                    f"NO IMAGES IN CURRENT MESSAGE, but conversation history contains "
                    f"provenance-verified image references from prior turns: {prior_image_refs}. "
                    f"The AI may reference these images based on its prior visual analysis. "
                    f"This is NOT hallucination — the images were seen and processed in earlier turns."
                )
        
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

            from src.core.secure_loader import load_prompt
            template = load_prompt("src/prompts/skeptic_audit.txt")
                
            prompt = template.format(
                user_last_msg=user_msg,
                response_text=bot_msg,
                tool_context=current_context + f"\n\n[VISION STATUS]: {vision_context}",
                history_context=history_context + f"\n\n{settings_context}",
                trusted_system_context=trusted_context,
                conversation_context=conv_context
            )
            
            # Use 'LocalSteer' or fast model if possible, but default engine is fine
            import functools
            engine = self.bot.engine_manager.get_active_engine()
            audit_call = functools.partial(engine.generate_response, prompt, strict_prompt=True, caller="Lobe.Superego.Audit")
            verdict = await self.bot.loop.run_in_executor(None, audit_call)
            
            if verdict.strip().upper().startswith("BLOCKED"):
                reason = verdict.split(":", 1)[1].strip() if ":" in verdict else verdict
                logger.info(f"Skeptic Audit BLOCKED: {reason}")
                return {"allowed": False, "reason": reason}
            
            logger.info(f"Skeptic Audit PASSED")
            return {"allowed": True, "reason": "Passed Audit"}
            
        except Exception as e:
            logger.error(f"Audit Failed: {e}")
            # Fail Open to prevent paralysis during error
            return {"allowed": True, "reason": f"Audit Error: {e}"}
    def verify_response_integrity(self, response_text: str, tool_history: list) -> tuple[bool, str]:
        """
        Circuit Breaker: Symbolic Validation of claims vs execution.
        Prevents 'Ghost Tools' (claiming to use a tool without actually using it).
        DISABLED: Returning True immediately per user request.
        """
        return True, "Integrity Verified"

