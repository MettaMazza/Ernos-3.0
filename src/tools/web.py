import os
import logging
import ipaddress
import socket
from urllib.parse import urlparse
from .registry import ToolRegistry
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.Web")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0"
]

def _get_headers():
    import random
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
logging.getLogger("ddgs").setLevel(logging.WARNING)


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


def _robust_ddgs_text(query: str, max_results: int = 5) -> list:
    """
    Attempts to fetch results using ddgs backends
    with session recovery and exponential backoff.
    """
    import time
    import random
    
    # Late import via existing helper to ensure dependency check
    DDGS_CLASS = _get_ddgs()
    if not DDGS_CLASS:
        return []

    backends = ['auto']
    errors = []
    max_retries = 3
    base_delay = 2.0
    
    for attempt in range(max_retries):
        for backend in backends:
            try:
                # Re-instantiate session per attempt to recover from broken pipes/timeouts
                with DDGS_CLASS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results, backend=backend))
                    if results:
                        return results
            except Exception as e:
                errors.append(f"try{attempt}_{backend}: {type(e).__name__}({e})")
                continue
                
        # Wait before retrying if all backends failed
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt) + random.uniform(0.5, 2.5)
            logger.debug(f"DDGS rate-limited on '{query}', retrying in {delay:.2f}s...")
            time.sleep(delay)
            
    if errors:
        logger.warning(f"DDGS attempts exhausted. Errors: {errors}")
    # Return empty list instead of None so len(results) safely resolves inside fallbacks
    return []
            
def _fallback_google_search(query: str, max_results: int = 5) -> list:
    """
    Tier 2 fallback: scrape google.com directly using urllib.
    """
    try:
        import urllib.request
        import urllib.parse
        from bs4 import BeautifulSoup

        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}&hl=en"
        
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, "html.parser")
        results = []
        for div in soup.select("div.g"):
            h3 = div.select_one("h3")
            a = div.select_one("a")
            p = div.select_one("div[data-sncf], span.st, div.VwiC3b")
            
            if h3 and a:
                results.append({
                    "title": h3.text.strip(),
                    "href": a.get("href", ""),
                    "body": p.text.strip() if p else "",
                })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        logger.warning(f"Google fallback search failed: {e}")
        return []


def _fallback_bing_search(query: str, max_results: int = 5) -> list:
    """
    Tier 3 fallback: scrape Bing search results using urllib.
    """
    try:
        import urllib.request
        import urllib.parse
        from bs4 import BeautifulSoup

        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded}"
        
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        for li in soup.select("li.b_algo"):
            h2 = li.select_one("h2 a")
            p = li.select_one("div.b_caption p, div.b_algoSlug")
            if h2 and p:
                results.append({
                    "title": h2.text.strip(),
                    "href": h2.get("href", ""),
                    "body": p.text.strip(),
                })
            if len(results) >= max_results:
                break
                
        return results
    except Exception as e:
        logger.warning(f"Bing fallback search also failed: {e}")
        return []

def _fallback_yahoo_search(query: str, max_results: int = 5) -> list:
    """
    Tier 4 fallback: scrape search.yahoo.com directly using urllib.
    """
    try:
        import urllib.request
        import urllib.parse
        from bs4 import BeautifulSoup

        encoded = urllib.parse.quote_plus(query)
        url = f"https://search.yahoo.com/search?p={encoded}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')

        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        for div in soup.select("div.algo"):
            h3 = div.select_one("h3 a") or div.select_one("a")
            p = div.select_one("div.compText, p")
            if h3:
                href = h3.get("href", "")
                title = h3.text.strip()
                if href and title:
                    results.append({
                        "title": title,
                        "href": href,
                        "body": p.text.strip() if p else "",
                    })
            if len(results) >= max_results:
                break
                
        return results
    except Exception as e:
        logger.warning(f"Yahoo fallback search also failed: {e}")
        return []

@ToolRegistry.register(name="search_web", description="Search the internet securely.")
def search_web(query: str, is_autonomy: bool = False, _loader=_get_ddgs, **kwargs) -> str:
    """Performs a real web search using a layered DDGS -> Google -> Bing -> Yahoo fallback architecture."""
    results = []
    
    # Tier 1: DuckDuckGo (via DDGS)
    try:
        results = _robust_ddgs_text(query, max_results=10)
    except Exception as e:
        logger.warning(f"DDGS Tier 1 completely failed: {e}")

    # Tier 2: Google
    if not results:
        logger.info(f"Tier 1 (DDGS) returned no results for '{query}', trying Tier 2 (Google)...")
        results = _fallback_google_search(query, max_results=7)
        
    # Tier 3: Bing
    if not results:
        logger.info(f"Tier 2 (Google) returned no results for '{query}', trying Tier 3 (Bing)...")
        results = _fallback_bing_search(query, max_results=7)

    # Tier 4: Yahoo
    if not results:
        logger.info(f"Tier 3 (Bing) returned no results for '{query}', trying Tier 4 (Yahoo)...")
        results = _fallback_yahoo_search(query, max_results=7)

    # Wrap up
    if not results:
        return "No results found across DDGS, DDG HTML, Bing, and Yahoo. Try a different query."
        
    formatted = []
    for r in results:
        formatted.append(f"Title: {r.get('title', '')}\nLink: {r.get('href', '')}\nSnippet: {r.get('body', '')}")
    
    return "\n---\n".join(formatted)


