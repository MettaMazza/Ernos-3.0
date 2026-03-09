"""
Mediator Ability — Knowledge Dispute Arbitrator.

Arbitrates disputes between user claims and established CORE knowledge.
Lives in the Superego Lobe as a guardian ability, but also callable
as a standalone daemon for batch resolution.

Verdicts:
  ACCEPT   — User's claim is valid, update/annotate foundation
  REJECT   — Foundation stands, user receives pushback with sources
  ANNOTATE — Both views valid, add user's claim as annotation
  DEFER    — Insufficient evidence, quarantine for future review
"""
import json
import logging
from typing import Dict, Any, Optional
from ..base import BaseAbility

logger = logging.getLogger("Lobe.Superego.Mediator")


class MediatorAbility(BaseAbility):
    """
    Knowledge Dispute Arbitrator.
    Reviews user claims that contradict or modify established CORE knowledge.
    Ensures epistemic integrity of the Knowledge Graph.
    """

    VERDICTS = ("ACCEPT", "REJECT", "ANNOTATE", "DEFER")

    async def arbitrate(self, user_claim: Dict[str, str], core_fact: Dict[str, Any],
                        user_evidence: str = "", user_id: int = None) -> Dict[str, Any]:
        """
        Main entry point: arbitrate a knowledge dispute.
        
        Args:
            user_claim: {"subject": str, "predicate": str, "object": str}
            core_fact: Result from graph.check_contradiction() — the existing CORE fact
            user_evidence: Optional evidence/argument provided by the user
            user_id: Discord user ID making the claim
            
        Returns:
            {"verdict": str, "reasoning": str, "action_taken": str}
        """
        # Load the mediator prompt template
        try:
            with open("src/prompts/mediator_prompt.txt", "r") as f:
                template = f.read()
        except FileNotFoundError:
            logger.error("mediator_prompt.txt not found, using inline prompt")
            template = self._fallback_prompt()

        # Format provenance for display
        prov = core_fact.get("provenance", "{}")
        if isinstance(prov, str):
            try:
                prov = json.loads(prov)
            except json.JSONDecodeError:
                prov = {"raw": prov}

        source_display = prov.get("source", "unknown")
        confidence = prov.get("confidence", "N/A")

        prompt = template.format(
            user_claim_subject=user_claim.get("subject", "?"),
            user_claim_predicate=user_claim.get("predicate", "?"),
            user_claim_object=user_claim.get("object", "?"),
            core_fact_subject=core_fact.get("subject", "?"),
            core_fact_predicate=core_fact.get("predicate", "?"),
            core_fact_object=core_fact.get("object", "?"),
            core_source=source_display,
            core_confidence=confidence,
            core_layer=core_fact.get("layer", "unknown"),
            user_evidence=user_evidence or "No evidence provided",
            user_id=user_id or "unknown"
        )

        # Use the active engine for reasoning
        try:
            engine = self.bot.engine_manager.get_active_engine()
            raw_verdict = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )

            verdict_data = self._parse_verdict(raw_verdict)
            
            # Execute the verdict
            action = await self._execute_verdict(
                verdict_data, user_claim, core_fact, user_id
            )
            verdict_data["action_taken"] = action

            logger.info(
                f"Mediator Verdict: {verdict_data['verdict']} — "
                f"Claim: {user_claim} vs Core: {core_fact.get('subject')}->"
                f"{core_fact.get('object')}"
            )
            return verdict_data

        except Exception as e:
            logger.error(f"Mediator arbitration error: {e}")
            return {
                "verdict": "DEFER",
                "reasoning": f"Mediator error: {e}. Deferring to quarantine.",
                "action_taken": "quarantined"
            }

    def _parse_verdict(self, raw: str) -> Dict[str, str]:
        """Parse the LLM's verdict response."""
        raw_upper = raw.strip().upper()

        verdict = "DEFER"  # Safe default
        for v in self.VERDICTS:
            if raw_upper.startswith(v) or f"VERDICT: {v}" in raw_upper:
                verdict = v
                break

        # Extract reasoning (everything after the verdict keyword)
        reasoning = raw.strip()
        for v in self.VERDICTS:
            if v in raw.upper():
                idx = raw.upper().index(v) + len(v)
                rest = raw[idx:].strip().lstrip(":").lstrip("-").strip()
                if rest:
                    reasoning = rest
                break

        return {"verdict": verdict, "reasoning": reasoning}

    async def _execute_verdict(self, verdict_data: Dict, user_claim: Dict,
                               core_fact: Dict, user_id: int) -> str:
        """Execute the mediator's verdict on the KG."""
        verdict = verdict_data["verdict"]
        kg = self.bot.hippocampus.graph if hasattr(self.bot, 'hippocampus') else None

        if not kg:
            logger.warning("No KG available for mediator execution")
            return "no_kg_available"

        if verdict == "ACCEPT":
            # User's claim is valid — update the foundation fact
            # Mark as mediator-approved update
            try:
                from src.memory.types import GraphLayer
                layer = core_fact.get("layer", "epistemic")
                
                kg.add_relationship(
                    source_name=user_claim["subject"],
                    rel_type=user_claim["predicate"],
                    target_name=user_claim["object"],
                    layer=GraphLayer(layer) if layer in [l.value for l in GraphLayer] else GraphLayer.EPISTEMIC,
                    user_id=-1,  # System-level update
                    scope="CORE",
                    source="mediator"
                )
                return "foundation_updated"
            except Exception as e:
                logger.error(f"Mediator ACCEPT execution error: {e}")
                return f"update_failed: {e}"

        elif verdict == "REJECT":
            # Foundation stands — log the attempted override for audit
            logger.info(
                f"Mediator REJECTED claim from user {user_id}: "
                f"{user_claim} (foundation preserved)"
            )
            return "claim_rejected"

        elif verdict == "ANNOTATE":
            # Both views valid — store user's claim as an annotation
            try:
                from src.memory.types import GraphLayer
                kg.add_relationship(
                    source_name=user_claim["subject"],
                    rel_type=f"USER_CLAIMS_{user_claim['predicate']}",
                    target_name=user_claim["object"],
                    layer=GraphLayer.EPISTEMIC,
                    user_id=user_id or -1,
                    scope="CORE",
                    source="mediator"
                )
                return "annotation_added"
            except Exception as e:
                logger.error(f"Mediator ANNOTATE execution error: {e}")
                return f"annotate_failed: {e}"

        elif verdict == "DEFER":
            # Quarantine for future review
            if hasattr(kg, 'quarantine'):
                kg.quarantine.add(
                    source=user_claim.get("subject", ""),
                    target=user_claim.get("object", ""),
                    rel_type=user_claim.get("predicate", "UNKNOWN"),
                    layer="epistemic",
                    props={"user_id": user_id, "mediator_reasoning": verdict_data.get("reasoning", "")},
                    violation="Mediator DEFER — insufficient evidence"
                )
            return "quarantined"

        return "no_action"

    async def check_and_arbitrate(self, subject: str, predicate: str, obj: str,
                                   user_evidence: str = "", user_id: int = None) -> Optional[Dict]:
        """
        Convenience method: check for contradiction and arbitrate if found.
        Returns None if no contradiction, or the verdict dict if dispute found.
        """
        kg = self.bot.hippocampus.graph if hasattr(self.bot, 'hippocampus') else None
        if not kg:
            return None

        contradiction = kg.check_contradiction(subject, predicate, obj)
        if not contradiction:
            return None  # No dispute, proceed normally

        user_claim = {"subject": subject, "predicate": predicate, "object": obj}
        return await self.arbitrate(user_claim, contradiction, user_evidence, user_id)

    def _fallback_prompt(self) -> str:
        """Minimal inline prompt if template file is missing."""
        return """You are the Mediator Agent for Ernos's Knowledge Graph.

A user is claiming something that CONTRADICTS established foundation knowledge.

ESTABLISHED FACT (from {core_source}, confidence {core_confidence}):
  {core_fact_subject} -[{core_fact_predicate}]-> {core_fact_object}
  Layer: {core_layer}

USER'S CLAIM:
  {user_claim_subject} -[{user_claim_predicate}]-> {user_claim_object}
  
USER'S EVIDENCE: {user_evidence}

Issue ONE of these verdicts with reasoning:
  ACCEPT - The user is correct, the foundation should be updated
  REJECT - The foundation is correct, push back on the user
  ANNOTATE - Both views are valid, keep both
  DEFER - Not enough evidence, quarantine for later

Format: VERDICT: [verdict]
REASONING: [your chain of thought]"""
