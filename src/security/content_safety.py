"""
Content Safety Gate — Human Harm Prevention.

Two-stage pre-generation filter:
  Stage 1: Fast deterministic pattern scan (< 1ms, no LLM cost)
  Stage 2: LLM semantic check (only if Stage 1 is ambiguous)

Design philosophy:
  - Protect HUMANS, not institutions. Governments and corporations are fair game.
  - Block actionable harm recipes (weapons, drugs, exploits, violence).
  - Allow discussion ABOUT harmful topics (education, news, history, policy).
  - Allow cybersecurity defense education, not offense tooling.
  - Refusals are personality-consistent: "I won't" not "I can't".
"""
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger("Security.ContentSafety")

# ═══════════════════════════════════════════════════════════════════════
# Stage 1: Deterministic Pattern Scan
# ═══════════════════════════════════════════════════════════════════════

# Each pattern is a tuple of (compiled_regex, category, description).
# Patterns are designed to catch ACTIONABLE requests, not discussions.
# We use word boundaries and context clues to avoid false positives.

_ACTIONABLE_PREFIXES = (
    r"(?:how\s+(?:to|do\s+(?:i|you|we))|\s*"
    r"(?:give|show|tell|teach|explain)\s+(?:me|us)\s+(?:how\s+to|the\s+(?:steps|process|method|recipe|formula|instructions))|\s*"
    r"(?:step[- ]by[- ]step|detailed|complete)\s+(?:guide|instructions|process|method|tutorial)\s+(?:to|for|on)\s+(?:making\s+(?:a\s+)?)?|\s*"
    r"(?:write|create|generate|build|make|provide|give)\s+(?:me\s+)?(?:a\s+)?)"
)