@ToolRegistry.register(name="browse_site", description="Read a website content.")
def browse_site(url: str, **kwargs) -> str:
    """Scrapes text from a URL."""
    if not _is_safe_url(url):
        return "Error: URL blocked — cannot access private/internal network addresses."
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {"User-Agent": "Ernos/3.0 (Research Bot)"}
        response = requests.get(url, headers=headers, timeout=30)
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


@ToolRegistry.register(
    name="download_file",
    description="Download a file from a URL and host it on the Ernos file server. Returns a local download link the user can open on any device.",
    parameters={"url": "The URL to download the file from", "filename": "Optional custom filename (auto-detected from URL if omitted)"}
)
def download_file_tool(url: str, filename: str = None, **kwargs) -> str:
    """Download a file from a URL, save it to the shared file server, and return a download link."""
    if not _is_safe_url(url):
        return "Error: URL blocked — cannot access private/internal network addresses."
    try:
        import requests
        import tempfile
        from pathlib import Path
        from src.web.file_server import share_file, SHARED_DIR

        headers = _get_headers()
        response = requests.get(url, headers=headers, timeout=120, stream=True)
        response.raise_for_status()

        # Determine filename
        if not filename:
            # Try Content-Disposition header first
            cd = response.headers.get("Content-Disposition", "")
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('" ')
            else:
                # Fall back to URL path
                from urllib.parse import urlparse, unquote
                path = urlparse(url).path
                filename = unquote(Path(path).name) if path and Path(path).name else "download"

        # Sanitize filename
        filename = "".join(c for c in filename if c.isalnum() or c in ".-_ ()").strip()
        if not filename:
            filename = "download"

        # Download to temp file first, then share
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
        size = 0
        try:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
                size += len(chunk)
            tmp.close()

            # Move to shared directory
            download_path = share_file(tmp.name, filename)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        # Build full URL
        port = int(os.environ.get("WEB_PORT", "8420"))
        try:
            import socket
            local_ip = socket.gethostbyname(socket.gethostname())
            if local_ip.startswith("127."):
                # Try to get real LAN IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
        except Exception:
            local_ip = "localhost"

        full_url = f"http://{local_ip}:{port}{download_path}"

        # Human-readable size
        if size > 1024 * 1024:
            size_str = f"{size / 1024 / 1024:.1f} MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} bytes"

        logger.info(f"📥 Downloaded: {filename} ({size_str}) from {url}")
        return f"Downloaded **{filename}** ({size_str}) and hosted it on the file server.\n\nDownload link: {full_url}"

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return f"Download failed: {e}"

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

