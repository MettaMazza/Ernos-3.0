"""
Conflict Sensor — v3.3 Mycelium Network.

Detects tension, disagreement, and potential conflict
in conversations. Provides early warnings to Ernos
so it can mediate or adjust its tone.

Architecture (v3.3): Hybrid Pre-Filter + AI Arbitration
- Fast keyword pre-filter generates an initial conflict signal (0.0-1.0)
- If signal > 0.15, AI model refines with contextual understanding
- AI considers sarcasm, cultural context, gaming vs. real hostility
- This avoids false positives while keeping latency low for benign messages
"""
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("Lobe.Interaction.ConflictSensor")

# Pre-filter: Fast signal detection (NOT the final score — AI refines this)
# These catch obvious patterns to avoid sending every message to the LLM
AGGRESSION_KEYWORDS = {
    "shut up", "stfu", "idiot", "stupid", "dumb", "trash",
    "moron", "loser", "pathetic", "worthless", "useless",
    "hate you", "go away", "leave me alone", "don't talk to me",
    "fight me", "you're wrong", "liar", "fake"
}

FRUSTRATION_PATTERNS = [
    r"(?:why|how)\s+(?:can't|won't|don't)\s+you",
    r"i\s+already\s+(?:told|said|asked)",
    r"(?:so|very|extremely)\s+(?:frustrated|annoyed|angry|mad)",
    r"(?:this|that|you)\s+(?:sucks?|is\s+terrible|is\s+awful)",
    r"(?:for\s+the\s+)?(?:last|hundredth)\s+time",
]

TENSION_INDICATORS = {
    "disagree", "wrong", "incorrect", "no way", "absolutely not",
    "that's not", "you're not", "stop", "quit", "enough",
    "seriously", "honestly", "whatever", "fine"
}


