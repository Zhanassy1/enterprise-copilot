"""
Vector / keyword retrieval uses SQLAlchemy ``text()`` with bound parameters only
(``:workspace_id``, ``:qtext``, ``:candidate_k``, ``:qvec``). No user-controlled
fragments are interpolated into SQL strings.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.debug_log import debug_log
from app.services.nlp import (
    boilerplate_penalty,
    expand_query,
    is_penalty_intent,
    is_price_intent,
    keyword_overlap,
)


def _dense_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    candidate_k: int,
) -> list[dict]:
    sql = text(
        """
        SELECT
          d.id AS document_id,
          d.filename AS source_filename,
          c.id AS chunk_id,
          c.chunk_index AS chunk_index,
          c.page_number AS page_number,
          c.paragraph_index AS paragraph_index,
          c.text AS text,
          (1 - (c.embedding_vector <=> (:qvec)::vector(384))) AS dense_score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE
          d.workspace_id = :workspace_id
          AND d.deleted_at IS NULL
          AND d.status = 'ready'
          AND c.embedding_vector IS NOT NULL
        ORDER BY dense_score DESC, c.chunk_index ASC
        LIMIT :candidate_k
        """
    )
    rows = db.execute(
        sql,
        {
            "workspace_id": str(workspace_id),
            "candidate_k": int(candidate_k),
            "qvec": "[" + ",".join(f"{float(x):.8f}" for x in query_embedding) + "]",
        },
    ).mappings()
    return [dict(r) for r in rows]


def _keyword_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_text: str,
    candidate_k: int,
) -> list[dict]:
    sql = text(
        """
        SELECT
          d.id AS document_id,
          d.filename AS source_filename,
          c.id AS chunk_id,
          c.chunk_index AS chunk_index,
          c.page_number AS page_number,
          c.paragraph_index AS paragraph_index,
          c.text AS text,
          (
            0.65 * LEAST(COALESCE(ts_rank_cd(to_tsvector('russian', c.text), websearch_to_tsquery('russian', :qtext)), 0.0), 1.0)
            + 0.30 * LEAST(COALESCE(ts_rank_cd(to_tsvector('simple', c.text), websearch_to_tsquery('simple', :qtext)), 0.0), 1.0)
            + 0.05 * CASE WHEN c.text ILIKE ('%' || :qtext || '%') THEN 1.0 ELSE 0.0 END
          ) AS keyword_score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.workspace_id = :workspace_id AND d.deleted_at IS NULL AND d.status = 'ready'
        ORDER BY keyword_score DESC, c.chunk_index ASC
        LIMIT :candidate_k
        """
    )
    rows = db.execute(
        sql,
        {
            "workspace_id": str(workspace_id),
            "candidate_k": int(candidate_k),
            "qtext": query_text,
        },
    ).mappings()
    return [dict(r) for r in rows]


def _rrf_fuse(
    dense: list[dict],
    keyword: list[dict],
    *,
    rrf_k: int,
    dense_weight: float,
    keyword_weight: float,
) -> list[dict]:
    fused: dict[str, dict] = {}
    dense_ranks: dict[str, int] = {}
    keyword_ranks: dict[str, int] = {}

    for i, row in enumerate(dense, start=1):
        dense_ranks[str(row["chunk_id"])] = i
    for i, row in enumerate(keyword, start=1):
        keyword_ranks[str(row["chunk_id"])] = i

    for row in dense:
        key = str(row["chunk_id"])
        fused[key] = {
            "document_id": row["document_id"],
            "source_filename": row.get("source_filename"),
            "chunk_id": row["chunk_id"],
            "chunk_index": row["chunk_index"],
            "page_number": row.get("page_number"),
            "paragraph_index": row.get("paragraph_index"),
            "text": row["text"],
            "dense_score": float(row.get("dense_score") or 0.0),
            "keyword_score": 0.0,
        }

    for row in keyword:
        key = str(row["chunk_id"])
        if key not in fused:
            fused[key] = {
                "document_id": row["document_id"],
                "source_filename": row.get("source_filename"),
                "chunk_id": row["chunk_id"],
                "chunk_index": row["chunk_index"],
                "page_number": row.get("page_number"),
                "paragraph_index": row.get("paragraph_index"),
                "text": row["text"],
                "dense_score": 0.0,
                "keyword_score": float(row.get("keyword_score") or 0.0),
            }
        else:
            fused[key]["keyword_score"] = float(row.get("keyword_score") or 0.0)

    for key, row in fused.items():
        score = 0.0
        if key in dense_ranks:
            score += float(dense_weight) / float(rrf_k + dense_ranks[key])
        if key in keyword_ranks:
            score += float(keyword_weight) / float(rrf_k + keyword_ranks[key])
        row["score"] = score

    return sorted(
        fused.values(),
        key=lambda r: (
            float(r.get("score") or 0.0),
            float(r.get("keyword_score") or 0.0),
            float(r.get("dense_score") or 0.0),
        ),
        reverse=True,
    )


def _apply_quality_heuristics(query_text: str, rows: list[dict]) -> list[dict]:
    price_intent = is_price_intent(query_text)
    penalty_intent = is_penalty_intent(query_text)
    tuned: list[dict] = []
    for row in rows:
        text_value = str(row.get("text") or "")
        low = text_value.lower()
        overlap = keyword_overlap(query_text, text_value)
        boiler = boilerplate_penalty(text_value)
        length_penalty = min(0.12, max(0.0, (len(text_value) - 1200) / 5000.0))

        bonus = 0.0
        hard_penalty = 0.0
        has_price_markers = any(m in low for m in ("цен", "стоим", "тенге", "kzt", "руб"))
        has_digits = any(ch.isdigit() for ch in text_value)
        has_penalty_markers = any(m in low for m in ("пен", "неусто", "штраф", "просроч"))
        if price_intent and has_price_markers:
            bonus += 0.10
        if price_intent and has_digits:
            bonus += 0.06
        if penalty_intent and has_penalty_markers:
            bonus += 0.12
        if price_intent and not (has_price_markers and has_digits):
            hard_penalty += 0.35
        if penalty_intent and not has_penalty_markers:
            hard_penalty += 0.35
        if overlap == 0.0:
            hard_penalty += 0.12

        intent_match = (price_intent and has_price_markers and has_digits) or (penalty_intent and has_penalty_markers)
        base = float(row.get("score") or 0.0)
        # Scale RRF base to compatible range with current quality thresholds.
        final_score = (base * 50.0) + 0.40 * overlap + bonus - boiler - length_penalty - hard_penalty
        row["score"] = final_score
        page_no = row.get("page_number")
        para_idx = row.get("paragraph_index")
        if page_no is not None:
            row["citation_anchor"] = f"page:{int(page_no)}:paragraph:{int(para_idx or 0)}"
        else:
            row["citation_anchor"] = f"paragraph:{int(para_idx or row.get('chunk_index') or 0)}"
        row["_base_score"] = base
        row["_overlap"] = overlap
        row["_boiler"] = boiler
        row["_length_penalty"] = length_penalty
        row["_hard_penalty"] = hard_penalty
        row["_intent_match"] = 1 if intent_match else 0
        tuned.append(row)

    tuned.sort(
        key=lambda r: (
            int(r.get("_intent_match") or 0),
            float(r.get("score") or 0.0),
            float(r.get("_overlap") or 0.0),
        ),
        reverse=True,
    )
    return tuned


def search_chunks_pgvector(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Requires pgvector + a `document_chunks.embedding_vector vector(<dim>)` column.
    Returns: [{document_id, chunk_id, chunk_index, text, score}]
    """
    expanded_query = expand_query(query_text)
    debug_log(
        hypothesisId="H_db",
        location="backend/app/services/vector_search.py:search",
        message="retrieval:execute",
        data={
            "top_k": int(top_k),
            "workspace_id": str(workspace_id),
            "qvec_type": type(query_embedding).__name__,
            "qvec_len": len(query_embedding),
            "qtext_len": len(query_text or ""),
            "qtext_expanded_len": len(expanded_query),
        },
    )
    try:
        candidate_k = max(int(top_k) * int(settings.retrieval_candidate_multiplier), int(settings.retrieval_candidate_floor))
        dense = _dense_candidates(
            db,
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            candidate_k=candidate_k,
        )
        keyword = _keyword_candidates(
            db,
            workspace_id=workspace_id,
            query_text=expanded_query,
            candidate_k=candidate_k,
        )

        if settings.retrieval_hybrid_enabled:
            fused = _rrf_fuse(
                dense,
                keyword,
                rrf_k=int(settings.retrieval_rrf_k),
                dense_weight=float(settings.retrieval_rrf_weight_dense),
                keyword_weight=float(settings.retrieval_rrf_weight_keyword),
            )
        else:
            fused = []
            for row in dense:
                fused.append(
                    {
                        "document_id": row["document_id"],
                        "chunk_id": row["chunk_id"],
                        "chunk_index": row["chunk_index"],
                        "text": row["text"],
                        "dense_score": float(row.get("dense_score") or 0.0),
                        "keyword_score": 0.0,
                        "score": float(row.get("dense_score") or 0.0),
                    }
                )

        reranked = _apply_quality_heuristics(query_text, fused)
        penalty_intent = is_penalty_intent(query_text)
        price_intent = is_price_intent(query_text)

        if penalty_intent:
            intent_hits = [r for r in reranked if int(r.get("_intent_match") or 0) == 1]
            if intent_hits:
                reranked = intent_hits
        if price_intent:
            def _price_match(row: dict) -> bool:
                txt = str(row.get("text") or "").lower()
                return (any(m in txt for m in ("цен", "стоим", "тенге", "kzt", "руб")) and any(ch.isdigit() for ch in txt))

            price_hits = [r for r in reranked if _price_match(r)]
            if price_hits:
                reranked = price_hits
        # Keep only chunks with acceptable score to suppress weak/noisy matches.
        min_score = float(settings.retrieval_min_score)
        reranked = [r for r in reranked if float(r.get("score") or 0.0) >= min_score]

        # De-duplicate near-identical chunks so context is diverse and useful.
        deduped: list[dict] = []
        max_dup_overlap = float(settings.retrieval_max_near_duplicate_overlap)
        for row in reranked:
            row_text = str(row.get("text") or "")
            is_duplicate = False
            for kept in deduped:
                kept_text = str(kept.get("text") or "")
                overlap = keyword_overlap(row_text, kept_text)
                if overlap >= max_dup_overlap:
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduped.append(row)
            if len(deduped) >= int(top_k):
                break
        out = deduped[: int(top_k)]

        debug_log(
            hypothesisId="H_rank",
            location="backend/app/services/vector_search.py:rank",
            message="retrieval:top_scores",
            data={
                "top3": [
                    {
                        "score": float(x.get("score") or 0.0),
                        "base_score": float(x.get("_base_score") or 0.0),
                        "overlap": float(x.get("_overlap") or 0.0),
                        "boiler": float(x.get("_boiler") or 0.0),
                        "length_penalty": float(x.get("_length_penalty") or 0.0),
                        "hard_penalty": float(x.get("_hard_penalty") or 0.0),
                        "intent_match": int(x.get("_intent_match") or 0),
                        "dense_score": float(x.get("dense_score") or 0.0),
                        "keyword_score": float(x.get("keyword_score") or 0.0),
                        "chunk_index": int(x.get("chunk_index") or 0),
                    }
                    for x in out[:3]
                ]
            },
        )
        for row in out:
            row.pop("_base_score", None)
            row.pop("_overlap", None)
            row.pop("_boiler", None)
            row.pop("_length_penalty", None)
            row.pop("_hard_penalty", None)
            row.pop("_intent_match", None)
        debug_log(
            hypothesisId="H_db",
            location="backend/app/services/vector_search.py:done",
            message="retrieval:ok",
            data={"hits": len(out)},
        )
        return out
    except Exception as e:
        debug_log(
            hypothesisId="H_db",
            location="backend/app/services/vector_search.py:error",
            message="retrieval:error",
            data={"type": type(e).__name__, "msg": str(e)},
        )
        raise

