#!/usr/bin/env python3
"""Paper content extraction with ToC-first strategy.

For long papers (>30 pages), first extracts the table of contents,
then selectively reads key sections. Short papers are fully extracted.

Usage:
    python3 lib/extract.py --pdf /tmp/paper.pdf
    python3 lib/extract.py --pdf /tmp/paper.pdf --long-paper
    python3 lib/extract.py --pdf /tmp/paper.pdf --sections "Introduction,Method,Conclusion"

Output (JSON to stdout):
  {"toc": [...], "sections": {...}, "figures": [...], "stats": {...}}
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


LONG_PAPER_THRESHOLD = 30  # pages
KEY_SECTIONS_LONG = [
    "introduction",
    "conclusion",
    "abstract",
]
METHOD_SECTIONS = [
    "architecture", "method", "approach", "model",
    "framework", "training", "pre-training", "post-training",
]


def _has_fitz() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def extract_text_pages(pdf_path: str) -> tuple[list[str], int]:
    """Extract text from each page of a PDF. Returns (pages_text, page_count)."""
    if not _has_fitz():
        # Fallback: try pdftotext
        import subprocess
        try:
            proc = subprocess.run(
                ["pdftotext", "-layout", pdf_path, "-"],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode == 0:
                # Can't split by page with pdftotext alone
                return [proc.stdout], 1
        except Exception:
            pass
        return [], 0

    import fitz
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text()
        pages.append(text)
    count = len(doc)
    doc.close()
    return pages, count


def extract_toc(pages: list[str]) -> list[dict]:
    """Extract table of contents from first pages of a PDF.

    Handles common formats:
      "1  Introduction  4"
      "2.1  Designs Inherited from DeepSeek-V3  7"
      "1. Introduction ........ 5"
    """
    toc = []
    search_text = "\n".join(pages[:5])

    # Remove arXiv header noise
    search_text = re.sub(r'arXiv:\d{4}\.\d{4,5}v\d.*?\n', '', search_text)

    # Primary pattern: dotted section number, title text, terminal page number
    # Matches: "1  Introduction  4", "2.1  Method Details  15", "A.1  Appendix  55"
    primary = re.compile(
        r'^(\d+(?:\.\d+)*)\s{1,4}([A-Z].+?)\s{2,}(\d{1,4})\s*$',
        re.MULTILINE,
    )
    for m in primary.finditer(search_text):
        num_str = m.group(1)
        title = m.group(2).strip()
        page = int(m.group(3))
        # Filter out false positives: page numbers should be reasonable (1-999)
        if page > 500:
            continue
        # Filter out lines that are just reference numbers, not ToC entries
        if len(title) < 3:
            continue
        toc.append({"num": num_str, "title": title, "page": page})

    # Secondary pattern: "1. Title ........ 5" (dots between title and page)
    secondary = re.compile(
        r'^(\d+(?:\.\d+)*)\.?\s+(.+?)\s*\.{3,}\s*(\d{1,3})\s*$',
        re.MULTILINE,
    )
    for m in secondary.finditer(search_text):
        num_str = m.group(1)
        title = m.group(2).strip()
        page = int(m.group(3))
        if not any(t["num"] == num_str for t in toc):
            toc.append({"num": num_str, "title": title, "page": page})

    # Fallback: plain section headers in text (no page numbers)
    if not toc:
        fallback = re.compile(
            r'^(\d+(?:\.\d+)*)\.?\s+([A-Z][A-Za-z\s\-/]{3,80})$',
            re.MULTILINE,
        )
        for i, page_text in enumerate(pages[:10]):
            for m in fallback.finditer(page_text):
                num_str = m.group(1)
                title = m.group(2).strip()
                if not any(t["num"] == num_str for t in toc):
                    toc.append({"num": num_str, "title": title, "page": i + 1})

    # Sort: by top-level number, then subsection
    def sort_key(t):
        parts = t["num"].split(".")
        return tuple(int(p) for p in parts)
    toc.sort(key=sort_key)
    return toc


def _section_keywords(section_title: str) -> list[str]:
    """Map a section title to keyword types."""
    lower = section_title.lower()
    keywords = []
    if any(w in lower for w in ["intro", "background", "motivation"]):
        keywords.append("introduction")
    if any(w in lower for w in ["method", "approach", "architecture",
                                 "model", "framework", "manifold",
                                 "attention", "optimizer"]):
        keywords.append("method")
    if any(w in lower for w in ["experiment", "evaluation", "result",
                                 "benchmark", "pre-training",
                                 "post-training"]):
        keywords.append("experiments")
    if any(w in lower for w in ["conclus", "discussion", "future",
                                 "limitation"]):
        keywords.append("conclusion")
    if any(w in lower for w in ["relat", "prior"]):
        keywords.append("related_work")
    if any(w in lower for w in ["appendix", "supplement",
                                 "author list", "acknowledgment"]):
        keywords.append("appendix")
    if any(w in lower for w in ["infrastructure", "training framework",
                                 "inference framework"]):
        keywords.append("method")  # infra is part of method for our purposes
    return keywords


def extract_sections(pages: list[str], toc: list[dict],
                     long_paper: bool = False) -> dict[str, str]:
    """Extract key sections from the paper.

    For long papers: only extracts Introduction, Conclusion, and first
    paragraphs of each method section (not full method details).
    For short papers: extracts all sections.
    """
    result: dict[str, str] = {}
    total = len(pages)

    if long_paper and toc:
        # Determine page ranges for key sections from ToC
        intro_page = 1
        method_start = None
        experiment_start = None
        conclusion_start = None
        appendix_start = None

        for t in toc:
            kw = _section_keywords(t["title"])
            if "introduction" in kw and not intro_page:
                intro_page = t["page"]
            if "method" in kw and not method_start:
                method_start = t["page"]
            if "experiments" in kw and not experiment_start:
                experiment_start = t["page"]
            if "conclusion" in kw and not conclusion_start:
                conclusion_start = t["page"]
            if "appendix" in kw and not appendix_start:
                appendix_start = t["page"]

        # Introduction (first 3 pages or until method section)
        intro_end = min(
            method_start or total, experiment_start or total, 5
        )
        result["introduction"] = "\n".join(pages[:intro_end])

        # Method — first paragraphs of each method section
        if method_start and method_start <= total:
            method_pages = []
            for t in toc:
                kw = _section_keywords(t["title"])
                if "method" in kw and t["page"]:
                    p = t["page"] - 1  # 0-indexed
                    if p < total:
                        # Just the first page of each method subsection
                        method_pages.append(pages[p])
            if method_pages:
                result["method"] = "\n...\n".join(method_pages)

        # Experiments — main results
        if experiment_start and experiment_start <= total:
            exp_pages = pages[experiment_start - 1:min(
                conclusion_start or total, experiment_start + 5
            )]
            result["experiments"] = "\n".join(exp_pages)

        # Conclusion
        if conclusion_start and conclusion_start <= total:
            conc_end = appendix_start or total
            conc_pages = pages[conclusion_start - 1:conc_end]
            result["conclusion"] = "\n".join(conc_pages)

    else:
        # Short paper: full text
        result["full_text"] = "\n".join(pages)

    return result


def extract_figures_from_text(pages: list[str]) -> list[dict]:
    """Extract figure captions from text content."""
    figures = []
    for i, page_text in enumerate(pages):
        for m in re.finditer(
            r'(?:Figure|Fig\.?)\s+(\d+)[.:]\s*(.+?)(?=\n\n|\n(?:Figure|Fig)|$)',
            page_text, re.DOTALL | re.IGNORECASE,
        ):
            figures.append({
                "num": int(m.group(1)),
                "caption": m.group(2).strip().replace("\n", " "),
                "page": i + 1,
            })
    figures.sort(key=lambda f: f["num"])
    return figures


def extract(pdf_path: str, long_paper: bool = False) -> dict:
    """Main extraction pipeline."""
    pages, total = extract_text_pages(pdf_path)
    if not pages:
        return {"error": "Could not extract text from PDF", "toc": [],
                "sections": {}, "figures": [], "stats": {}}

    # Auto-detect long paper
    if not long_paper and total > LONG_PAPER_THRESHOLD:
        long_paper = True

    toc = extract_toc(pages)
    sections = extract_sections(pages, toc, long_paper=long_paper)
    figures = extract_figures_from_text(pages)

    full_text = "\n".join(pages)
    stats = {
        "total_pages": total,
        "total_chars": len(full_text),
        "long_paper": long_paper,
        "strategy": "toc_first" if long_paper else "full_extract",
    }

    return {
        "toc": toc,
        "sections": sections,
        "figures": figures,
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract paper content with ToC-first strategy"
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--long-paper", action="store_true",
                        help="Force long-paper extraction strategy")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.exists():
        print(json.dumps({"error": f"PDF not found: {pdf_path}"}))
        sys.exit(1)

    result = extract(str(pdf_path), long_paper=args.long_paper)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
