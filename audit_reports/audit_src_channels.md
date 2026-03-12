# Audit Report: `src/channels/` (Communication Adapters)

## Overview
The `src/channels/` directory implements a platform-agnostic Channel Adapter Framework. This architecture entirely decouples Ernos's cognitive core from specific chat SDKs (like `discord.py`). It defines unified data structures (`UnifiedMessage`, `OutboundResponse`) that all inbound platform messages are parsed into, and outbound responses are formatted from. 

The `ChannelManager` registers active adapters, allowing Ernos to operate across Discord, Telegram, Matrix, and a Web UI simultaneously or interchangeably.

---

## File-by-File Analysis

### 1. `types.py` (Unified Data Structures)
**Functionality:** Defines the core data classes that abstract away platform-specific messaging quirks.
**Key Mechanisms:**
- `Attachment`: Normalizes file uploads with lazily loaded byte data.
- `UnifiedMessage`: The grand unifier. Strips null bytes (security), caps content length to 4000 characters (anti-flooding), and exposes helper properties for filtering image vs. document attachments.
- `OutboundResponse`: Represents the cognitive core's reply, including files, emoji reactions, and TTS audio paths.
**Quote:**
```python
@dataclass
class UnifiedMessage:
    # ...
    def __post_init__(self):
        """Validate and sanitize on construction."""
        # Cap content length to prevent context flooding
        if len(self.content) > self.MAX_CONTENT_LENGTH:
            self.content = self.content[:self.MAX_CONTENT_LENGTH]
        # Strip null bytes (common in binary injection attempts)
        self.content = self.content.replace('\x00', '')
```

### 2. `base.py` & `manager.py` (Architecture)
**Functionality:**
- **`ChannelAdapter` (base.py):** Abstract base class defining the required contract for platforms: `normalize()`, `send_response()`, `add_reaction()`, `fetch_attachment_data()`, and `format_mentions()`. Mention formatting is critical to prevent cross-platform spoofing.
- **`ChannelManager` (manager.py):** A simple runtime registry (`_adapters: Dict[str, ChannelAdapter]`) that stores and retrieves instantiated adapters by their platform name.

### 3. `discord_adapter.py`
**Functionality:** The primary, fully implemented adapter utilizing `discord.py`.
**Key Mechanisms:**
- **Normalization:** Accurately detects DM vs. Server context across standard channels, private threads, and guildless channels.
- **Chunking:** Safely splits OutboundResponses exceeding Discord's 2000-character limit into multiple messages.
- **Mention Parsing:** Uses regex lookbehinds to securely wrap flat `@userID` text produced by the LLM into Discord's native `<@userID>` clickable format.
**Quote:**
```python
async def format_mentions(self, text: str) -> str:
    """
    Convert bare @userID mentions to Discord's <@userID> format.
    ... Uses negative lookbehind to avoid double-wrapping ...
    """
    return re.sub(r"(?<!<)@(\d{17,20})", r"<@\1>", text)
```

### 4. `telegram_adapter.py` & `matrix_adapter.py` (Stubs)
**Functionality:** "v3.4 Rhizome" stubs designed to be activated once `python-telegram-bot` and `matrix-nio` are installed.
**Key Mechanisms:**
- They accurately trace the data structures of their respective APIs (e.g., Matrix's `m.room.message` payloads and Telegram's `Update` objects containing photo/document arrays) and map them to `UnifiedMessage`.
- They currently stand as functional architectures awaiting dependency installation.

### 5. `web_adapter.py`
**Functionality:** Enables Ernos to run via a REST/WebSocket interface for web frontends.
**Key Mechanisms:**
- Maintains a registry of active WebSockets keyed by `session_id`.
- Attempts to stream `OutboundResponse` objects directly down the WebSocket.
- Uses a fallback `_response_queue` array for older HTTP polling clients if the WebSocket connection is dropped.
**Quote:**
```python
    def get_responses(self, session_id: str) -> list:
        """Retrieve and clear queued responses for a session (polling fallback)."""
        responses = self._response_queue.pop(session_id, [])
        return responses
```

---

## Technical Debt & Observations
1.  **Security Posture:** `UnifiedMessage` actively strips null bytes (`\x00`), which is excellent for preventing zero-byte injection attacks downstream in C-based libraries or file saving routines.
2.  **Missing SDKs:** The Telegram and Matrix adapters are currently un-executable stubs as their imports and underlying bot instances are not instantiated.
3.  **Discord Dominance:** Despite the abstract framework, Discord remains the clearly favored and most robustly implemented channel.
