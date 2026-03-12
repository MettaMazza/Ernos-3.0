"""
Ernos File Server — Share files across devices over WiFi.

Serves files from the `shared/` directory via HTTP. Any device on the
local network can browse and download files from:

    http://<your-ip>:8420/files/

Ernos can share files by copying them into `shared/` (via the share_file tool).
"""
import logging
import mimetypes
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

logger = logging.getLogger("Web.FileServer")

# Shared files directory (project root / shared/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SHARED_DIR = PROJECT_ROOT / "shared"
SHARED_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/files", tags=["files"])


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _file_icon(name: str) -> str:
    """Get an emoji icon based on file extension."""
    ext = Path(name).suffix.lower()
    icons = {
        ".apk": "📱", ".pdf": "📄", ".txt": "📝", ".md": "📝",
        ".py": "🐍", ".js": "📜", ".kt": "📜", ".java": "☕",
        ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️", ".gif": "🖼️", ".webp": "🖼️",
        ".mp3": "🎵", ".wav": "🎵", ".ogg": "🎵", ".flac": "🎵",
        ".mp4": "🎬", ".mkv": "🎬", ".avi": "🎬",
        ".zip": "📦", ".tar": "📦", ".gz": "📦", ".7z": "📦",
        ".json": "📋", ".csv": "📊", ".html": "🌐",
    }
    return icons.get(ext, "📎")


@router.get("/", response_class=HTMLResponse)
async def list_files(request: Request):
    """Browsable file listing with a clean mobile-friendly UI."""
    files = []
    if SHARED_DIR.exists():
        for f in sorted(SHARED_DIR.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": _human_size(stat.st_size),
                    "size_bytes": stat.st_size,
                    "icon": _file_icon(f.name),
                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                })

    host = request.headers.get("host", "localhost:8420")

    file_rows = ""
    for f in files:
        file_rows += f"""
        <a href="/files/download/{f['name']}" class="file-row">
            <span class="icon">{f['icon']}</span>
            <div class="file-info">
                <span class="name">{f['name']}</span>
                <span class="meta">{f['size']} · {f['modified']}</span>
            </div>
            <span class="download">⬇</span>
        </a>"""

    if not files:
        file_rows = '<div class="empty">No files shared yet.</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ernos Files</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 24px 20px;
            border-bottom: 1px solid #2a2a4a;
        }}
        .header h1 {{
            font-size: 22px;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header .subtitle {{
            font-size: 13px;
            color: #888;
            margin-top: 4px;
        }}
        .file-list {{
            padding: 8px;
        }}
        .file-row {{
            display: flex;
            align-items: center;
            padding: 16px 12px;
            border-bottom: 1px solid #1a1a2e;
            text-decoration: none;
            color: inherit;
            border-radius: 8px;
            transition: background 0.15s;
        }}
        .file-row:hover, .file-row:active {{
            background: #1a1a2e;
        }}
        .icon {{
            font-size: 28px;
            margin-right: 14px;
            flex-shrink: 0;
        }}
        .file-info {{
            flex: 1;
            min-width: 0;
        }}
        .name {{
            display: block;
            font-size: 15px;
            font-weight: 500;
            color: #e0e0e0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .meta {{
            display: block;
            font-size: 12px;
            color: #666;
            margin-top: 2px;
        }}
        .download {{
            font-size: 20px;
            color: #667eea;
            flex-shrink: 0;
            margin-left: 8px;
        }}
        .empty {{
            text-align: center;
            padding: 60px 20px;
            color: #555;
            font-size: 15px;
        }}
        .count {{
            padding: 12px 20px;
            font-size: 12px;
            color: #555;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🗂️ Ernos Files</h1>
        <div class="subtitle">{len(files)} file{'s' if len(files) != 1 else ''} · {host}</div>
    </div>
    <div class="file-list">
        {file_rows}
    </div>
    <div class="count">Powered by Ernos · Files shared from your PC</div>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download a shared file."""
    # Sanitize — prevent path traversal
    safe_name = Path(filename).name
    file_path = SHARED_DIR / safe_name

    if not file_path.exists() or not file_path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type=media_type or "application/octet-stream",
    )


@router.get("/api/list")
async def api_list_files():
    """JSON API — list all shared files."""
    files = []
    if SHARED_DIR.exists():
        for f in sorted(SHARED_DIR.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "size_human": _human_size(stat.st_size),
                    "modified": stat.st_mtime,
                })
    return JSONResponse({"files": files, "count": len(files)})


def share_file(source_path: str, filename: Optional[str] = None) -> str:
    """
    Copy a file into the shared directory so it's downloadable.

    Args:
        source_path: Absolute path to the file to share.
        filename: Optional override for the filename.

    Returns:
        The download URL path.
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    dest_name = filename or src.name
    dest = SHARED_DIR / dest_name
    shutil.copy2(str(src), str(dest))

    logger.info(f"📤 Shared: {dest_name} ({_human_size(dest.stat().st_size)})")
    return f"/files/download/{dest_name}"
