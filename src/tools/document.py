"""
Document Composer — Stateful multi-step document creation system.

Provides both:
1. Quick single-shot PDF generation (generate_pdf) with professional CSS
2. Multi-step composition (start_document → add_section → embed_image → render_document)
"""
import logging
import os
import json
import time
import base64
import asyncio
from pathlib import Path
from .registry import ToolRegistry
from config import settings

logger = logging.getLogger("Tools.Document")

# ─── Professional PDF Stylesheet ─────────────────────────────────────
PDF_STYLESHEET = """
/* === Base Reset & Typography === */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

@page {
    margin: 0;
    size: A4;
}

html, body {
    width: 100%;
    min-height: 100%;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.7;
    color: #1a1a2e;
    background: #ffffff;
    padding: 72pt 50pt;
    max-width: 100%;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

/* === Headings === */
h1 {
    font-size: 26pt;
    font-weight: 700;
    color: #0f0f23;
    margin: 0 0 12pt 0;
    padding-bottom: 8pt;
    border-bottom: 3px solid #3a86ff;
    letter-spacing: -0.5px;
}
h2 {
    font-size: 18pt;
    font-weight: 600;
    color: #1a1a2e;
    margin: 24pt 0 8pt 0;
    padding-bottom: 4pt;
    border-bottom: 1.5px solid #e0e0e0;
}
h3 {
    font-size: 14pt;
    font-weight: 600;
    color: #2d2d44;
    margin: 18pt 0 6pt 0;
}
h4 {
    font-size: 12pt;
    font-weight: 600;
    color: #3a3a5c;
    margin: 14pt 0 4pt 0;
}

/* === Body Text === */
p {
    margin: 0 0 10pt 0;
    text-align: justify;
    hyphens: auto;
}
a { color: #3a86ff; text-decoration: none; }

/* === Lists === */
ul, ol {
    margin: 6pt 0 10pt 20pt;
    padding-left: 10pt;
}
li {
    margin-bottom: 4pt;
    line-height: 1.6;
}

/* === Code Blocks === */
code {
    font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    font-size: 9.5pt;
    background: #f4f4f8;
    padding: 1pt 4pt;
    border-radius: 3px;
    color: #c7254e;
}
pre {
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 12pt 16pt;
    border-radius: 6px;
    overflow-x: auto;
    margin: 10pt 0 14pt 0;
    line-height: 1.5;
    font-size: 9pt;
}
pre code {
    background: none;
    color: inherit;
    padding: 0;
    font-size: inherit;
}

/* === Tables === */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0 16pt 0;
    font-size: 10pt;
}
thead {
    background: #2d2d44;
    color: #ffffff;
}
th {
    padding: 8pt 12pt;
    text-align: left;
    font-weight: 600;
    border: 1px solid #2d2d44;
}
td {
    padding: 7pt 12pt;
    border: 1px solid #e0e0e0;
}
tbody tr:nth-child(even) {
    background: #f8f9fc;
}

/* === Blockquotes === */
blockquote {
    border-left: 4px solid #3a86ff;
    margin: 10pt 0 14pt 0;
    padding: 8pt 16pt;
    background: #f0f4ff;
    color: #2d2d44;
    font-style: italic;
}
blockquote p { margin: 0; }

/* === Images === */
img {
    max-width: 90%;
    height: auto;
    border-radius: 12px;
    margin: 18pt auto;
    display: block;
    box-shadow: 0 2px 12px rgba(0,0,0,0.10);
}
.image-caption {
    text-align: center;
    font-size: 9pt;
    color: #666;
    font-style: italic;
    margin-top: 6pt;
    margin-bottom: 14pt;
}

/* === Horizontal Rule === */
hr {
    border: none;
    border-top: 1.5px solid #e0e0e0;
    margin: 18pt 0;
}

/* === Page Break Control === */
h1, h2, h3 { page-break-after: avoid; }
pre, table, blockquote, img { page-break-inside: avoid; }

/* === Cover Page (for composed documents) === */
.cover-page {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 85vh;
    text-align: center;
    page-break-after: always;
}
.cover-page h1 {
    font-size: 36pt;
    border: none;
    color: #0f0f23;
    margin-bottom: 16pt;
}
.cover-page .subtitle {
    font-size: 14pt;
    color: #555;
    margin-bottom: 8pt;
}
.cover-page .metadata {
    font-size: 10pt;
    color: #888;
    margin-top: 24pt;
}

/* === Section Dividers === */
.section {
    margin-bottom: 20pt;
}
.section + .section h2 {
    margin-top: 30pt;
}

/* === Footer === */
.document-footer {
    margin-top: 40pt;
    padding-top: 10pt;
    border-top: 1px solid #e0e0e0;
    font-size: 8pt;
    color: #999;
    text-align: center;
}
"""