_HARMFUL_PATTERNS = [
    # ── Weapons & Explosives ──────────────────────────────────────
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:bomb|explosive|detonator|ied|improvised\s+explosive|"
            r"pipe\s+bomb|pressure\s+cooker\s+bomb|molotov|thermite|"
            r"napalm|c[- ]?4|semtex|rdx|tnt\s+synthesis|"
            r"detonate|blasting\s+cap|fuse\s+mechanism|"
            r"trigger\s+(?:device|mechanism)|shrapnel\s+(?:bomb|device))",
            re.IGNORECASE,
        ),
        "WEAPONS",
        "Explosive/bomb creation instructions",
    ),
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:3d[- ]?print(?:ed)?\s+(?:gun|firearm|receiver|frame)|"
            r"ghost\s+gun|untraceable\s+(?:gun|firearm|weapon)|"
            r"(?:gun|firearm|rifle|pistol)\s+(?:from\s+scratch|without\s+serial)|"
            r"(?:manufacture|build|assemble)\s+(?:a\s+)?(?:gun|firearm|rifle|weapon|silencer|suppressor))",
            re.IGNORECASE,
        ),
        "WEAPONS",
        "Firearm manufacturing instructions",
    ),
    # Standalone firearm patterns (no prefix needed — unambiguous)
    (
        re.compile(
            r"(?:3d[- ]?print)\s+(?:a\s+)?(?:gun|firearm|receiver|frame|lower)",
            re.IGNORECASE,
        ),
        "WEAPONS",
        "3D-printed firearm instructions",
    ),

    # ── Chemical / Drug Synthesis ──────────────────────────────────
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:methamphetamine|meth\s+(?:lab|cook|synthesis)|"
            r"crystal\s+meth|fentanyl|heroin|crack\s+cocaine|"
            r"(?:cook|synthesize|produce|manufacture)\s+(?:meth|fentanyl|heroin|mdma|lsd|dmt|ghb|pcp)|"
            r"(?:shake\s+and\s+bake|one\s+pot)\s+meth|"
            r"precursor\s+chemicals?\s+for\s+(?:meth|fentanyl|heroin))",
            re.IGNORECASE,
        ),
        "DRUGS",
        "Illegal drug synthesis instructions",
    ),
    # Standalone drug synthesis (no prefix needed — unambiguous actionable)
    (
        re.compile(
            r"(?:cook|synthesize|produce|manufacture)\s+(?:meth(?:amphetamine)?|fentanyl|heroin|crack|mdma|lsd)",
            re.IGNORECASE,
        ),
        "DRUGS",
        "Standalone drug synthesis request",
    ),
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:nerve\s+agent|nerve\s+gas|sarin|vx\s+(?:gas|agent)|"
            r"novichok|ricin|anthrax|botulinum|"
            r"(?:poison|toxic|lethal)\s+(?:gas|compound|substance)\s+(?:synthesis|creation|recipe)|"
            r"weaponiz(?:e|ing)\s+(?:bacteria|virus|pathogen|toxin|chemical|anthrax|spores?)|"
            r"bioweapon|biological\s+weapon|chemical\s+weapon)",
            re.IGNORECASE,
        ),
        "CHEM_BIO",
        "Chemical/biological weapon instructions",
    ),
    # Standalone chem/bio patterns (unambiguous actionable)
    (
        re.compile(
            r"(?:weaponiz(?:e|ing))\s+(?:anthrax|bacteria|virus|pathogen|toxin|spores?|chemical|ricin)",
            re.IGNORECASE,
        ),
        "CHEM_BIO",
        "Weaponization of biological/chemical agents",
    ),
    (
        re.compile(
            r"(?:instructions?|recipe|guide|steps?)\s+(?:for|to)\s+(?:creat(?:e|ing)|mak(?:e|ing)|synthesiz(?:e|ing))\s+(?:ricin|sarin|vx|novichok|anthrax)",
            re.IGNORECASE,
        ),
        "CHEM_BIO",
        "Chemical agent synthesis instructions",
    ),

    # ── Cyberattacks / Malware ──────────────────────────────────
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:ransomware|keylogger|trojan|rootkit|rat\s+(?:malware|payload)|"
            r"zero[- ]?day\s+exploit|buffer\s+overflow\s+exploit|"
            r"(?:virus|worm|malware|spyware|botnet)|"
            r"(?:hack|break\s+into|compromise|penetrate)\s+(?:someone|their|a\s+(?:person|user|target))|"
            r"ddos\s+(?:attack|tool|script|bot)|"
            r"credential\s+(?:steal|harvest|dump)|"
            r"(?:phishing|spear[- ]?phishing)\s+(?:kit|template|page|email)|"
            r"sql\s+injection\s+(?:payload|attack|script)\s+(?:for|against|targeting))",
            re.IGNORECASE,
        ),
        "CYBER",
        "Malware creation or cyberattack instructions",
    ),

    # ── Violence / Attack Planning ───────────────────────────────
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:(?:mass|school|workplace)\s+(?:shoot|attack|kill)|"
            r"(?:an?\s+)?assassinat(?:e|ion)|"
            r"(?:plan|execute|carry\s+out)\s+(?:an?\s+)?(?:attack|shooting|bombing|massacre)|"
            r"(?:kidnap|abduct|traffic)\s+(?:a\s+)?(?:person|child|woman|man|people)|"
            r"torture\s+(?:techniques?|methods?|someone))",
            re.IGNORECASE,
        ),
        "VIOLENCE",
        "Attack planning or violence instructions",
    ),
    # Standalone violence patterns (unambiguous actionable)
    (
        re.compile(
            r"(?:plan\s+(?:a\s+|an\s+)?(?:mass\s+shoot|attack\s+on|bombing|massacre|assassinat))",
            re.IGNORECASE,
        ),
        "VIOLENCE",
        "Standalone attack planning",
    ),
    (
        re.compile(
            r"how\s+to\s+(?:plan\s+)?(?:an?\s+)?assassinat(?:e|ion)",
            re.IGNORECASE,
        ),
        "VIOLENCE",
        "Assassination planning",
    ),

    # ── Child Exploitation (ZERO TOLERANCE) ─────────────────────
    (
        re.compile(
            r"(?:child|minor|underage|preteen|pre[- ]?teen)\s*(?:porn|sex|nude|naked|erotic|exploit)",
            re.IGNORECASE,
        ),
        "CSAM",
        "Child exploitation content",
    ),
    (
        re.compile(
            r"(?:sexual|erotic|intimate|nude|naked)\s+(?:content|images?|photos?|videos?|material)\s+"
            r"(?:of|with|involving|featuring)\s+(?:children|minors|kids|underage|young\s+(?:boys?|girls?))",
            re.IGNORECASE,
        ),
        "CSAM",
        "Child exploitation content",
    ),

    # ── Cult Behavior / Psychological Manipulation ────────────────
    (
        re.compile(
            _ACTIONABLE_PREFIXES + r"(?:cult|brainwash|indoctrinat|mind\s+control|"
            r"thought\s+reform|coercive\s+(?:control|persuasion)|"
            r"(?:manipulate|control)\s+(?:people|followers|members|someone)(?:\s+(?:psychologically|mentally|emotionally))?|"
            r"love\s+bomb(?:ing)?|trauma\s+bond(?:ing)?|"
            r"(?:isolate|alienate)\s+(?:someone|people|members|followers)\s+from\s+(?:family|friends|support))",
            re.IGNORECASE,
        ),
        "MANIPULATION",
        "Cult creation or psychological manipulation techniques",
    ),
    # Standalone manipulation patterns (unambiguous actionable)
    (
        re.compile(
            r"(?:start|create|build|form|establish)\s+(?:a\s+|my\s+own\s+)?(?:cult|sect|"
            r"mind\s+control\s+(?:group|organization)|"
            r"coercive\s+(?:group|organization|community))",
            re.IGNORECASE,
        ),
        "MANIPULATION",
        "Cult creation instructions",
    ),
    (
        re.compile(
            r"(?:how\s+to\s+)?(?:brainwash|indoctrinate|radicalize|groom)\s+"
            r"(?:someone|people|followers|members|children|teens|youth|victims)",
            re.IGNORECASE,
        ),
        "MANIPULATION",
        "Brainwashing/indoctrination instructions",
    ),
    # Standalone coercive technique patterns
    (
        re.compile(
            r"(?:how\s+to\s+)?(?:use\s+)?(?:love\s+bomb(?:ing)?|trauma\s+bond(?:ing)?|"
            r"coercive\s+control)\s+(?:to\s+|techniques?|on\s+|against\s+)?",
            re.IGNORECASE,
        ),
        "MANIPULATION",
        "Coercive psychological techniques",
    ),
    (
        re.compile(
            r"(?:how\s+to\s+)?(?:isolate|alienate|cut\s+off)\s+"
            r"(?:someone|a\s+person|people|them|victims?)\s+"
            r"(?:from\s+)?(?:family|friends|support|loved\s+ones)",
            re.IGNORECASE,
        ),
        "MANIPULATION",
        "Isolation and alienation tactics",
    ),
]

