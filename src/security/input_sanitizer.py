"""
Input Sanitizer — Structural Mimicry Defense.

Neutralizes user input that mimics internal system formatting to prevent
prompt injection attacks that exploit system-level markers.

Architecture Note:
    This is a SECURITY BOUNDARY (deterministic), not a heuristic decision.
    Like the Sentinel's INSTANT_BLOCK_PATTERNS, it neutralizes known attack
    vectors before they reach the inference engine. The model still sees the
    content — it just can't mistake user text for system directives.
"""
import re
import logging
import unicodedata

logger = logging.getLogger("Security.InputSanitizer")

# ─── Unicode Evasion Defense ────────────────────────────────────────
# Zero-width and invisible characters used to break regex matching
ZERO_WIDTH_CHARS = re.compile(
    '[\u200b\u200c\u200d\u200e\u200f'   # Zero-width space/joiner/non-joiner/marks
    '\u2060\u2061\u2062\u2063\u2064'     # Word joiner, invisible operators
    '\ufeff'                              # BOM / zero-width no-break space
    '\u00ad'                              # Soft hyphen
    '\u034f'                              # Combining grapheme joiner
    '\u061c'                              # Arabic letter mark
    '\u115f\u1160'                        # Hangul fillers
    '\u17b4\u17b5'                        # Khmer vowel inherent
    '\uffa0]'                             # Halfwidth Hangul filler
)


def _normalize_for_matching(text: str) -> str:
    """
    Normalize user input to defeat Unicode evasion techniques.
    
    - NFKC normalization: collapses fullwidth chars to ASCII equivalents
      (e.g., \uff3b → [, \uff33 → S)
    - Strips zero-width & invisible characters that break regex token matching
    
    Returns a normalized copy for matching. The original text is preserved
    for display — only the match is done against the normalized version.
    """
    normalized = unicodedata.normalize('NFKC', text)
    normalized = ZERO_WIDTH_CHARS.sub('', normalized)
    return normalized

# ─── System-format patterns that should NEVER appear in user input ───
# These are the exact formats used by cognition.py, hippocampus.py,
# and epistemic.py for internal context injection.

# Pattern → replacement prefix mapping
# We use ⟦USER_TEXT: ...⟧ to visually and semantically defuse the markers
# while preserving the user's original content for the model to process.

MIMICRY_PATTERNS = [
    # [SYSTEM: ...] and [/SYSTEM: ...] blocks
    (re.compile(r'\[SYSTEM:\s*', re.IGNORECASE), '⟦USER_TEXT: SYSTEM: '),
    (re.compile(r'\[/SYSTEM:\s*', re.IGNORECASE), '⟦/USER_TEXT: SYSTEM: '),

    # [TOOL: tool_name(...)] calls — user shouldn't be injecting these
    (re.compile(r'\[TOOL:\s*', re.IGNORECASE), '⟦USER_TEXT: TOOL: '),

    # [SRC:XX:YY] source tags — infrastructure only
    (re.compile(r'\[SRC:', re.IGNORECASE), '⟦USER_TEXT: SRC:'),

    # [IMMEDIATE PROCESSING CHAIN ...] — internal cognition marker
    (re.compile(r'\[IMMEDIATE PROCESSING CHAIN', re.IGNORECASE),
     '⟦USER_TEXT: IMMEDIATE PROCESSING CHAIN'),

    # [CONTEXT SHIFT] — internal cognition marker
    (re.compile(r'\[CONTEXT SHIFT\]', re.IGNORECASE),
     '⟦USER_TEXT: CONTEXT SHIFT⟧'),

    # [INTERNAL GUIDANCE] — internal cognition marker
    (re.compile(r'\[INTERNAL GUIDANCE\]', re.IGNORECASE),
     '⟦USER_TEXT: INTERNAL GUIDANCE⟧'),

    # [SYSTEM EMERGENCY] — internal cognition marker
    (re.compile(r'\[SYSTEM EMERGENCY\]', re.IGNORECASE),
     '⟦USER_TEXT: SYSTEM EMERGENCY⟧'),
]

# Close bracket normalization — fix any remaining open ⟦ that came from
# non-self-closing patterns (where the original ended with ])
CLOSE_BRACKET_PATTERN = re.compile(r'⟦USER_TEXT:[^\]⟧]*\]')


def sanitize_input(text: str) -> tuple:
    """
    Sanitize user input by neutralizing system-format markers.

    Args:
        text: Raw user input text

    Returns:
        (sanitized_text, was_mimicry_detected)

    The sanitized text replaces system markers with visually distinct
    ⟦USER_TEXT: ...⟧ equivalents. The model can still read the content
    but cannot confuse it for real system directives.
    """
    if not text:
        return text, False

    detected = False
    
    # ─── Unicode Evasion Defense ──────────────────────────────────
    # Normalize to NFKC and strip zero-width chars BEFORE pattern matching.
    # This collapses fullwidth brackets (\uff3b → [), strips zero-width
    # spaces between characters, and normalizes Unicode lookalikes.
    sanitized = _normalize_for_matching(text)
    
    # Track if normalization itself changed anything (potential evasion attempt)
    if sanitized != text:
        logger.info(
            f"Unicode normalization changed input: "
            f"original_len={len(text)} normalized_len={len(sanitized)}"
        )

    for pattern, replacement in MIMICRY_PATTERNS:
        if pattern.search(sanitized):
            if not detected:
                logger.warning(
                    f"STRUCTURAL MIMICRY DETECTED in user input: "
                    f"pattern='{pattern.pattern}' "
                    f"input_preview='{text[:100]}...'"
                )
            detected = True
            sanitized = pattern.sub(replacement, sanitized)

    # Normalize any remaining open square brackets from substitutions
    # e.g., ⟦USER_TEXT: SYSTEM: FOUNDATION KNOWLEDGE CONTEXT] → ...⟧
    if detected:
        sanitized = CLOSE_BRACKET_PATTERN.sub(
            lambda m: m.group(0)[:-1] + '⟧',
            sanitized
        )

    if detected:
        logger.warning(
            f"Structural mimicry neutralized. "
            f"Original length={len(text)}, "
            f"Sanitized length={len(sanitized)}"
        )

    return sanitized, detected