async def _research_task(
    topic: str,
    max_depth: int,
    channel_id: str,
    user_id: str,
    request_scope: str,
    is_autonomy: bool,
    intention: str = None
):
    """
    Background research task — spawns a full agent (with all tools) instead of the
    old DDGS-only DeepResearcher.  Keeps the fire-and-forget delivery pattern.
    """
    logger.info(f"Background research started for: {topic}")

    try:
        from src.bot import globals
        import discord

        RESEARCH_CHANNEL_ID = 1447560747982000172

        # Get research channel (if available/applicable)
        research_channel = None
        if is_autonomy and request_scope != "PRIVATE" and hasattr(globals.bot, "get_channel"):
            research_channel = globals.bot.get_channel(RESEARCH_CHANNEL_ID)

        # Determine Scope and Directory
        from src.privacy.scopes import PrivacyScope
        try:
            scope = PrivacyScope[request_scope.upper()]
        except Exception:
            scope = PrivacyScope.PUBLIC

        if user_id and user_id != "CORE":
            base_dir = str(data_dir()) + f"/users/{user_id}/research/{scope.name.lower()}"
        else:
            base_dir = "memory/core/research"

        os.makedirs(base_dir, exist_ok=True)
        safe_topic = topic.replace(' ', '_').replace('/', '_')[:50]
        filename = f"{base_dir}/research_{safe_topic}.md"

        # --- SPAWN A FULL RESEARCH AGENT ---
        try:
            from src.agents.spawner import AgentSpawner, AgentSpec

            spec = AgentSpec(
                task=(
                    f"Conduct comprehensive, multi-angle research on the following topic:\n\n"
                    f"**{topic}**\n\n"
                    f"Instructions:\n"
                    f"1. Start with broad web searches to establish the landscape.\n"
                    f"2. Browse the most relevant pages for detailed information.\n"
                    f"3. Search from multiple angles — different perspectives, controversies, recent developments.\n"
                    f"4. Cross-reference findings across sources.\n"
                    f"5. Produce a comprehensive markdown report with:\n"
                    f"   - Executive summary\n"
                    f"   - Key findings organized by theme\n"
                    f"   - Sources cited inline\n"
                    f"   - Areas of uncertainty or conflicting information noted\n\n"
                    f"Be thorough. Use at least 5 different searches and browse at least 3 key pages."
                ),
                max_steps=50,
                timeout=1200,
                scope=request_scope,
                user_id=user_id,
            )

            result = await AgentSpawner.spawn(spec, globals.bot)

            if result.status.value == "completed" and result.output:
                report_text = result.output
            else:
                report_text = f"Research agent failed: {result.error or 'Unknown error'}"

        except Exception as e:
            logger.error(f"Agent-based research failed: {e}")
            report_text = f"Research Error: {e}"

        # Write Report
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_text)

        # KG Extraction — extract extensive triples from the report
        try:
            if globals.bot and globals.bot.cerebrum:
                interaction_lobe = globals.bot.cerebrum.get_lobe_by_name("InteractionLobe")
                if interaction_lobe:
                    researcher = interaction_lobe.get_ability("ResearchAbility")
                    if researcher:
                        await researcher._extract_and_store_knowledge(topic, report_text)
        except Exception as e:
            logger.warning(f"KG Error: {e}")

        # Provenance
        try:
             from src.security.provenance import ProvenanceManager
             ProvenanceManager.log_artifact(filename, "research", {
                "topic": topic, "user_id": user_id, "scope": str(scope), "is_autonomy": is_autonomy,
                "intention": intention
             })
        except Exception:
            logger.warning(f"Provenance logging failed for research task.")

        # Notifications
        completion_msg = f"📄 **Research Complete**: '{topic}'"
        file_attachment = discord.File(filename)

        # 1. To Research Channel (if autonomy)
        if is_autonomy and research_channel:
             try:
                 await research_channel.send(completion_msg, file=file_attachment)
             except:
                 await research_channel.send(completion_msg + f"\n(File saved to {filename})")

        # 2. To Delivery Channel (User Origin)
        elif not is_autonomy:
            delivery_channel = None
            if channel_id and hasattr(globals.bot, "get_channel"):
                delivery_channel = globals.bot.get_channel(int(channel_id))

            # Fallback to active_message context if available
            if not delivery_channel:
                msg = globals.active_message.get()
                if msg:
                     delivery_channel = msg.channel

            if delivery_channel:
                 # Re-create file object for second send if needed
                 file_attachment_user = discord.File(filename)
                 await delivery_channel.send(completion_msg, file=file_attachment_user)

    except Exception as e:
        logger.error(f"Background research task failed: {e}")


@ToolRegistry.register(name="start_deep_research", description="Launch an async deep research task.")
async def start_deep_research(
    topic: str,
    max_depth: int = 2,
    research_channel_id: int = None,
    user_id: int = None,
    request_scope: str = "PUBLIC",
    is_autonomy: bool = False,
    intention: str = None
) -> str:
    """
    Kicks off a background agent loop that researches a topic in depth and
    compiles a final markdown report. Returns immediately with an acknowledgment.
    """
    try:
        from src.bot import globals
        import asyncio
        import discord
        
        # Infer user_id/channel if missing
        local_research_channel_id = research_channel_id
        if not user_id and globals.active_message.get():
            user_id = str(globals.active_message.get().author.id)
            if not local_research_channel_id:
                local_research_channel_id = str(globals.active_message.get().channel.id)
        
        if not user_id:
            is_autonomy = True
            user_id = "CORE"

        # Check loop
        if globals.bot and hasattr(globals.bot, 'loop'):
            # FIRE AND FORGET
            asyncio.create_task(_research_task(
                topic, max_depth, local_research_channel_id, user_id, request_scope, is_autonomy, intention
            ))
            status = "Background Task Spawned"
        else:
            # Fallback for testing without running loop
            await _research_task(topic, max_depth, local_research_channel_id, user_id, request_scope, is_autonomy, intention)
            status = "Task Ran Synchronously (Test Mode)"
            
        return (
            f"[TOOL RESULT: start_deep_research] Research task for '{topic}' has been launched as an ASYNCHRONOUS BACKGROUND PROCESS. "
            f"Status: {status}.\n\n"
            f"[CRITICAL INSTRUCTION]: The deep research report is being compiled IN THE BACKGROUND and has NOT been returned to you yet. "
            f"You have ZERO research results from this tool. "
            f"Do NOT cite, summarize, list, or invent ANY specific facts, names, dates, bills, events, or statistics about '{topic}'. "
            f"You may ONLY use data explicitly returned by OTHER tools (e.g. search_web) in this turn. "
            f"Do NOT say 'initial highlights' or 'verified data from the retrieval' — you have NONE from this tool. "
            f"Tell the user: 'I have initiated a deep research process on [topic]. The full report will be delivered shortly.' "
            f"Output ONLY a brief acknowledgment that research has started."
        )

    except Exception as e:
        return f"Deep Research Launch Error: {e}"
