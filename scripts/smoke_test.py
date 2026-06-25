"""Smoke test — verifies the stack is configured correctly end-to-end.

Run after pasting GROQ_API_KEY into .env:
    python scripts/smoke_test.py

Checks:
  1. .env has GROQ_API_KEY
  2. Groq SDK can complete a tiny chat
  3. sentence-transformers model loads + embeds
  4. ChromaDB creates a collection and round-trips a doc
  5. Scope wrapper handles in-scope + out-of-scope queries
  6. (Optional) seed reviews load + normalize cleanly
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make `src` importable when running as `python scripts/smoke_test.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import GROQ_API_KEY, SEED_PATH


def passed(msg: str) -> None:
    print(f"  ✓ {msg}")


def failed(msg: str) -> None:
    print(f"  ✗ {msg}")


def section(title: str) -> None:
    print(f"\n[{title}]")


def main() -> int:
    fails = 0

    section("1. Environment")
    if not GROQ_API_KEY:
        failed("GROQ_API_KEY missing. Paste it into .env (copy from .env.example).")
        return 1
    passed(f"GROQ_API_KEY found (length={len(GROQ_API_KEY)})")

    section("2. Groq SDK")
    try:
        from src.pipeline.groq_client import fast_client
        out = fast_client().chat(
            system="You are a terse assistant.",
            user="Reply with the single word PONG.",
            max_tokens=8,
            temperature=0,
        )
        if "PONG" in out.upper():
            passed(f"Groq chat works (got: {out.strip()!r})")
        else:
            failed(f"Groq replied unexpectedly: {out!r}")
            fails += 1
    except Exception as exc:                                       # noqa: BLE001
        failed(f"Groq call failed: {exc}")
        fails += 1

    section("3. Local embeddings")
    try:
        from src.pipeline.embed import embed_texts
        vecs = embed_texts(["spotify discover weekly is stale", "i love jazz"])
        if vecs and len(vecs) == 2 and len(vecs[0]) == 384:
            passed(f"Embeddings OK (2 vectors, dim={len(vecs[0])})")
        else:
            failed(f"Unexpected embed shape: {len(vecs)} vectors")
            fails += 1
    except Exception as exc:                                       # noqa: BLE001
        failed(f"Embedding failed: {exc}")
        fails += 1

    section("4. ChromaDB round-trip")
    try:
        from src.pipeline.embed import get_collection
        coll = get_collection()
        before = coll.count()
        coll.upsert(
            ids=["__smoke__"],
            documents=["smoke test doc"],
            embeddings=embed_texts(["smoke test doc"]),
            metadatas=[{"source": "smoke", "rating": -1, "date": "", "url": "",
                        "canonical_tags": "", "features": "", "author": ""}],
        )
        after = coll.count()
        coll.delete(ids=["__smoke__"])
        passed(f"Chroma round-trip OK (count {before} -> {after} -> {coll.count()})")
    except Exception as exc:                                       # noqa: BLE001
        failed(f"Chroma round-trip failed: {exc}")
        fails += 1

    section("5. Scope wrapper")
    try:
        from src.rag.scope import evaluate_scope
        in_q = "why can't I find new music on spotify?"
        out_q = "what's the weather like in mumbai?"
        v_in = evaluate_scope(in_q)
        v_out = evaluate_scope(out_q)
        if v_in.in_scope and not v_out.in_scope:
            passed(
                f"In-scope detected ({v_in.max_similarity:.2f}, path={v_in.confidence}) | "
                f"Out-of-scope detected ({v_out.max_similarity:.2f}, path={v_out.confidence})"
            )
        else:
            failed(
                f"Scope routing wrong: in_q.in_scope={v_in.in_scope}, "
                f"out_q.in_scope={v_out.in_scope}"
            )
            fails += 1
    except Exception as exc:                                       # noqa: BLE001
        failed(f"Scope wrapper failed: {exc}")
        fails += 1

    section("6. Seed reviews")
    try:
        if not SEED_PATH.exists():
            failed(f"Seed file missing: {SEED_PATH}")
            fails += 1
        else:
            with SEED_PATH.open(encoding="utf-8") as f:
                seeds = [json.loads(line) for line in f if line.strip()]
            passed(f"Seed reviews loadable: {len(seeds)} records")
    except Exception as exc:                                       # noqa: BLE001
        failed(f"Seed load failed: {exc}")
        fails += 1

    print()
    if fails == 0:
        print("All checks passed. You are ready to run: python -m src.pipeline.refresh --seed-only")
        return 0
    print(f"{fails} check(s) failed. See messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
