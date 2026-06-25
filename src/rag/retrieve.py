"""RAG retrieval - pull the top-K most relevant reviews from Chroma for a query.

Uses similarity search + MMR (Maximal Marginal Relevance) re-ranking so we
don't feed the LLM 15 near-duplicate reviews. MMR balances similarity to the
query against diversity within the result set.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from src.config import RAG_RETRIEVE_K, RAG_TOP_K
from src.pipeline.embed import embed_texts, get_collection

log = logging.getLogger(__name__)


@dataclass
class RetrievedReview:
    id: str
    text: str
    score: float                       # cosine similarity to the query
    metadata: dict


def _mmr(
    query_vec: np.ndarray,
    doc_vecs: np.ndarray,
    doc_meta: list[dict],
    *,
    top_k: int,
    lambda_param: float = 0.7,
) -> list[int]:
    """Greedy MMR. Returns selected indices into doc_vecs / doc_meta."""
    selected: list[int] = []
    candidates = list(range(len(doc_vecs)))
    if not candidates:
        return selected

    sim_to_q = doc_vecs @ query_vec                                 # cosine (normalized)

    while candidates and len(selected) < top_k:
        if not selected:
            best = max(candidates, key=lambda i: sim_to_q[i])
            selected.append(best)
            candidates.remove(best)
            continue

        selected_vecs = doc_vecs[selected]
        # similarity to most-similar already-selected
        sim_to_selected = (doc_vecs[candidates] @ selected_vecs.T).max(axis=1)
        scores = lambda_param * sim_to_q[candidates] - (1 - lambda_param) * sim_to_selected
        best_local = int(np.argmax(scores))
        best = candidates[best_local]
        selected.append(best)
        candidates.remove(best)

    return selected


def retrieve(
    query: str,
    *,
    k_initial: int | None = None,
    k_final: int | None = None,
    filter_canonical: str | None = None,
) -> list[RetrievedReview]:
    """Retrieve top-K reviews for a query.

    Args:
        query: question text
        k_initial: how many to fetch from Chroma before MMR (default RAG_RETRIEVE_K)
        k_final:   how many to keep after MMR (default RAG_TOP_K)
        filter_canonical: if set, only consider reviews tagged with this canonical id
    """
    k_initial = k_initial or RAG_RETRIEVE_K
    k_final = k_final or RAG_TOP_K

    coll = get_collection()
    n_total = coll.count()
    if n_total == 0:
        return []

    # Chroma metadata filter for canonical tag is a CSV string match; we filter post-hoc
    # for flexibility. Pull a slightly larger initial pool when filtering.
    pull = min(k_initial * 3 if filter_canonical else k_initial, n_total)

    query_vec = np.array(embed_texts([query])[0])
    results = coll.query(
        query_embeddings=[query_vec.tolist()],
        n_results=pull,
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    embs = np.array(results["embeddings"][0])
    # Chroma "distances" with cosine space are 1 - cosine_similarity; convert back
    sims = [1.0 - d for d in results["distances"][0]]

    # Post-filter by canonical tag if requested
    if filter_canonical:
        keep = [
            i for i, m in enumerate(metas)
            if filter_canonical in (m.get("canonical_tags") or "").split(",")
        ]
        if not keep:                                               # fall back to no filter
            keep = list(range(len(ids)))
        ids = [ids[i] for i in keep]
        docs = [docs[i] for i in keep]
        metas = [metas[i] for i in keep]
        embs = embs[keep] if len(keep) else embs
        sims = [sims[i] for i in keep]

    if len(ids) == 0:
        return []

    # MMR re-rank
    selected = _mmr(query_vec, embs, metas, top_k=min(k_final, len(ids)))

    out: list[RetrievedReview] = []
    for i in selected:
        out.append(
            RetrievedReview(
                id=ids[i],
                text=docs[i],
                score=float(sims[i]),
                metadata=metas[i] or {},
            )
        )
    return out
