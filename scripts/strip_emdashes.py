"""One-off cleanup: replace em-dashes and en-dashes with ASCII hyphens.

Rationale: em-dashes (U+2014) and en-dashes (U+2013) are a common tell that
text was auto-generated. We prefer ASCII hyphens, commas, or restructured
sentences. This script does the simple, reliable transform; manual polish
can follow if needed.

Skips:
- node_modules, .venv, .git
- data/ jsonl files (those contain real scraped user reviews; leave alone)
- binary files (anything that doesn't decode as utf-8)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOTS = [
    Path(r"C:\Users\tiwari.mahima\Mayank\01-ai-review-engine"),
    Path(r"C:\Users\tiwari.mahima\Mayank\02-mvp"),
    Path(r"C:\Users\tiwari.mahima\Mayank\03-research-and-deck"),
    Path(r"C:\Users\tiwari.mahima\Mayank\masterArchitecture.md"),
    Path(r"C:\Users\tiwari.mahima\Mayank\masterProblemStatement.md"),
]

# File extensions we will rewrite.
INCLUDE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".html",
                    ".yml", ".yaml", ".toml", ".json", ".css", ".txt"}

# Skip these directories entirely.
SKIP_DIRS = {"node_modules", ".venv", "venv", ".git",
             "chroma_db", "__pycache__", "dist", "build", ".pytest_cache"}

# Within data/, only touch a small allowlist so we never edit scraped user
# content. metadata.json and canonical_answers.json are also LLM/derived but
# we leave them alone to preserve evidence integrity.
SKIP_PATH_SUBSTRS = ["/data/raw/", "/data/seed/", "/data/processed/",
                     "/data/insights/", "/data/chroma_db/"]

REPLACEMENTS = [
    (" - ", " - "),
    (" - ", " - "),
    ("-",   "-"),
    ("-",   "-"),
]


def should_skip(p: Path) -> bool:
    parts = {x.lower() for x in p.parts}
    if parts & SKIP_DIRS:
        return True
    posix = p.as_posix()
    if any(s in posix for s in SKIP_PATH_SUBSTRS):
        return True
    return p.suffix.lower() not in INCLUDE_SUFFIXES


def iter_files() -> list[Path]:
    out: list[Path] = []
    for root in ROOTS:
        if root.is_file():
            out.append(root)
            continue
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and not should_skip(p):
                out.append(p)
    return out


def transform(text: str) -> tuple[str, int]:
    n = 0
    for a, b in REPLACEMENTS:
        n += text.count(a)
        text = text.replace(a, b)
    return text, n


def main(write: bool) -> int:
    total_files = 0
    total_repls = 0
    for p in iter_files():
        try:
            original = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new, n = transform(original)
        if n > 0:
            total_files += 1
            total_repls += n
            mark = "WRITE" if write else "DRYRUN"
            print(f"{mark} {n:>4}  {p}")
            if write:
                p.write_text(new, encoding="utf-8")
    print(f"\n{'wrote' if write else 'would write'} {total_repls} replacements across {total_files} files.")
    return 0


if __name__ == "__main__":
    do_write = "--write" in sys.argv
    sys.exit(main(write=do_write))