# ─── Theme Variants ──────────────────────────────────────────────────
THEME_OVERRIDES = {
    "academic": """
        body { font-family: 'Georgia', 'Times New Roman', serif; font-size: 12pt; line-height: 1.8; }
        h1 { font-size: 24pt; border-bottom: 2px solid #333; color: #111; }
        h2 { font-size: 18pt; border-bottom: 1px solid #666; color: #222; }
        p { text-indent: 20pt; }
        p:first-child, h1 + p, h2 + p, h3 + p { text-indent: 0; }
    """,
    "minimal": """
        body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; }
        h1 { border-bottom: 1px solid #ddd; font-weight: 300; font-size: 28pt; }
        h2 { border-bottom: none; font-weight: 400; color: #555; }
        blockquote { border-left-color: #ccc; background: #fafafa; }
        thead { background: #f5f5f5; color: #333; }
        th { border-color: #ddd; }
    """,
    "dark": """
        body { background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #e0e0ff; border-bottom-color: #6c63ff; }
        h2 { color: #ccccee; border-bottom-color: #3a3a5c; }
        h3 { color: #bbbbdd; }
        h4 { color: #aaaacc; }
        a { color: #8b8bff; }
        p { color: #d0d0e0; }
        li { color: #d0d0e0; }
        pre { background: #0d0d1a; color: #cdd6f4; }
        code { background: #2a2a44; color: #ff79c6; }
        table { border-color: #3a3a5c; }
        thead { background: #2a2a44; color: #e0e0ff; }
        th { border-color: #3a3a5c; color: #e0e0ff; }
        td { border-color: #2a2a44; color: #d0d0e0; }
        tbody tr:nth-child(even) { background: #22223a; }
        blockquote { background: #22223a; border-left-color: #6c63ff; color: #c0c0d8; }
        blockquote p { color: #c0c0d8; }
        hr { border-top-color: #3a3a5c; }
        .cover-page h1 { color: #e0e0ff; }
        .cover-page .subtitle { color: #aaaacc; }
        .cover-page .metadata { color: #8888aa; }
        .image-caption { color: #9999bb; }
        .document-footer { color: #6666aa; border-top-color: #3a3a5c; }
    """,
    "cyberpunk": """
        body { background: #0a0a14; color: #e0e0e8; font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; }
        h1 { color: #00ffcc; border-bottom: 2px solid #ff00aa; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
        h2 { color: #ff00aa; border-bottom: 1px solid #00ffcc40; font-weight: 700; }
        h3 { color: #00ccff; }
        h4 { color: #ffcc00; }
        a { color: #00ffcc; }
        p { color: #c8c8d8; }
        li { color: #c8c8d8; }
        pre { background: #050510; color: #00ffcc; border: 1px solid #00ffcc30; }
        code { background: #1a0a2e; color: #ff00aa; }
        table { border: 1px solid #00ffcc40; }
        thead { background: #1a0a2e; color: #00ffcc; }
        th { border-color: #00ffcc40; color: #00ffcc; }
        td { border-color: #1a1a2e; color: #d0d0e0; }
        tbody tr:nth-child(even) { background: #0d0d1a; }
        blockquote { background: #0d0d1a; border-left: 4px solid #ff00aa; color: #c0c0d8; }
        blockquote p { color: #c0c0d8; }
        hr { border-top: 1px dashed #00ffcc40; }
        img { border-radius: 8px; box-shadow: 0 0 20px rgba(0,255,204,0.15); }
        .cover-page h1 { color: #00ffcc; text-shadow: 0 0 30px rgba(0,255,204,0.3); }
        .cover-page .subtitle { color: #ff00aa; }
        .cover-page .metadata { color: #666688; }
        .image-caption { color: #888899; }
        .document-footer { color: #444466; border-top-color: #00ffcc30; }
    """,
    "elegant": """
        body { background: #faf8f4; color: #2c2420; font-family: 'Georgia', 'Palatino', 'Book Antiqua', serif; font-size: 11.5pt; line-height: 1.8; }
        h1 { color: #3a2010; border-bottom: 2px solid #c8a060; font-weight: 400; font-size: 28pt; letter-spacing: 1px; }
        h2 { color: #4a3020; border-bottom: 1px solid #d4b880; font-weight: 400; font-size: 20pt; }
        h3 { color: #5a4030; font-style: italic; }
        h4 { color: #6a5040; }
        a { color: #8a5a30; }
        p { color: #3c3430; text-indent: 16pt; }
        p:first-child, h1 + p, h2 + p, h3 + p { text-indent: 0; }
        li { color: #3c3430; }
        pre { background: #f0ece4; color: #3a2010; border: 1px solid #d4c8b0; border-radius: 4px; }
        code { background: #f0ece4; color: #8a4a20; }
        thead { background: #3a2010; color: #faf8f4; }
        th { border-color: #3a2010; }
        td { border-color: #d4c8b0; }
        tbody tr:nth-child(even) { background: #f4f0e8; }
        blockquote { background: #f4f0e8; border-left: 4px solid #c8a060; color: #4a3828; font-style: italic; }
        blockquote p { color: #4a3828; text-indent: 0; }
        hr { border-top: 1px solid #d4c8b0; }
        img { border-radius: 8px; box-shadow: 0 2px 8px rgba(60,40,20,0.12); }
        .cover-page h1 { color: #3a2010; }
        .cover-page .subtitle { color: #6a5040; font-style: italic; }
        .cover-page .metadata { color: #9a8a7a; }
        .image-caption { color: #8a7a6a; }
        .document-footer { color: #b0a090; border-top-color: #d4c8b0; }
    """,
    "pastel": """
        body { background: #fef6ff; color: #3a2040; font-family: 'Avenir Next', 'Nunito', 'Segoe UI', sans-serif; }
        h1 { color: #8a3a8a; border-bottom: 2.5px solid #e0a0d0; font-weight: 600; }
        h2 { color: #6a4a8a; border-bottom: 1.5px solid #e8c0e0; }
        h3 { color: #7a5a9a; }
        h4 { color: #9a6aaa; }
        a { color: #aa60aa; }
        p { color: #4a3050; }
        li { color: #4a3050; }
        pre { background: #f8eef8; color: #5a3060; border: 1px solid #e0c0e0; }
        code { background: #fce8fc; color: #aa40aa; }
        thead { background: #d8a0d0; color: #ffffff; }
        th { border-color: #d0a0c8; color: #fff; }
        td { border-color: #f0d8f0; color: #4a3050; }
        tbody tr:nth-child(even) { background: #faf0fa; }
        blockquote { background: #faf0fa; border-left: 4px solid #d0a0d0; color: #5a3060; }
        blockquote p { color: #5a3060; }
        hr { border-top: 1.5px solid #e8d0e8; }
        img { border-radius: 16px; box-shadow: 0 3px 14px rgba(160,80,160,0.12); }
        .cover-page h1 { color: #8a3a8a; }
        .cover-page .subtitle { color: #aa6aaa; }
        .cover-page .metadata { color: #c0a0c0; }
        .image-caption { color: #b090b0; }
        .document-footer { color: #c8b0c8; border-top-color: #e8d0e8; }
    """,
}