class ConflictSensor:
    """
    Detects interpersonal tension in conversations.
    
    Hybrid Architecture:
    1. Fast pre-filter scores 0.0-1.0 from keywords (sync, instant)
    2. AI refinement for ambiguous signals (async, contextual)
    3. Final score drives recommended action
    
    Integration points:
    - Called from chat processing pipeline
    - Reports to HUD for awareness
    - Can trigger tone adjustment in response generation
    """
    
    def __init__(self):
        # Track conflict scores per channel to detect escalation
        self._channel_history: Dict[int, List[float]] = {}
        self._alerts: List[Dict] = []
    
    def _prefilter_score(self, message: str) -> Tuple[float, List[str]]:
        """
        Fast synchronous pre-filter using keyword matching.
        
        This is NOT the final score — it's a signal strength indicator.
        If > 0.15, AI refinement is triggered for contextual analysis.
        
        Returns: (raw_score, signals_detected)
        """
        raw_text = message.strip()
        text = raw_text.lower()
        signals = []
        score = 0.0
        
        # 1. Aggression keywords
        for keyword in AGGRESSION_KEYWORDS:
            if keyword in text:
                signals.append(f"aggression:{keyword}")
                score += 0.3
        
        # 2. Frustration patterns
        for pattern in FRUSTRATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                signals.append(f"frustration:{pattern[:30]}")
                score += 0.2
        
        # 3. Tension indicators
        tension_count = sum(1 for t in TENSION_INDICATORS if t in text)
        if tension_count >= 2:
            signals.append(f"tension:{tension_count} indicators")
            score += tension_count * 0.1
        
        # 4. ALL CAPS detection (shouting) — use raw text
        raw_words = raw_text.split()
        caps_words = [w for w in raw_words if w.isupper() and len(w) > 2]
        if len(caps_words) >= 2:
            signals.append("shouting:caps")
            score += 0.2
        
        # 5. Excessive punctuation
        if text.count("!") >= 3 or text.count("?") >= 3:
            signals.append("emphasis:punctuation")
            score += 0.1
        
        return min(score, 1.0), signals

    def analyze_message(self, message: str, user_id: int, 
                        channel_id: int) -> Dict:
        """
        Synchronous pre-filter analysis of a message.
        
        For full AI-refined analysis, use analyze_message_with_ai() instead.
        This method provides instant results for pipeline integration.
        
        Returns:
            Dict with: score (0-1), signals, escalating, recommended_action
        """
        score, signals = self._prefilter_score(message)
        
        # Track history for escalation detection
        if channel_id not in self._channel_history:
            self._channel_history[channel_id] = []
        self._channel_history[channel_id].append(score)
        
        # Only keep last 20 scores
        if len(self._channel_history[channel_id]) > 20:
            self._channel_history[channel_id] = self._channel_history[channel_id][-20:]
        
        # Detect escalation
        escalating = self._detect_escalation(channel_id)
        
        # Recommend action (pre-filter level)
        action = self._recommend_action(score, escalating)
        
        # Log alerts for high-conflict situations
        if score >= 0.5:
            alert = {
                "user_id": user_id,
                "channel_id": channel_id,
                "score": score,
                "signals": signals,
                "timestamp": datetime.now().isoformat(),
                "ai_refined": False
            }
            self._alerts.append(alert)
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-50:]
            
            logger.warning(
                f"Conflict pre-filter: user={user_id} channel={channel_id} "
                f"score={score:.2f} signals={signals}"
            )
        
        return {
            "score": round(score, 2),
            "signals": signals,
            "escalating": escalating,
            "recommended_action": action,
            "ai_refined": False
        }

    async def analyze_message_with_ai(self, message: str, user_id: int,
                                       channel_id: int, bot=None) -> Dict:
        """
        Full AI-refined conflict analysis.
        
        1. Runs pre-filter for instant signal detection
        2. If signal > 0.15, calls AI for contextual refinement
        3. Returns refined score with AI reasoning
        """
        # Step 1: Fast pre-filter
        result = self.analyze_message(message, user_id, channel_id)
        
        # Step 2: AI refinement for ambiguous/elevated signals
        if result["score"] > 0.15 and bot is not None:
            try:
                refined = await self._ai_refine(
                    message, user_id, result["score"], 
                    result["signals"], bot
                )
                if refined:
                    result["score"] = refined["score"]
                    result["recommended_action"] = refined["action"]
                    result["ai_reasoning"] = refined["reasoning"]
                    result["ai_refined"] = True
                    
                    # Update channel history with refined score
                    if self._channel_history.get(channel_id):
                        self._channel_history[channel_id][-1] = refined["score"]
                    
                    logger.info(
                        f"AI refined conflict: user={user_id} "
                        f"prefilter={result['score']:.2f} → "
                        f"refined={refined['score']:.2f} "
                        f"({refined['reasoning']})"
                    )
            except Exception as e:
                logger.error(f"Conflict AI refinement failed: {e}")
        
        return result

    async def _ai_refine(self, message: str, user_id: int,
                          prefilter_score: float, signals: List[str],
                          bot) -> Optional[Dict]:
        """
        Refine pre-filter score using AI contextual analysis.
        
        The AI considers:
        - Sarcasm and humor misidentified as aggression
        - Gaming context ('kill', 'destroy' in game talk)
        - Cultural communication styles
        - Conversation history context
        """
        try:
            engine = bot.engine_manager.get_active_engine()
            if not engine:
                return None
            
            prompt = (
                "You are analyzing a message for interpersonal conflict.\n"
                f"Pre-filter detected these signals: {signals}\n"
                f"Pre-filter score: {prefilter_score:.2f}/1.0\n\n"
                f"Message: \"{message[:1500]}\"\n\n"
                "Refine the conflict assessment considering:\n"
                "- Is this sarcasm, humor, or banter misidentified as conflict?\n"
                "- Is this gaming/roleplay context where 'kill'/'destroy' are normal?\n"
                "- Is the user venting vs. actually hostile?\n"
                "- Cultural communication style (direct ≠ aggressive)\n\n"
                "Respond ONLY with JSON:\n"
                '{"score": <float 0.0-1.0>, "action": "<normal|acknowledge|soften_tone|de-escalate>", '
                '"reasoning": "<1 sentence>"}'
            )

            response = await bot.loop.run_in_executor(
                None,
                engine.generate_response,
                prompt,
                "You are a conflict analysis system. Respond only with JSON.",
                []
            )

            # Parse response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]
            
            data = json.loads(text)
            return {
                "score": max(0.0, min(1.0, float(data.get("score", prefilter_score)))),
                "action": data.get("action", "normal"),
                "reasoning": str(data.get("reasoning", "No reasoning"))
            }
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Conflict AI parse failed: {e}")
            return None
    
    def _detect_escalation(self, channel_id: int) -> bool:
        """Detect if conflict is escalating (3+ messages rising)."""
        history = self._channel_history.get(channel_id, [])
        if len(history) < 3:
            return False
        
        recent = history[-3:]
        return (recent[0] < recent[1] < recent[2] and 
                recent[2] >= 0.3)
    
    def _recommend_action(self, score: float, escalating: bool) -> str:
        """Recommend how the active agent should respond."""
        if score >= 0.7 or (escalating and score >= 0.4):
            return "de-escalate"
        elif score >= 0.4:
            return "soften_tone"
        elif score >= 0.2:
            return "acknowledge"
        return "normal"
    
    def get_channel_tension(self, channel_id: int) -> float:
        """Get current tension level for a channel (rolling average)."""
        history = self._channel_history.get(channel_id, [])
        if not history:
            return 0.0
        recent = history[-5:]
        return round(sum(recent) / len(recent), 2)
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent conflict alerts."""
        return self._alerts[-limit:]
    
    def clear_channel_history(self, channel_id: int):
        """Clear conflict history for a channel (e.g., after resolution)."""
        self._channel_history.pop(channel_id, None)

