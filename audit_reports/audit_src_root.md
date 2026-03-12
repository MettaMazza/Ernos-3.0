# Comprehensive Codebase Audit: `src/` Root Files

**Date:** 2026-02-23
**Module Path:** `src/` (Root level python files: `main.py`, `scheduler.py`, `silo_manager.py`, `feature_x.py`)
**Purpose:** Entry point initialization, background task scheduling, and Discord channel privacy management (Silos).

## Overview
These four files manage the highest-level execution loop, background timers, and the specialized "Silo" privacy protocol within Discord.

## File-by-File Analysis

### 1. `main.py`
*   **Role:** The application entry point.
*   **Analysis:** Initializes the `ErnosBot` and the FastAPI web server concurrently. It explicitly silences noisy external libraries (`phonemizer`, `espeakng`, `neo4j`, etc.) to keep terminal output clean for the AI's dynamic context. Reads `DISCORD_TOKEN` from the environment.
*   **Direct Quote:**
    ```python
    async def main():
        ...
        bot = ErnosBot()
        # Start Web Server alongside Discord bot
        async def start_web():
            from src.web.web_server import start_web_server
            await start_web_server(bot)
        ...
        # Run both Discord bot and Web server concurrently
        web_task = asyncio.create_task(start_web())
        await bot.start(settings.DISCORD_TOKEN)
    ```

### 2. `scheduler.py`
*   **Role:** Background task manager.
*   **Analysis:** A native `asyncio` wrapper for scheduling daily and ad-hoc background tasks without relying on external dependencies like `APScheduler` or `cron`. Crucially responsible for triggering the `BackupManager.daily_backup` at 14:00 (2 PM) daily.
*   **Direct Quote:**
    ```python
    async def setup_backup_scheduler(bot=None):
        ...
        scheduler.add_daily_task(
            name="daily_backup",
            hour=14,  # 2pm
            minute=0,
            coro_func=backup_mgr.daily_backup
        )
    ```

### 3. `silo_manager.py`
*   **Role:** Multi-user secure context manager for Discord.
*   **Analysis:** Enforces "Protocol §14.3" which mandates that a secure private thread ("Silo") will only be created if proposed in a channel with at least 2 humans and the bot. It requires unanimous consent via reactions (✅) or explicit text confirmations (`yes`, `confirm`). It also dictates a strict turn-taking logic where Ernos only replies once all human participants have spoken.
*   **Direct Quote:**
    ```python
    class SiloManager:
        '''
        Manages Silos - Private threads within public channels.
        Strictly follows §14.3: Triggered by Bot + 2 or more Humans (excluding bot).
        '''
        ...
        async def should_bot_reply(self, message: discord.Message) -> bool:
            '''Turn-taking logic: Bot only replies if it is in a Silo and all humans have spoken.'''
    ```

### 4. `feature_x.py`
*   **Role:** Unknown / Deprecated.
*   **Analysis:** Contains only 1 line of text: `new code`. It is likely a leftover test file or artifact from previous development.
*   **Direct Quote:**
    ```python
    new code
    ```

## Conclusion
The root files properly isolate the entry loop (`main.py`) from background timers (`scheduler.py`) and specialized Discord privacy rules (`silo_manager`). The existence of `feature_x.py` reveals a tiny bit of clutter in the source root.

## Status 
Audited fully.