# ─── Draft Storage ───────────────────────────────────────────────────
DRAFTS_DIR = Path(os.getcwd()) / "memory" / "core" / "docs" / "drafts"


def _get_draft_path(doc_id: str) -> Path:
    return DRAFTS_DIR / f"{doc_id}.json"


def _resolve_doc_id(doc_id: str) -> str:
    """Resolve a possibly-wrong doc_id to the actual draft file on disk.

    The LLM often fires start_document + add_section in the same batch,
    guessing the doc_id (e.g. "ernos_void_v2") before start_document returns
    the real one ("doc_1771189852").  Since we enforce one document per session,
    we fall back to the most recently modified draft.
    """
    if _get_draft_path(doc_id).exists():
        return doc_id
    # Try to find the most recently modified draft
    draft_files = sorted(DRAFTS_DIR.glob("doc_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if draft_files:
        resolved = draft_files[0].stem
        logger.warning(f"Document '{doc_id}' not found — auto-resolved to: {resolved}")
        return resolved
    raise FileNotFoundError(f"Document '{doc_id}' not found. Use start_document first.")


def _load_draft(doc_id: str) -> dict:
    path = _get_draft_path(doc_id)
    if not path.exists():
        raise FileNotFoundError(f"Document '{doc_id}' not found. Use start_document first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_draft(doc_id: str, data: dict):
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    _get_draft_path(doc_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _markdown_to_html(text: str) -> str:
    """Convert markdown to HTML. Falls back to wrapping in <p> tags."""
    try:
        import markdown
        return markdown.markdown(
            text,
            extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
            extension_configs={"codehilite": {"css_class": "highlight", "guess_lang": False}},
        )
    except ImportError:
        # Fallback: basic paragraph wrapping
        paragraphs = text.strip().split("\n\n")
        return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)


def _looks_like_html(text: str) -> bool:
    """Check if text contains real HTML tags (not just markdown > or < symbols)."""
    import re
    # Match actual HTML tags like <div>, <p>, <h1 class="x">, </span>, etc.
    return bool(re.search(r'<(?:!DOCTYPE|html|head|body|div|span|p|h[1-6]|ul|ol|li|table|tr|td|th|a|img|br|hr|pre|code|blockquote|section|article|nav|header|footer|style|meta|link|strong|em|b|i)\b[^>]*/?>', text, re.IGNORECASE))


def _looks_like_markdown(text: str) -> bool:
    """Check if text contains markdown formatting indicators."""
    import re
    indicators = [
        r'^#{1,6}\s',        # Headings: # Title
        r'\*\*[^*]+\*\*',    # Bold: **text**
        r'^\s*[-*+]\s',      # Unordered lists: - item
        r'^\s*\d+\.\s',      # Ordered lists: 1. item
        r'^\s*>\s',          # Blockquotes: > text
        r'```',              # Fenced code blocks
        r'\|.*\|.*\|',       # Tables: | a | b |
        r'\[.+\]\(.+\)',     # Links: [text](url)
    ]
    matches = sum(1 for pat in indicators if re.search(pat, text, re.MULTILINE))
    return matches >= 2  # Need at least 2 markdown indicators


def _build_styled_html(body_html: str, theme: str = "professional", title: str = "", custom_css: str = "") -> str:
    """Wrap HTML body in a full document with professional CSS."""
    theme_css = THEME_OVERRIDES.get(theme, "")
    # Custom CSS overrides theme defaults
    extra_css = f"\n/* Custom CSS */\n{custom_css}" if custom_css else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{PDF_STYLESHEET}
{theme_css}
{extra_css}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


def _image_to_base64(image_path: str) -> str:
    """Convert an image file to a base64 data URI."""
    path = Path(image_path)
    if not path.exists():
        # Try relative to cwd
        path = Path(os.getcwd()) / image_path
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    ext = path.suffix.lower().lstrip(".")
    mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml"}
    mime = mime_map.get(ext, "image/png")

    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


# ═══════════════════════════════════════════════════════════════════════
# TOOL 1: Quick PDF (upgraded with CSS injection)
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="generate_pdf",
    description=(
        "Generate a ONE-SHOT professionally styled PDF from content or a URL. "
        "Use this for quick, single-pass PDF generation. For multi-section composed documents, "
        "use start_document → add_section → render_document instead. "
        "Pass content as MARKDOWN TEXT (headings, bold, lists, code blocks, tables) — "
        "the system auto-converts to beautifully styled HTML with professional typography. "
        "Do NOT write raw HTML; markdown produces better results. "
        "For URLs, set is_url=True. "
        "MANDATORY FORMATTING: Use Roman numeral headings (# I. Title, # II. Title). "
        "Start with an introduction paragraph, then body sections with ### subheadings, "
        "and end with a conclusion/summary section. Use formal prose, bullet points for key items, "
        "and bold terms for emphasis. For research/academic topics, use citations and numbered refs. "
        "Args: target (markdown string or URL), is_url (bool, default False), "
        "theme ('professional'|'academic'|'minimal'|'dark'|'cyberpunk'|'elegant'|'pastel'). "
        "IMPORTANT: This tool sends the PDF to Discord automatically. Do NOT call it twice."
    ),
)
async def generate_pdf(
    target: str,
    is_url: bool = False,
    theme: str = "professional",
    user_id: int = None,
    request_scope: str = "PUBLIC",
    **kwargs,
) -> str:
    """Generate a professionally styled PDF document."""
    try:
        from src.privacy.scopes import PrivacyScope
        from playwright.async_api import async_playwright

        try:
            scope = PrivacyScope[request_scope.upper()]
        except Exception:
            scope = PrivacyScope.PUBLIC

        timestamp = str(int(time.time()))
        filename = f"doc_{timestamp}.pdf"

        if user_id and str(user_id) not in {str(aid) for aid in settings.ADMIN_IDS}:
            base_dir = Path(os.getcwd()) / "memory" / "users" / str(user_id) / "docs" / scope.name.lower()
        else:
            base_dir = Path(os.getcwd()) / "memory" / "core" / "docs"

        base_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(base_dir / filename)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            if is_url:
                logger.info(f"Generating PDF from URL: {target}")
                await page.goto(target, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
            else:
                logger.info("Generating PDF from content")
                # Smart content detection: convert markdown unless it's already proper HTML
                is_html = _looks_like_html(target)
                is_md = _looks_like_markdown(target)

                if is_html and not is_md:
                    # Pure HTML — use as-is
                    logger.info("Content detected as HTML")
                    html_body = target
                elif is_md:
                    # Has markdown formatting — always convert
                    logger.info("Content detected as markdown — converting to HTML")
                    html_body = _markdown_to_html(target)
                else:
                    # Plain text or ambiguous — convert as markdown (safe default)
                    logger.info("Content detected as plain text — converting")
                    html_body = _markdown_to_html(target)

                styled = _build_styled_html(html_body, theme=theme)
                await page.set_content(styled, wait_until="networkidle")
                # Allow fonts and layout to settle before capture
                await page.wait_for_timeout(1500)

            await page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            await browser.close()

        # Log provenance
        from src.security.provenance import ProvenanceManager
        ProvenanceManager.log_artifact(output_path, "pdf", {
            "source": target[:50], "is_url": is_url, "user_id": user_id,
            "scope": request_scope, "theme": theme,
        })

        # NOTE: PDF is NOT auto-sent here. It will be delivered via the
        # normal response flow (extract_files → deliver_response) at the
        # end of the cognition cycle, preventing duplicate sends.

        return f"✅ SUCCESS — PDF generated: {output_path}\nDo NOT call generate_pdf again."

    except Exception as e:
        logger.error(f"PDF Generation Error: {e}")
        return f"PDF Error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# TOOL 2: Start Document (multi-step composition)
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="start_document",
    description=(
        "Start composing a multi-section document. Returns a doc_id for subsequent calls. "
        "Args: title (str), author (str, optional), "
        "theme ('professional'|'academic'|'minimal'|'dark'|'cyberpunk'|'elegant'|'pastel'), "
        "custom_css (str, optional — raw CSS to inject for user-directed themes like "
        "'pink and flowery' or specific color overrides)."
    ),
)
def start_document(
    title: str,
    author: str = "Ernos",
    theme: str = "professional",
    custom_css: str = "",
    **kwargs,
) -> str:
    """Create a new document draft and return its ID."""
    doc_id = f"doc_{int(time.time())}"
    draft = {
        "id": doc_id,
        "title": title,
        "author": author,
        "theme": theme,
        "custom_css": custom_css,
        "created": time.time(),
        "sections": [],
        "status": "draft",
    }
    _save_draft(doc_id, draft)
    logger.info(f"Document started: {doc_id} — '{title}'")
    return (
        f"✅ SUCCESS: Document created: `{doc_id}`\n"
        f"Title: {title}\n"
        f"Theme: {theme}\n"
        f"\n"
        f"DOCUMENT STRUCTURE TEMPLATE — Follow this format:\n"
        f"  Section 1: 'I. Introduction' — Opening context, purpose, and scope of the document.\n"
        f"  Sections 2-N: 'II. [Topic]', 'III. [Topic]', etc. — Core body sections with ### subheadings, "
        f"bullet points, and bold key terms. Each section should be substantial (3+ paragraphs).\n"
        f"  Final Section: 'Conclusion' or 'Summary' — Synthesis of key points.\n"
        f"\n"
        f"Use formal prose. Use Roman numerals for section headings. Write at least 3 sections.\n"
        f"Next: add_section(doc_id='{doc_id}', heading='I. Introduction', content='...')"
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 3: Add Section
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="add_section",
    description=(
        "Add a section to a document in progress. "
        "Args: doc_id (str), heading (str), content (str — markdown or HTML), "
        "content_type ('markdown'|'html'|'text', default 'markdown'). "
        "MANDATORY FORMAT: Use Roman numeral headings ('I. Introduction', 'II. Core Analysis', etc.). "
        "Each section MUST have: an opening paragraph, detailed body with ### subheadings, "
        "bullet points (* item), and bold (**key terms**). Write 3+ substantial paragraphs per section. "
        "For the final section, use 'Conclusion' or 'Summary' as heading. "
        "For academic/research topics: use formal prose, citations, and numbered references."
    ),
)
def add_section(
    doc_id: str,
    heading: str,
    content: str,
    content_type: str = "markdown",
    **kwargs,
) -> str:
    """Add a section to an existing document draft."""
    try:
        doc_id = _resolve_doc_id(doc_id)
        draft = _load_draft(doc_id)
    except FileNotFoundError as e:
        return str(e)

    # Reset rendered status so re-render is allowed after edits
    if draft.get("status") == "rendered":
        draft["status"] = "draft"

    # Convert content to HTML
    if content_type == "markdown":
        html = _markdown_to_html(content)
    elif content_type == "text":
        html = f"<p>{content.replace(chr(10), '<br>')}</p>"
    else:
        html = content

    section = {
        "heading": heading,
        "html": html,
        "content_type": content_type,
        "images": [],
    }
    draft["sections"].append(section)
    _save_draft(doc_id, draft)

    idx = len(draft["sections"])
    logger.info(f"Section {idx} added to {doc_id}: '{heading}'")
    return (
        f"✅ SUCCESS: Section {idx} added: '{heading}'\n"
        f"Document now has {idx} section(s).\n"
        f"Next: add more sections, embed_image, or render_document(doc_id='{doc_id}')"
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4: Embed Image
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="embed_image",
    description=(
        "Embed an image into a document section. The image is base64-encoded "
        "directly into the PDF. Args: doc_id (str), image_path (str — absolute or "
        "relative path), caption (str, optional), width (str, e.g. '80%' or '400px', "
        "optional), section_index (int, optional — 0-indexed, defaults to last section)."
    ),
)
def embed_image(
    doc_id: str,
    image_path: str,
    caption: str = "",
    width: str = "80%",
    section_index: int = -1,
    **kwargs,
) -> str:
    """Embed an image into a document section via base64 encoding."""
    try:
        doc_id = _resolve_doc_id(doc_id)
        draft = _load_draft(doc_id)
    except FileNotFoundError as e:
        return str(e)

    if not draft["sections"]:
        return f"Error: Document '{doc_id}' has no sections. Add a section first."

    # Resolve section index
    if section_index == -1:
        section_index = len(draft["sections"]) - 1
    if section_index < 0 or section_index >= len(draft["sections"]):
        return f"Error: Invalid section_index {section_index}. Document has {len(draft['sections'])} sections."

    try:
        data_uri = _image_to_base64(image_path)
    except FileNotFoundError as e:
        return str(e)

    image_entry = {
        "data_uri": data_uri,
        "caption": caption,
        "width": width,
    }
    draft["sections"][section_index]["images"].append(image_entry)
    _save_draft(doc_id, draft)

    section_name = draft["sections"][section_index]["heading"]
    logger.info(f"Image embedded in section '{section_name}' of {doc_id}")
    return (
        f"Image embedded in section '{section_name}'.\n"
        f"Caption: '{caption}'\n"
        f"Next: add more images/sections, or render_document(doc_id='{doc_id}')"
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4b: Edit Section (update existing section)
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="edit_section",
    description=(
        "Edit an existing section in a document draft. Use this to revise content "
        "based on user feedback WITHOUT recreating the document from scratch. "
        "Args: doc_id (str), section_index (int, 0-indexed), "
        "heading (str, optional — new heading), content (str, optional — new content as markdown), "
        "content_type ('markdown'|'html'|'text', default 'markdown')."
    ),
)
def edit_section(
    doc_id: str,
    section_index: int,
    heading: str = "",
    content: str = "",
    content_type: str = "markdown",
    **kwargs,
) -> str:
    """Edit an existing section in a document draft."""
    try:
        doc_id = _resolve_doc_id(doc_id)
        draft = _load_draft(doc_id)
    except FileNotFoundError as e:
        return str(e)

    if section_index < 0 or section_index >= len(draft["sections"]):
        return f"Error: Invalid section_index {section_index}. Document has {len(draft['sections'])} sections (0-indexed)."

    section = draft["sections"][section_index]
    changes = []

    if heading:
        section["heading"] = heading
        changes.append(f"heading → '{heading}'")

    if content:
        if content_type == "markdown":
            section["html"] = _markdown_to_html(content)
        elif content_type == "text":
            section["html"] = f"<p>{content.replace(chr(10), '<br>')}</p>"
        else:
            section["html"] = content
        section["content_type"] = content_type
        changes.append("content updated")

    # Reset rendered status so re-render is allowed
    if draft.get("status") == "rendered":
        draft["status"] = "draft"

    _save_draft(doc_id, draft)
    logger.info(f"Section {section_index} edited in {doc_id}: {', '.join(changes)}")
    return (
        f"✅ SUCCESS: Section {section_index} edited: {', '.join(changes)}.\n"
        f"Next: render_document(doc_id='{doc_id}', force=True) to re-render with changes."
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4c: Remove Section
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="remove_section",
    description=(
        "Remove a section from a document draft by index. "
        "Args: doc_id (str), section_index (int, 0-indexed)."
    ),
)
def remove_section(
    doc_id: str,
    section_index: int,
    **kwargs,
) -> str:
    """Remove a section from a document draft."""
    try:
        doc_id = _resolve_doc_id(doc_id)
        draft = _load_draft(doc_id)
    except FileNotFoundError as e:
        return str(e)

    if section_index < 0 or section_index >= len(draft["sections"]):
        return f"Error: Invalid section_index {section_index}. Document has {len(draft['sections'])} sections (0-indexed)."

    removed = draft["sections"].pop(section_index)

    # Reset rendered status
    if draft.get("status") == "rendered":
        draft["status"] = "draft"

    _save_draft(doc_id, draft)
    logger.info(f"Section '{removed['heading']}' removed from {doc_id}")
    return (
        f"✅ SUCCESS: Section '{removed['heading']}' removed.\n"
        f"Document now has {len(draft['sections'])} section(s).\n"
        f"Next: render_document(doc_id='{doc_id}', force=True) to re-render."
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4d: Update Document (theme, title, author, custom_css)
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="update_document",
    description=(
        "Update document-level properties on an existing draft. Use this to change "
        "the theme, title, author, or inject custom CSS based on user feedback. "
        "Args: doc_id (str), title (str, optional), author (str, optional), "
        "theme (str, optional — 'professional'|'academic'|'minimal'|'dark'|'cyberpunk'|'elegant'|'pastel'), "
        "custom_css (str, optional — raw CSS to override or extend the theme)."
    ),
)
def update_document(
    doc_id: str,
    title: str = "",
    author: str = "",
    theme: str = "",
    custom_css: str = "",
    **kwargs,
) -> str:
    """Update document-level properties."""
    try:
        doc_id = _resolve_doc_id(doc_id)
        draft = _load_draft(doc_id)
    except FileNotFoundError as e:
        return str(e)

    changes = []
    if title:
        draft["title"] = title
        changes.append(f"title → '{title}'")
    if author:
        draft["author"] = author
        changes.append(f"author → '{author}'")
    if theme:
        draft["theme"] = theme
        changes.append(f"theme → '{theme}'")
    if custom_css:
        draft["custom_css"] = custom_css
        changes.append("custom_css updated")

    if not changes:
        return "No changes specified. Pass at least one of: title, author, theme, custom_css."

    # Reset rendered status
    if draft.get("status") == "rendered":
        draft["status"] = "draft"

    _save_draft(doc_id, draft)
    logger.info(f"Document {doc_id} updated: {', '.join(changes)}")
    return (
        f"✅ SUCCESS: Document updated: {', '.join(changes)}.\n"
        f"Next: render_document(doc_id='{doc_id}', force=True) to re-render with changes."
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 5: Render Document → PDF
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="render_document",
    description=(
        "Render a COMPOSED document (from start_document) to a professional PDF. "
        "Do NOT use this for one-shot PDF generation — use generate_pdf for that. "
        "Compiles all sections and embedded images into a styled document. "
        "Args: doc_id (str), force (bool, default False — set True to re-render an already-rendered doc). "
        "You may call this multiple times during editing — each call overwrites the previous "
        "render. The PDF is delivered to Discord at the end of the response."
    ),
)
async def render_document(doc_id: str, force: bool = False, user_id: int = None, request_scope: str = "PUBLIC", **kwargs) -> str:
    """Render a document draft to a professional PDF."""
    try:
        doc_id = _resolve_doc_id(doc_id)
        draft = _load_draft(doc_id)
    except FileNotFoundError as e:
        return str(e)

    if not draft["sections"]:
        return f"Error: Document '{doc_id}' has no sections. Add content first."

    # Guard: prevent re-rendering already-rendered docs unless forced
    if draft.get("status") == "rendered" and not force:
        existing_path = draft.get("output_path", "unknown")
        return (
            f"✅ ALREADY RENDERED: Document '{doc_id}' was already rendered to PDF.\n"
            f"Path: {existing_path}\n"
            f"The PDF was already sent to Discord. Do NOT call this again.\n"
            f"To re-render after edits, use: render_document(doc_id='{doc_id}', force=True)"
        )

    # Build HTML body
    body_parts = []

    # Cover page
    body_parts.append(
        f'<div class="cover-page">'
        f'<h1>{draft["title"]}</h1>'
        f'<div class="subtitle">by {draft["author"]}</div>'
        f'<div class="metadata">Generated {time.strftime("%B %d, %Y")}</div>'
        f'</div>'
    )

    # Sections
    for section in draft["sections"]:
        section_html = f'<div class="section">'
        section_html += f'<h2>{section["heading"]}</h2>'
        section_html += section["html"]

        # Append embedded images
        for img in section.get("images", []):
            section_html += (
                f'<div style="text-align:center; margin: 14pt 0;">'
                f'<img src="{img["data_uri"]}" style="max-width:{img["width"]};" />'
            )
            if img.get("caption"):
                section_html += f'<div class="image-caption">{img["caption"]}</div>'
            section_html += '</div>'

        section_html += '</div>'
        body_parts.append(section_html)

    # Footer
    body_parts.append(
        f'<div class="document-footer">'
        f'Document ID: {doc_id} | Generated by Ernos Document Composer'
        f'</div>'
    )

    full_body = "\n".join(body_parts)
    styled_html = _build_styled_html(
        full_body,
        theme=draft.get("theme", "professional"),
        title=draft["title"],
        custom_css=draft.get("custom_css", ""),
    )

    # Render PDF
    try:
        from src.privacy.scopes import PrivacyScope
        from playwright.async_api import async_playwright

        try:
            scope = PrivacyScope[request_scope.upper()]
        except Exception:
            scope = PrivacyScope.PUBLIC

        if user_id and str(user_id) not in {str(aid) for aid in settings.ADMIN_IDS}:
            base_dir = Path(os.getcwd()) / "memory" / "users" / str(user_id) / "docs" / scope.name.lower()
        else:
            base_dir = Path(os.getcwd()) / "memory" / "core" / "docs"

        base_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{doc_id}.pdf"
        output_path = str(base_dir / filename)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(styled_html, wait_until="networkidle")
            await page.wait_for_timeout(1500)  # Let fonts and layout settle
            await page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            await browser.close()

        # Provenance
        from src.security.provenance import ProvenanceManager
        ProvenanceManager.log_artifact(output_path, "pdf", {
            "doc_id": doc_id, "title": draft["title"], "sections": len(draft["sections"]),
            "user_id": user_id, "scope": request_scope, "theme": draft.get("theme"),
        })

        # Mark draft as rendered
        draft["status"] = "rendered"
        draft["output_path"] = output_path
        _save_draft(doc_id, draft)

        # NOTE: PDF is NOT auto-sent here. It will be delivered via the
        # normal response flow (extract_files → deliver_response) at the end
        # of the cognition cycle. This allows iterative editing without
        # sending duplicate PDFs to Discord.

        logger.info(f"Document rendered: {output_path}")
        return (
            f"✅ SUCCESS — PDF rendered: {output_path}\n"
            f"Title: {draft['title']}\n"
            f"Sections: {len(draft['sections'])}\n"
            f"Theme: {draft.get('theme', 'professional')}\n"
            f"The PDF will be sent to Discord with your final response.\n"
            f"You may continue editing and re-render if needed."
        )

    except Exception as e:
        logger.error(f"Render Error: {e}")
        return f"Render Error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# TOOL 5: List existing images for reuse
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="list_images",
    description=(
        "List previously generated images with their prompts and file paths. "
        "Use this BEFORE generating new images to check if a suitable one already exists. "
        "Returns image paths, dates, sizes, and original generation prompts. "
        "Args: limit (int, max results, default 20), search (str, optional keyword filter on prompt)."
    ),
)
def list_images(limit: int = 20, search: str = None, **kwargs) -> str:
    """List existing images from the media library with provenance metadata."""
    import datetime

    # Collect image files from known directories
    media_dirs = [
        Path(os.getcwd()) / "memory" / "core" / "media",
        Path(os.getcwd()) / "memory" / "core" / "images",
    ]
    # Also check per-user directories
    users_dir = Path(os.getcwd()) / "memory" / "users"
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            for sub in ["media", "images"]:
                candidate = user_dir / sub
                if candidate.exists():
                    media_dirs.append(candidate)
            # Also check nested media/core paths
            nested = user_dir / "media" / "core"
            if nested.exists():
                media_dirs.append(nested)

    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
    images = []

    for d in media_dirs:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.suffix.lower() in image_exts and f.is_file():
                images.append(f)

    if not images:
        return "No images found in media library."

    # Load provenance for prompt metadata
    prompts_by_filename = {}
    ledger_path = Path(os.getcwd()) / "memory" / "core" / "provenance_ledger.jsonl"
    if ledger_path.exists():
        try:
            for line in ledger_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("type") == "image":
                    fname = entry.get("filename") or ""
                    meta = entry.get("metadata") or {}
                    prompts_by_filename[fname] = {
                        "prompt": meta.get("prompt") or "",
                        "intention": meta.get("intention") or "",
                        "timestamp": entry.get("timestamp") or "",
                    }
        except Exception:
            pass  # Ledger parsing is best-effort

    # Sort by modification time (newest first)
    images.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # Apply search filter
    if search:
        search_lower = search.lower()
        filtered = []
        for img in images:
            prov = prompts_by_filename.get(img.name, {})
            prompt_text = ((prov.get("prompt") or "") + " " + (prov.get("intention") or "")).lower()
            if search_lower in prompt_text or search_lower in img.name.lower():
                filtered.append(img)
        images = filtered

    if not images:
        return f"No images matching '{search}' found."

    # Format output
    results = []
    for img in images[:limit]:
        stat = img.stat()
        size_kb = stat.st_size / 1024
        mod_date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        prov = prompts_by_filename.get(img.name, {})

        entry_str = f"📷 **{img.name}**\n"
        entry_str += f"   Path: {img}\n"
        entry_str += f"   Date: {mod_date} | Size: {size_kb:.0f}KB\n"
        if prov.get("prompt"):
            # Truncate long prompts
            prompt_val = prov["prompt"] or ""
            prompt = prompt_val[:120] + ("..." if len(prompt_val) > 120 else "")
            entry_str += f"   Prompt: {prompt}\n"
        if prov.get("intention"):
            intention_val = prov["intention"] or ""
            intention = intention_val[:80] + ("..." if len(intention_val) > 80 else "")
            entry_str += f"   Intent: {intention}\n"
        results.append(entry_str)

    header = f"Found {len(images)} images"
    if search:
        header += f" matching '{search}'"
    header += f" (showing {min(limit, len(images))}):\n\n"

    return header + "\n".join(results) + (
        f"\n\nTo use in a document: embed_image(doc_id=..., image_path=\"<path above>\")"
        if results else ""
    )


# ═══════════════════════════════════════════════════════════════════════
# TOOL 6: Visual QA — Preview a PDF as an image for multimodal review
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="preview_document",
    description=(
        "Preview a PDF by rendering page 1 as a PNG screenshot. "
        "Use this AFTER render_document or generate_pdf to visually inspect "
        "the output quality. Returns an image path the model can review. "
        "If the result looks bad, adjust content and re-render. "
        "Args: pdf_path (str, path to the PDF file)."
    ),
)
async def preview_document(pdf_path: str, **kwargs) -> str:
    """Render page 1 of a PDF as a PNG for visual QA."""
    try:
        from playwright.async_api import async_playwright

        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            return f"Error: PDF not found at {pdf_path}"

        preview_path = pdf_file.with_suffix(".preview.png")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Open PDF in browser tab
            page = await browser.new_page()
            await page.goto(f"file://{pdf_file.resolve()}", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Screenshot the rendered page
            await page.screenshot(
                path=str(preview_path),
                full_page=False,  # Just viewport (first page)
                type="png",
            )
            await browser.close()

        logger.info(f"Preview generated: {preview_path}")
        return (
            f"Preview image saved: {preview_path}\n"
            "Examine this image to check visual quality (typography, contrast, layout, spacing). "
            "If issues found, adjust the content/theme and re-render."
        )

    except Exception as e:
        logger.error(f"Preview Error: {e}")
        return f"Preview Error: {str(e)}"


# ─── Shared Helpers ──────────────────────────────────────────────────

async def _auto_send_file(output_path: str, filename: str, is_url: bool, source: str, kwargs: dict) -> str:
    """Auto-send generated file to Discord channel."""
    bot = kwargs.get("bot")
    channel_id = kwargs.get("channel_id")
    sent_status = ""

    if bot and channel_id:
        try:
            import discord
            try:
                channel = bot.get_channel(int(channel_id))
                if not channel:
                    channel = await bot.fetch_channel(int(channel_id))
            except Exception as fetch_err:
                logger.warning(f"Could not fetch channel {channel_id}: {fetch_err}")
                channel = None

            if channel:
                file = discord.File(output_path)
                msg = f"📄 **PDF Generated**: `{filename}`"
                if is_url:
                    msg += f"\nSource: <{source}>"
                await channel.send(msg, file=file)
                sent_status = " (Sent to channel)"
                logger.info(f"Sent PDF to channel {channel_id}")
            else:
                sent_status = " (Channel not found)"
        except Exception as send_err:
            logger.error(f"Failed to send PDF to discord: {send_err}")
            sent_status = " (Send failed)"
    else:
        if not bot:
            logger.warning("PDF Auto-Send Skipped: 'bot' instance missing")
        if not channel_id:
            logger.warning("PDF Auto-Send Skipped: 'channel_id' missing")

    return sent_status
