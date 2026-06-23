#!/usr/bin/env python3
"""Paper discovery: locate and download papers from multiple sources.

Input types:
  - arXiv link (abs/pdf/html)
  - Paper title
  - Local PDF path
  - DOI link
  - Direct PDF URL (HuggingFace, GitHub, project page)

Output (JSON to stdout):
  {"source_type": "arxiv_html", "arxiv_id": "2605.24934",
   "pdf_path": null, "html_url": "https://arxiv.org/html/2605.24934",
   "metadata": {"title": "...", "authors": [...], "year": 2026}}

Usage:
    python3 lib/discover.py "Attention Is All You Need"
    python3 lib/discover.py "https://arxiv.org/abs/2605.24934"
    python3 lib/discover.py /path/to/paper.pdf
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

_LIB = Path(__file__).resolve().parent
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from common import extract_arxiv_id, force_utf8_stdout, tmp_path  # noqa: E402


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

CURL_TIMEOUT = 30
PDF_MIN_SIZE = 1024  # 1KB minimum for valid PDF


def _tmp(filename: str) -> str:
    """Return a platform-appropriate temp file path as a string."""
    return str(tmp_path(filename))


def is_arxiv_url(text: str) -> bool:
    return 'arxiv.org' in text


def is_doi(text: str) -> bool:
    return 'doi.org' in text or text.startswith('10.')


def is_local_pdf(text: str) -> bool:
    return text.endswith('.pdf') and os.path.exists(text)


def is_direct_pdf_url(text: str) -> bool:
    return (text.endswith('.pdf') and text.startswith('http') and
            not is_arxiv_url(text))


def curl_fetch(url: str, timeout: int = CURL_TIMEOUT) -> Optional[str]:
    """Fetch URL content via curl. Returns text or None on failure."""
    try:
        proc = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), url],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout + 5,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:
        pass
    return None


def curl_download(url: str, dest: str, timeout: int = 60) -> bool:
    """Download a file via curl. Returns True on success."""
    try:
        subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-o", dest, url],
            capture_output=True, timeout=timeout + 5,
        )
        return os.path.exists(dest) and os.path.getsize(dest) > PDF_MIN_SIZE
    except Exception:
        return False


def extract_authors_from_arxiv_html(html: str) -> list[str]:
    """Try to parse author names from arXiv HTML."""
    authors = []
    # Look for author spans
    for m in re.finditer(r'<span[^>]*class="ltx_personname"[^>]*>(.*?)</span>',
                         html, re.DOTALL):
        name = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
        name = re.sub(r'\s+', ' ', name)
        if name:
            authors.append(name)
    if authors:
        return authors
    # Fallback: meta tags
    for m in re.finditer(
        r'<meta[^>]*name="citation_author"[^>]*content="([^"]+)"', html
    ):
        authors.append(m.group(1))
    return authors


# ---------------------------------------------------------------------------
# Source handlers
# ---------------------------------------------------------------------------

def handle_arxiv(arxiv_id: str) -> dict:
    """Handle arXiv paper: try HTML first, fallback to PDF download."""
    result = {
        "source_type": "arxiv_pdf",
        "arxiv_id": arxiv_id,
        "pdf_path": None,
        "html_url": None,
        "metadata": {"title": "", "authors": [], "year": None},
        "error": None,
    }

    # Try arXiv HTML
    html_url = f"https://arxiv.org/html/{arxiv_id}"
    html_content = curl_fetch(html_url)
    if html_content and '<article' in html_content:
        result["source_type"] = "arxiv_html"
        result["html_url"] = html_url
        # Try to get title
        title_m = re.search(r'<h1[^>]*class="ltx_title[^"]*"[^>]*>(.*?)</h1>',
                            html_content, re.DOTALL)
        if title_m:
            title = re.sub(r'<[^>]+>', ' ', title_m.group(1)).strip()
            title = re.sub(r'\s+', ' ', title)
            result["metadata"]["title"] = title
        result["metadata"]["authors"] = extract_authors_from_arxiv_html(
            html_content
        )
        return result

    # Fallback: download PDF
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    pdf_path = _tmp(f"arxiv_{arxiv_id}.pdf")
    if curl_download(pdf_url, pdf_path):
        result["pdf_path"] = pdf_path
    else:
        result["error"] = "arXiv HTML unavailable and PDF download failed"

    # Try abstract page for metadata
    abs_html = curl_fetch(f"https://arxiv.org/abs/{arxiv_id}")
    if abs_html:
        title_m = re.search(
            r'<meta[^>]*name="citation_title"[^>]*content="([^"]+)"', abs_html
        )
        if title_m:
            result["metadata"]["title"] = title_m.group(1)
        author_ms = re.findall(
            r'<meta[^>]*name="citation_author"[^>]*content="([^"]+)"', abs_html
        )
        result["metadata"]["authors"] = author_ms
        date_m = re.search(
            r'<meta[^>]*name="citation_date"[^>]*content="([^"]+)"', abs_html
        )
        if date_m:
            try:
                result["metadata"]["year"] = int(date_m.group(1)[:4])
            except (ValueError, IndexError):
                pass

    return result


def handle_title(title: str) -> dict:
    """Discover paper by title with multi-source fallback.

    Priority:
      1. Search arXiv (with title verification)
      2. Try direct HuggingFace URL for known orgs
      3. Return error for manual search fallback
    """
    result = {
        "source_type": "url_pdf",
        "arxiv_id": None,
        "pdf_path": None,
        "html_url": None,
        "metadata": {"title": title, "authors": [], "year": None},
        "error": None,
    }

    # Step 1: Search arXiv
    arxiv_result = curl_fetch(
        f"https://arxiv.org/search/?query={title.replace(' ', '+')}&searchtype=all"
    )
    if arxiv_result:
        # Find arXiv IDs AND check if any result title matches
        paper_entries = re.findall(
            r'<p class="list-title[^"]*">\s*(.*?)\s*</p>.*?arXiv:(\d{4}\.\d{4,5})',
            arxiv_result, re.DOTALL,
        )
        # Also try the simple ID extraction as fallback
        arxiv_ids = re.findall(r'arXiv:(\d{4}\.\d{4,5})', arxiv_result)
        # Prefer the first ID that has a matching title
        for entry_title, aid in paper_entries:
            entry_title_clean = re.sub(r'<[^>]+>', '', entry_title).strip().lower()
            if title.lower()[:30] in entry_title_clean or entry_title_clean in title.lower():
                arxiv_info = handle_arxiv(aid)
                arxiv_info["metadata"]["title"] = title
                return arxiv_info
        # No title match — fall back to first arXiv ID found (title or ID search)
        if arxiv_ids:
            arxiv_info = handle_arxiv(arxiv_ids[0])
            arxiv_info["metadata"]["title"] = title
            return arxiv_info

    # Step 2: Try HuggingFace direct URL construction
    # Extract potential org/model from title keywords
    hf_orgs = {
        "deepseek": "deepseek-ai",
        "llama": "meta-llama",
        "qwen": "Qwen",
        "gemini": "google",
        "claude": "anthropics",
        "gpt": "openai",
        "kimi": "moonshot-ai",
        "glm": "THUDM",
    }
    title_lower = title.lower()
    for keyword, org in hf_orgs.items():
        if keyword in title_lower:
            # Try common PDF paths on HuggingFace, derived from the title
            model_name = title.split(":")[0].strip().replace(" ", "-")
            hf_urls = [
                f"https://huggingface.co/{org}/{model_name}/resolve/main/paper.pdf",
                f"https://huggingface.co/{org}/{model_name}/resolve/main/report.pdf",
            ]
            for url in hf_urls:
                fname = re.sub(r'[^a-zA-Z0-9_.-]', '_', title)[:50]
                pdf_path = _tmp(f"{fname}.pdf")
                if curl_download(url, pdf_path, timeout=60):
                    result["pdf_path"] = pdf_path
                    result["source_type"] = "hf_pdf"
                    return result
            break  # Only try one org

    result["error"] = (
        "Paper not found on arXiv or HuggingFace. "
        "Use WebSearch to find the PDF URL, then re-run with the URL."
    )
    return result


def handle_local_pdf(path: str) -> dict:
    return {
        "source_type": "local_pdf",
        "arxiv_id": None,
        "pdf_path": os.path.abspath(path),
        "html_url": None,
        "metadata": {"title": "", "authors": [], "year": None},
        "error": None,
    }


def handle_doi(doi: str) -> dict:
    # Try to resolve DOI to arXiv
    resolved = curl_fetch(f"https://doi.org/{doi}")
    if resolved:
        arxiv_id = extract_arxiv_id(resolved)
        if arxiv_id:
            return handle_arxiv(arxiv_id)
    return {
        "source_type": "url_pdf",
        "arxiv_id": None,
        "pdf_path": None,
        "html_url": None,
        "metadata": {"title": "", "authors": [], "year": None},
        "error": "Could not resolve DOI to an accessible PDF",
    }


def handle_direct_pdf_url(url: str) -> dict:
    fname = re.search(r'([^/]+)\.pdf', url)
    local_name = fname.group(1) if fname else "paper"
    pdf_path = _tmp(f"{local_name}.pdf")
    ok = curl_download(url, pdf_path, timeout=120)
    source_type = "hf_pdf" if "huggingface" in url else "url_pdf"
    return {
        "source_type": source_type,
        "arxiv_id": None,
        "pdf_path": pdf_path if ok else None,
        "html_url": None,
        "metadata": {"title": "", "authors": [], "year": None},
        "error": None if ok else f"Failed to download PDF from {url}",
    }


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

def discover(user_input: str) -> dict:
    """Dispatch paper discovery based on input type."""
    user_input = user_input.strip()

    # arXiv URL
    if is_arxiv_url(user_input):
        arxiv_id = extract_arxiv_id(user_input)
        if arxiv_id:
            return handle_arxiv(arxiv_id)

    # DOI
    if is_doi(user_input):
        return handle_doi(user_input)

    # Local PDF
    if is_local_pdf(user_input):
        return handle_local_pdf(user_input)

    # Direct PDF URL
    if is_direct_pdf_url(user_input):
        return handle_direct_pdf_url(user_input)

    # Assume paper title
    return handle_title(user_input)


def main():
    force_utf8_stdout()
    parser = argparse.ArgumentParser(
        description="Discover and download academic papers from multiple sources"
    )
    parser.add_argument(
        "input", help="Paper title, arXiv link, DOI, local PDF path, or PDF URL"
    )
    args = parser.parse_args()

    result = discover(args.input)

    if result.get("error"):
        print(f"Warning: {result['error']}", file=sys.stderr)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
