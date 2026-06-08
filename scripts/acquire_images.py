#!/usr/bin/env python3
"""Acquire paper figures from arXiv HTML or PDF.

Two-source fallback pipeline:
  Source A: arXiv HTML  — scrape <figure> elements for image URLs and captions
  Source B: PDF extraction — pdfimages or PyMuPDF/fitz per-page screenshots

Usage:
    python3 acquire_images.py \\
        --arxiv-id 2605.24934 \\
        --output-dir /path/to/assets \\
        --method-name HumanEgo

Output (JSON to stdout):
    {
      "figures": [
        {"num": 1, "caption": "...", "ref_type": "url", "ref_value": "https://...", "source": "arxiv_html"}
      ],
      "summary": {"total": 10, "arxiv_html": 8, "pdf_extract": 2, "failed": 0}
    }
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# HTML scraping
# ---------------------------------------------------------------------------

def fetch_html(arxiv_id: str) -> Optional[str]:
    """Fetch the arXiv HTML page for a given arxiv_id. Returns raw HTML or None."""
    url = f"https://arxiv.org/html/{arxiv_id}"
    try:
        proc = subprocess.run(
            ["curl", "-sL", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:
        pass
    return None


def scrape_figures_from_html(html: str) -> list[dict]:
    """Extract figure numbers, captions, and image URLs from arXiv HTML.

    Returns list of {num, caption, url}.
    """
    figures = []

    # Split by <figure> blocks
    figure_blocks = re.split(r'<figure[^>]*>', html)
    for block in figure_blocks[1:]:  # skip content before first <figure>
        # Extract image URL
        img_match = re.search(r'<img[^>]*src="([^"]+)"', block)
        if not img_match:
            continue
        url = img_match.group(1)

        # Make relative URLs absolute
        if url.startswith("/"):
            url = f"https://arxiv.org{url}"
        elif not url.startswith("http"):
            # relative to HTML page
            arxiv_id = extract_arxiv_id_from_url(url) or ""
            base = f"https://arxiv.org/html/{arxiv_id}"
            url = f"{base}/{url}"

        # Skip non-figure images (icons, logos, etc.) — figure images are typically xN.png
        if not re.search(r'x\d+\.(png|jpg|jpeg|gif|webp|svg)', url):
            continue

        # Extract caption
        caption_match = re.search(
            r'<figcaption[^>]*>(.*?)</figcaption>', block, re.DOTALL
        )
        caption = ""
        if caption_match:
            caption = re.sub(r'<[^>]+>', ' ', caption_match.group(1)).strip()
            caption = re.sub(r'\s+', ' ', caption)

        # Extract figure number from caption tag
        num_match = re.search(r'<span[^>]*ltx_tag_figure[^>]*>([^<]+)</span>', block)
        num = None
        if num_match:
            try:
                num = int(num_match.group(1).strip())
            except ValueError:
                pass

        # Fallback: try to get number from image filename (x1.png → 1)
        if num is None:
            file_match = re.search(r'x(\d+)\.(png|jpg)', url)
            if file_match:
                num = int(file_match.group(1))

        figures.append({"num": num, "caption": caption, "url": url})

    # Sort by figure number, put None at end
    figures.sort(key=lambda f: (f["num"] is None, f["num"] or 0))
    return figures


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

def extract_arxiv_id_from_url(url: str) -> Optional[str]:
    """Extract arxiv_id (e.g. 2605.24934) from a URL."""
    m = re.search(r'(\d{4}\.\d{4,5})', url)
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


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def has_pdfimages() -> bool:
    """Check if pdfimages (poppler-utils) is available."""
    return subprocess.run(["which", "pdfimages"], capture_output=True).returncode == 0


def has_fitz() -> bool:
    """Check if PyMuPDF (fitz) is available."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def extract_images_with_pdfimages(pdf_path: str, output_dir: Path,
                                  prefix: str) -> list[Path]:
    """Extract images from PDF using pdfimages. Returns list of output file paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix_full = str(output_dir / prefix)
    try:
        subprocess.run(
            ["pdfimages", "-png", pdf_path, prefix_full],
            capture_output=True, timeout=60,
        )
    except Exception:
        pass
    # Filter to images >10KB
    extracted = sorted(output_dir.glob(f"{prefix}-*.png"))
    return [f for f in extracted if f.stat().st_size > 10240]


def extract_images_with_fitz(pdf_path: str, output_dir: Path,
                              prefix: str) -> list[Path]:
    """Extract images from PDF using PyMuPDF (per-page screenshots for figure pages)."""
    try:
        import fitz
    except ImportError:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Try extracting embedded images first
            images = page.get_images(full=True)
            for img_idx, img in enumerate(images):
                xref = img[0]
                base = doc.extract_image(xref)
                if base["width"] < 200 or base["height"] < 200:
                    continue
                ext = base["ext"]
                if ext == "jpeg":
                    ext = "jpg"
                fname = f"{prefix}-{page_num+1:03d}-{img_idx}.{ext}"
                fpath = output_dir / fname
                fpath.write_bytes(base["image"])
                if fpath.stat().st_size > 10240:
                    saved.append(fpath)

            # If no embedded images found, render the whole page
            if not page.get_images(full=True):
                pix = page.get_pixmap(dpi=150)
                fname = f"{prefix}-{page_num+1:03d}.png"
                fpath = output_dir / fname
                pix.save(str(fpath))
                if fpath.stat().st_size > 10240:
                    saved.append(fpath)

        doc.close()
    except Exception:
        pass
    return saved


def download_pdf(arxiv_id: str) -> Optional[str]:
    """Download arXiv PDF to a temp file. Returns path or None."""
    pdf_path = f"/tmp/arxiv_{arxiv_id}.pdf"
    if os.path.exists(pdf_path):
        return pdf_path
    try:
        subprocess.run(
            ["curl", "-sL", "--max-time", "60",
             "-o", pdf_path,
             f"https://arxiv.org/pdf/{arxiv_id}.pdf"],
            capture_output=True, timeout=65,
        )
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1024:
            return pdf_path
    except Exception:
        pass
    return None


def extract_figures_from_pdf(arxiv_id: str, output_dir: Path,
                              method_name: str,
                              needed_count: int = 10) -> list[dict]:
    """Extract figures from arXiv PDF. Returns list of {num, caption, ref_type, ref_value, source}."""
    pdf_path = download_pdf(arxiv_id)
    if not pdf_path:
        return []

    prefix = f"{method_name}_pdf_fig"
    image_files = []

    if has_pdfimages():
        image_files = extract_images_with_pdfimages(pdf_path, output_dir, prefix)

    if not image_files and has_fitz():
        image_files = extract_images_with_fitz(pdf_path, output_dir, prefix)

    # Sort by file size (larger images are more likely to be figures)
    image_files.sort(key=lambda f: f.stat().st_size, reverse=True)
    image_files = image_files[:needed_count]

    figures = []
    for i, fpath in enumerate(image_files):
        relative = f"{fpath.parent.name}/{fpath.name}"
        figures.append({
            "num": i + 1,
            "caption": "",
            "ref_type": "local",
            "ref_value": f"![[{fpath.name}]]",
            "source": "pdf_extract",
        })

    return figures


# ---------------------------------------------------------------------------
# Magic byte validation
# ---------------------------------------------------------------------------

def is_valid_image(path: Path) -> bool:
    """Check magic bytes to verify a file is a real image."""
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


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def acquire_images(arxiv_id: str, output_dir: Path, method_name: str = "paper",
                   max_figures: int = 10) -> dict:
    """Run the full image acquisition pipeline.

    Returns dict with 'figures' list and 'summary' dict.
    """
    figures: list[dict] = []
    stats = {"arxiv_html": 0, "pdf_extract": 0, "failed": 0}

    # --- Source A: arXiv HTML ---
    html = fetch_html(arxiv_id)
    if html:
        scraped = scrape_figures_from_html(html)
        for f in scraped[:max_figures]:
            url = dedup_url(f["url"])
            figures.append({
                "num": f["num"],
                "caption": f["caption"],
                "ref_type": "url",
                "ref_value": url,
                "source": "arxiv_html",
            })
        stats["arxiv_html"] = min(len(scraped), max_figures)

    # --- Source B: PDF extraction (for missing figures) ---
    missing = max_figures - len(figures)
    if missing > 0:
        pdf_figures = extract_figures_from_pdf(
            arxiv_id, output_dir, method_name, needed_count=missing
        )
        # Re-number PDF figures continuing from last HTML figure
        base = len(figures)
        for i, f in enumerate(pdf_figures):
            f["num"] = base + i + 1
            figures.append(f)
        stats["pdf_extract"] = len(pdf_figures)

    # --- Post-processing ---
    # Fill in missing numbers
    for i, f in enumerate(figures):
        if f["num"] is None:
            f["num"] = i + 1

    # Format ref_value for url type; strip arXiv HTML's built-in "Fig. X:" prefix
    for f in figures:
        if f["ref_type"] == "url":
            num = f["num"]
            caption_text = f["caption"] or f"Figure {num}"
            caption_text = re.sub(r'^Fig\.\s*\d+[.:]\s*', '', caption_text).strip()
            f["ref_value"] = f"![Figure {num}: {caption_text}]({f['ref_value']})"

    stats["total"] = len(figures)
    stats["failed"] = max_figures - len(figures)

    return {"figures": figures, "summary": stats}


def main():
    parser = argparse.ArgumentParser(
        description="Acquire paper figures from arXiv HTML or PDF"
    )
    parser.add_argument("--arxiv-id", required=True, help="arXiv ID, e.g. 2605.24934")
    parser.add_argument("--output-dir", required=True, help="Output directory for local images")
    parser.add_argument("--method-name", default="paper", help="Method name for file naming")
    parser.add_argument("--max-figures", type=int, default=10, help="Maximum figures to extract")
    parser.add_argument("--json-only", action="store_true", help="Output only JSON (no status messages)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()

    if not args.json_only:
        print(f"Acquiring figures for arXiv:{args.arxiv_id} → {output_dir}",
              file=sys.stderr)

    result = acquire_images(
        arxiv_id=args.arxiv_id,
        output_dir=output_dir,
        method_name=args.method_name,
        max_figures=args.max_figures,
    )

    if not args.json_only:
        s = result["summary"]
        print(f"Done: {s['total']} figures "
              f"({s['arxiv_html']} HTML, {s['pdf_extract']} PDF, {s['failed']} failed)",
              file=sys.stderr)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
