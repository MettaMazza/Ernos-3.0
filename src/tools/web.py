import os
import logging
import ipaddress
import socket
from urllib.parse import urlparse
from .registry import ToolRegistry

logger = logging.getLogger("Tools.Web")


def _is_safe_url(url: str) -> bool:
    """Block requests to private/internal network addresses (SSRF protection)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        # Block obvious local hostnames
        if hostname in ("localhost", "0.0.0.0", "[::]"):
            return False
        # Resolve and check IP
        ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
            return False
        return True
    except Exception:
        return False


def _get_ddgs():
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        return None


@ToolRegistry.register(name="search_web", description="Search the internet using DuckDuckGo.")
def search_web(query: str, is_autonomy: bool = False, _loader=_get_ddgs, **kwargs) -> str:
    """Performs a real web search."""
    try:
        DDGS = _loader()
        if DDGS is None:
             raise ImportError("duckduckgo-search module not found")

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        
        if not results:
            return "No results found."
            
        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}")
        
        return "\n---\n".join(formatted)
    except ImportError:
        return "Error: ddgs module not found. Please install dependencies."
    except Exception as e:
        return f"Search Error: {e}"


@ToolRegistry.register(name="browse_site", description="Read a website content.")
def browse_site(url: str, **kwargs) -> str:
    """Scrapes text from a URL."""
    if not _is_safe_url(url):
        return "Error: URL blocked — cannot access private/internal network addresses."
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {"User-Agent": "Ernos/3.0 (Research Bot)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strip scripts and styles
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        
        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        total_chars = len(text)
        return f"Content of {url} ({total_chars} chars):\n[DOCUMENT COMPLETE]\n\n{text}"
    except Exception as e:
        return f"Browse Error: {e}"

@ToolRegistry.register(name="check_world_news", description="Fetch usage headlines via RSS.")
def check_world_news(category: str = "general", is_autonomy: bool = False, **kwargs) -> str:
    """
    Fetches news from RSS feeds.
    Categories: general, tech, science, business.
    """
    try:
        import feedparser
        feeds = {
            "general": "http://feeds.bbci.co.uk/news/rss.xml",
            "tech": "http://feeds.feedburner.com/TechCrunch",
            "science": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
            "business": "https://feeds.bloomberg.com/markets/news.rss"
        }
        
        url = feeds.get(category.lower(), feeds["general"])
        feed = feedparser.parse(url)
        
        if not feed.entries:
            return f"No news found for {category}."
            
        headlines = []
        for entry in feed.entries[:5]:
            headlines.append(f"- {entry.title} ({entry.link})")
            
        return f"Latest {category.title()} News:\n" + "\n".join(headlines)
    except Exception as e:
        return f"News Error: {e}"

@ToolRegistry.register(name="start_deep_research", description="Launch an async deep research task.")
async def start_deep_research(topic: str, request_scope: str = "PUBLIC", user_id: str = None, is_autonomy: bool = False, channel_id: str = None) -> str:
    """
    Initiates a background deep research process.
    (MVP: Performs multi-angle search immediately).
    
    SECURITY: Output path determined by request scope and user.
    
    Args:
        topic: Research topic
        request_scope: Privacy scope (PUBLIC/PRIVATE/CORE)
        user_id: User who requested (None = CORE/autonomy)
        is_autonomy: If True, send .md to research channel; if False, return path for user
    """
    RESEARCH_CHANNEL_ID = 1447560747982000172
    
    try:
        from src.bot import globals
        import discord
        
        # Infer user_id if missing
        if not user_id and globals.active_message.get():
            user_id = str(globals.active_message.get().author.id)
        
        # Force autonomy flag if no user_id
        if not user_id:
            is_autonomy = True
            user_id = "CORE"

        # Get research channel for progress updates (only for autonomy + non-PRIVATE scope)
        research_channel = None
        if is_autonomy and request_scope != "PRIVATE" and hasattr(globals.bot, "get_channel"):
            research_channel = globals.bot.get_channel(RESEARCH_CHANNEL_ID)
            
        if research_channel:
            await research_channel.send(f"🧪 **Deep Research Initiated**: '{topic}'")

        # MVP: Perform 3 sub-searches and synthesize.
        angles = [f"{topic} overview", f"{topic} controversy", f"{topic} future outlook"]
        report = [f"### Deep Research: {topic}"]
        
        from ddgs import DDGS
        
        with DDGS() as ddgs:
            for angle in angles:
                if research_channel:
                    await research_channel.send(f"🔍 Scanning angle: `{angle}`...")
                    
                results = list(ddgs.text(angle, max_results=2))
                if results:
                    report.append(f"\n#### Angle: {angle}")
                    for r in results:
                         report.append(f"- {r['title']}: {r['href']}")
                         
        # USER-SCOPED STORAGE: Route to appropriate directory
        report_text = "\n".join(report)
        safe_topic = topic.replace(' ', '_').replace('/', '_')[:50]
        
        # Determine scope
        from src.privacy.scopes import PrivacyScope
        try:
            scope = PrivacyScope[request_scope.upper()]
        except Exception:
            scope = PrivacyScope.PUBLIC
        
        # Route to user-scoped research directory
        if user_id and user_id != "CORE":
            # User research: memory/users/{user_id}/research/{scope}/
            base_dir = f"memory/users/{user_id}/research/{scope.name.lower()}"
        else:
            # Autonomy/CORE research: memory/core/research/
            base_dir = "memory/core/research"
        
        os.makedirs(base_dir, exist_ok=True)
        filename = f"{base_dir}/research_{safe_topic}.md"
            
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_text)
        
        # KG AUTO-EXTRACTION: Store research topic to Knowledge Graph
        try:
            if globals.bot and globals.bot.cerebrum:
                memory_lobe = globals.bot.cerebrum.get_lobe_by_name("MemoryLobe")
                if memory_lobe:
                    ontologist = memory_lobe.get_ability("OntologistAbility")
                    if ontologist:
                        # Create relationship: "Ernos" -> [RESEARCHED] -> "Topic"
                        await ontologist.execute("Ernos", "RESEARCHED", topic)
                        logger.info(f"KG: Indexed research topic '{topic}'")
        except Exception as kg_error:
            logger.warning(f"KG extraction warning: {kg_error}")
        
        # PROVENANCE: Cryptographically sign and log this artifact
        try:
            from src.security.provenance import ProvenanceManager
            ProvenanceManager.log_artifact(filename, "research", {
                "topic": topic,
                "user_id": user_id,
                "scope": scope.name if hasattr(scope, 'name') else str(scope),
                "is_autonomy": is_autonomy
            })
        except Exception as prov_error:
            logger.warning(f"Provenance logging warning: {prov_error}")
        
        # Channel Routing: Autonomy research .md files go to research channel
        if is_autonomy and research_channel:
            try:
                file = discord.File(filename)
                await research_channel.send(
                    f"✅ **Autonomy Research Complete**: '{topic}'",
                    file=file
                )
            except Exception as e:
                await research_channel.send(f"✅ **Research Complete**: '{topic}'\nSaved to: `{filename}`")
        elif not is_autonomy:
            # User-initiated: deliver .md back to originating channel (DM or guild)
            try:
                delivery_channel = None
                if channel_id and hasattr(globals.bot, "get_channel"):
                    delivery_channel = globals.bot.get_channel(int(channel_id))
                if not delivery_channel and globals.active_message.get():
                    delivery_channel = globals.active_message.get().channel
                if delivery_channel:
                    file = discord.File(filename)
                    await delivery_channel.send(
                        f"📄 **Research Complete**: '{topic}'",
                        file=file
                    )
                    logger.info(f"Delivered research '{topic}' to channel {delivery_channel.id}")
            except Exception as e:
                logger.warning(f"Research delivery failed (non-fatal): {e}")
        
        return f"Deep Research initialized. Preliminary data saved to {filename}.\nSummary:\n{report_text[:5000]}..."
    except Exception as e:
        return f"Deep Research Error: {e}"

