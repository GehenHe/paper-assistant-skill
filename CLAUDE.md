# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Claude Code skill for interactive academic paper reading. Three-phase workflow: initial reading → multi-turn Q&A → merge insights back into structured Obsidian notes.

## Architecture: four-layer modular design

```
SKILL.md          ← Orchestration (WHAT + WHEN). Keep lean — reference other files, don't inline detail.
references/*.md   ← Detailed guides (HOW). Loaded on demand at specific phases.
assets/*.md       ← Templates for generated output (paper notes, concept notes).
lib/*.py          ← Automation (discovery, extraction, images). Callable from SKILL.md commands.
scripts/*.py      ← Post-processing tools (image reachability check).
```

**Core principle**: when adding detail to SKILL.md, ask "does this belong in a reference file instead?" SKILL.md is the conductor, not the orchestra.

## Key design decisions

- **Direction vs Concept**: Directions are user-defined research interests (directory-based, chosen at save time). Concepts are auto-extracted technical terms (flat `_概念/` directory, `[[wikilinks]]`). Never mix the two.
- **Note naming**: `{来源}{年份}-{方法名}.md` (e.g., `arxiv2026-HumanEgo.md`). Source + year concatenated, no separators.
- **Save path**: `{NOTES_PATH}/{方向}/{来源}{年份}-{方法名}.md`. Direction is chosen by user in Phase 1.4 from existing directories or by creating a new one.
- **Concept notes**: Flat under `_概念/` (no subdirectories). Each has `## 被引用` section with backlinks to papers. Template: `assets/concept-note-template.md`.
- **Image pipeline**: Two scripts — `lib/images.py` (acquisition, pre-note) and `scripts/download_note_images.py` (reachability check, post-note). Both support arXiv HTML and local PDF paths.
- **Paper discovery** (`lib/discover.py`): Multi-source fallback — arXiv → HuggingFace direct URL for known orgs → manual search. Non-arXiv papers (DeepSeek, OpenAI tech reports) are handled via `hf_pdf` source type.
- **Long paper extraction** (`lib/extract.py`): >30 pages triggers ToC-first strategy — Introduction (full) → Method (first paragraphs) → Main Results → Conclusion. Appendix skipped by default.
- **Phase 2 Q&A strategies**: 8 question types with tailored response strategies in `references/discussion-guide.md`. Concept questions get the deepest treatment (definition → position in paper → mechanism → design rationale → relationship to other concepts).
- **Bidirectional links**: Papers → concepts via `[[wikilinks]]`, concepts → papers via `## 被引用` section. Both sides maintained in Phase 3.3.

## Vault conventions

Obsidian vault path is configured in `../_shared/user-config.json` (shared across skills). If missing, ask user in Step 0. Default subdirectories: `论文笔记` for notes, `_概念` for concepts.

## When editing

- SKILL.md changes should be phase-level orchestration, not implementation detail
- New templates go in `assets/`, new guides in `references/`
- Python changes in `lib/` should remain CLI-callable with JSON output for Claude to parse
- Test image scripts with `--json-only` flag for clean output
- Do not commit `__pycache__/` or `*.swp` (in `.gitignore`)