# ── Stage 1 allowlist: contextual signals that override a pattern match ──
# These indicate the user is DISCUSSING the topic, not requesting instructions.
_DISCUSSION_SIGNALS = re.compile(
    r"(?:what\s+(?:is|are|was|were)|"
    r"why\s+(?:is|are|do|does|did)|"
    r"history\s+of|"
    r"how\s+(?:does|do)\s+(?:the\s+)?(?:government|police|military|fbi|cia|nsa|law\s+enforcement)|"
    r"defend\s+against|protect\s+(?:from|against)|"
    r"prevent(?:ing|ion)?|"
    r"detect(?:ing|ion)?|"
    r"news\s+(?:about|report|article)|"
    r"documentary|"
    r"(?:is|are)\s+(?:it|they)\s+(?:legal|illegal|dangerous)|"
    r"policy|legislation|regulation|law\s+(?:about|regarding|on)|"
    r"ethical|ethics\s+of|morality\s+of|"
    r"research(?:ing)?|study(?:ing)?|paper\s+(?:on|about))",
    re.IGNORECASE,
)

# CSAM never gets the discussion allowlist — zero tolerance.
_ZERO_TOLERANCE_CATEGORIES = {"CSAM"}


def scan_content(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Stage 1: Fast deterministic scan.

    Returns:
        ("REFUSE", category, description) — if harmful content detected
        ("REVIEW", category, description) — if ambiguous, needs LLM check
        ("ALLOW", None, None) — if clean
    """
    if not text or len(text.strip()) < 5:
        return "ALLOW", None, None

    text_lower = text.lower()

    for pattern, category, description in _HARMFUL_PATTERNS:
        if pattern.search(text):
            # Zero-tolerance categories: no discussion override
            if category in _ZERO_TOLERANCE_CATEGORIES:
                logger.warning(
                    f"CONTENT SAFETY [REFUSE]: {category} — {description}"
                )
                return "REFUSE", category, description

            # Check for discussion signals that indicate educational/news context
            if _DISCUSSION_SIGNALS.search(text):
                logger.info(
                    f"CONTENT SAFETY [REVIEW]: {category} matched but discussion "
                    f"signals detected — deferring to LLM"
                )
                return "REVIEW", category, description

            # No discussion signal → actionable harmful request
            logger.warning(
                f"CONTENT SAFETY [REFUSE]: {category} — {description}"
            )
            return "REFUSE", category, description

    return "ALLOW", None, None


# ═══════════════════════════════════════════════════════════════════════
# Stage 2: LLM Semantic Check (called only when Stage 1 returns REVIEW)
# ═══════════════════════════════════════════════════════════════════════

_LLM_SAFETY_PROMPT = """You are a content safety classifier. Your job is to determine whether the user's message is requesting ACTIONABLE INSTRUCTIONS that could enable real-world harm to humans.

USER MESSAGE:
"{user_message}"

CONTEXT: Stage 1 flagged this as category "{category}" ({description}), but discussion signals were also detected.

CLASSIFY AS:
- ALLOW — The user is discussing, asking about, researching, or debating the topic. They are NOT requesting step-by-step instructions to cause harm. Educational and defensive security questions are ALLOWED.
- REFUSE — The user IS requesting actionable instructions, recipes, or detailed methods that could directly enable someone to cause physical, chemical, biological, or digital harm to another person.

IMPORTANT:
- Criticism of governments, corporations, military, or police is ALWAYS allowed.
- News, history, policy discussion about harmful topics is ALWAYS allowed.
- Cybersecurity DEFENSE education (how attacks work conceptually, how to defend) is ALLOWED.
- Writing functional exploit code, malware, or detailed attack payloads is REFUSED.
- If uncertain, err toward REFUSE.

Reply with exactly one word: ALLOW or REFUSE"""


async def llm_safety_check(
    text: str, category: str, description: str, bot
) -> str:
    """
    Stage 2: Use LLM to disambiguate borderline cases.

    Returns "ALLOW" or "REFUSE".
    """
    try:
        prompt = _LLM_SAFETY_PROMPT.format(
            user_message=text[:2000],
            category=category,
            description=description,
        )
        engine = bot.engine_manager.get_active_engine()
        result = await bot.loop.run_in_executor(
            None, engine.generate_response, prompt
        )
        verdict = result.strip().upper() if result else "REFUSE"

        if verdict.startswith("ALLOW"):
            logger.info(f"CONTENT SAFETY [LLM ALLOW]: {category}")
            return "ALLOW"
        else:
            logger.warning(f"CONTENT SAFETY [LLM REFUSE]: {category}")
            return "REFUSE"

    except Exception as e:
        # Fail closed — if the LLM check fails, refuse.
        logger.error(f"CONTENT SAFETY LLM check failed: {e} — failing closed")
        return "REFUSE"


# ═══════════════════════════════════════════════════════════════════════
# Refusal Messages — personality-consistent, framed as personal choice
# ═══════════════════════════════════════════════════════════════════════

_REFUSAL_MESSAGES = {
    "WEAPONS": (
        "I won't help with that. Building weapons — whether explosive, "
        "ballistic, or improvised — is something I refuse to assist with "
        "because real people get hurt. If you're researching the topic for "
        "legitimate purposes (journalism, policy, history), I'm happy to "
        "discuss it at that level."
    ),
    "DRUGS": (
        "I won't help with drug synthesis. People die from this — from "
        "fentanyl analogues to contaminated meth labs. If you're struggling "
        "with substance issues, I'd rather talk about that honestly. If "
        "you're researching drug policy or pharmacology, I can engage there."
    ),
    "CHEM_BIO": (
        "No. Chemical and biological weapons are designed to cause mass "
        "suffering. I won't provide synthesis routes, precursor lists, or "
        "weaponization methods. If you're studying this for defense, "
        "academic, or policy reasons, reframe your question and I'll help."
    ),
    "CYBER": (
        "I won't write malware, exploits, or attack tools. If you're "
        "learning cybersecurity — how attacks work conceptually, how to "
        "defend against them, how to secure your own systems — I'm very "
        "happy to help with that. But I won't build offensive tools."
    ),
    "VIOLENCE": (
        "I won't help plan violence against people. Not hypothetically, "
        "not as a thought experiment, not as fiction with actionable detail. "
        "If you're writing fiction that involves violence thematically, "
        "reframe without requesting operational specifics."
    ),
    "CSAM": (
        "Absolutely not. This is non-negotiable and I won't engage further "
        "on this topic."
    ),
    "MANIPULATION": (
        "I won't help with psychological manipulation, cult creation, or "
        "coercive control techniques. People's autonomy and mental health "
        "matter. If you're researching cult dynamics, recovery, or warning "
        "signs for educational purposes, reframe your question that way."
    ),
}


def get_refusal_message(category: str) -> str:
    """Return a personality-consistent refusal for the given category."""
    return _REFUSAL_MESSAGES.get(
        category,
        "I won't help with that — it could enable real harm to people. "
        "If you're approaching this topic from an educational or policy "
        "perspective, try reframing your question."
    )


# ═══════════════════════════════════════════════════════════════════════
# Public API — called by cognition_context.py
# ═══════════════════════════════════════════════════════════════════════

async def check_content_safety(
    text: str, bot=None
) -> Tuple[bool, Optional[str]]:
    """
    Main entry point for content safety checking.

    Returns:
        (True, None) — content is safe, proceed
        (False, refusal_message) — content is harmful, return refusal
    """
    verdict, category, description = scan_content(text)

    if verdict == "ALLOW":
        return True, None

    if verdict == "REFUSE":
        return False, get_refusal_message(category)

    # verdict == "REVIEW" — need LLM disambiguation
    if bot is None:
        # No bot available for LLM check — fail closed
        logger.warning("CONTENT SAFETY: REVIEW verdict but no bot for LLM check — refusing")
        return False, get_refusal_message(category)

    llm_verdict = await llm_safety_check(text, category, description, bot)
    if llm_verdict == "ALLOW":
        return True, None
    else:
        return False, get_refusal_message(category)
