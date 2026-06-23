#!/usr/bin/env python3
"""Shared helpers for the paper-assistant lib/scripts.

Pure, dependency-free utilities consolidated here to avoid duplication across
discover.py, images.py, and scripts/download_note_images.py.

Standalone scripts import these with a path bootstrap, e.g.:

    import sys
    from pathlib import Path
    _LIB = Path(__file__).resolve().parent          # for files in lib/
    # _LIB = Path(__file__).resolve().parent.parent / "lib"   # for files in scripts/
    if str(_LIB) not in sys.path:
        sys.path.insert(0, str(_LIB))
    from common import extract_arxiv_id, is_valid_image, dedup_url
"""

import re
import sys
import tempfile
from pathlib import Path
from typing import Optional


def force_utf8_stdout() -> None:
    """Force stdout/stderr to UTF-8 so JSON with non-ASCII (ensure_ascii=False)
    prints reliably on locale-bound consoles (e.g. GBK on Chinese Windows).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def tmp_path(filename: str) -> Path:
    """Return a platform-appropriate temp file path (Windows: %TEMP%, else /tmp).

    Single source of truth for the temp dir so cached downloads (e.g. an
    arXiv PDF) are found by every script that looks for them.
    """
    return Path(tempfile.gettempdir()) / filename


def extract_arxiv_id(text: str) -> Optional[str]:
    """Extract an arXiv ID (e.g. 2605.24934) from a URL or text. None if absent."""
    m = re.search(r'(\d{4}\.\d{4,5})', text)
    return m.group(1) if m else None


def dedup_url(url: str) -> str:
    """Remove duplicated arxiv_id path segments from a URL.

    Example: .../2603.05312v1/2603.05312v1/x1.png → .../2603.05312v1/x1.png
    """
    m = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', url)
    if not m:
        return url
    segment = m.group(1)
    pattern = f"/{re.escape(segment)}/{re.escape(segment)}/"
    if re.search(pattern, url):
        url = url.replace(f"/{segment}/{segment}/", f"/{segment}/", 1)
    return url


def is_valid_image(path: Path) -> bool:
    """Verify a file is a real image by inspecting magic bytes, not just size."""
    path = Path(path)
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        header = path.read_bytes()[:16]
        if header[:4] == b"\x89PNG":
            return True       # PNG
        if header[:3] == b"\xff\xd8\xff":
            return True       # JPEG
        if header[:3] == b"GIF":
            return True       # GIF
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return True       # WebP
        return False
    except Exception:
        return False
