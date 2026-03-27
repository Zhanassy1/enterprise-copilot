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


def search_chunks_pgvector(
    db: Session,
    *,
    owner_id: uuid.UUID,
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Requires pgvector + a `document_chunks.embedding_vector vector(<dim>)` column.
    Returns: [{document_id, chunk_id, chunk_index, text, score}]
    """
    expanded_query = expand_query(query_text)
    price_intent = is_price_intent(query_text)
    penalty_intent = is_penalty_intent(query_text)

    sql = text(
        """
        WITH ranked AS (
          SELECT
            d.id AS document_id,
            c.id AS chunk_id,
            c.chunk_index AS chunk_index,
            c.text AS text,
            (1 - (c.embedding_vector <=> (:qvec)::vector(384))) AS vector_score,
            ts_rank_cd(
              to_tsvector('russian', c.text),
              websearch_to_tsquery('russian', :qtext)
            ) AS lexical_score_ru,
            ts_rank_cd(
              to_tsvector('simple', c.text),
              websearch_to_tsquery('simple', :qtext)
            ) AS lexical_score_simple,
            CASE
              WHEN c.text ILIKE ('%' || :qtext || '%') THEN 1.0
              ELSE 0.0
            END AS phrase_bonus
          FROM document_chunks c
          JOIN documents d ON d.id = c.document_id
          WHERE d.owner_id = :owner_id
        )
        SELECT
          document_id,
          chunk_id,
          chunk_index,
          text,
          vector_score,
          lexical_score_ru,
          lexical_score_simple,
          phrase_bonus,
          (
            0.35 * COALESCE(vector_score, 0.0) +
            0.45 * LEAST(COALESCE(lexical_score_ru, 0.0), 1.0) +
            0.15 * LEAST(COALESCE(lexical_score_simple, 0.0), 1.0) +
            0.05 * COALESCE(phrase_bonus, 0.0)
          ) AS score
        FROM ranked
        ORDER BY score DESC, lexical_score_ru DESC, lexical_score_simple DESC, chunk_index ASC
        LIMIT :candidate_k
        """
    )

    debug_log(
        hypothesisId="H_db",
        location="backend/app/services/vector_search.py:44",
        message="pgvector:execute",
        data={
            "top_k": int(top_k),
            "owner_id": str(owner_id),
            "qvec_type": type(query_embedding).__name__,
            "qvec_len": len(query_embedding),
            "qtext_len": len(query_text or ""),
            "qtext_expanded_len": len(expanded_query),
        },
    )
    try:
        candidate_k = max(int(top_k) * 8, 40)
        rows = db.execute(
            sql,
            {
                "owner_id": str(owner_id),
                "candidate_k": candidate_k,
                "qtext": expanded_query,
                "qvec": "[" + ",".join(f"{float(x):.8f}" for x in query_embedding) + "]",
            },
        ).mappings()
        out = [dict(r) for r in rows]

        reranked: list[dict] = []
        for x in out:
            text_value = str(x.get("text") or "")
            base = float(x.get("score") or 0.0)
            overlap = keyword_overlap(query_text, text_value)
            boiler = boilerplate_penalty(text_value)
            length_penalty = min(0.12, max(0.0, (len(text_value) - 1200) / 5000.0))

            bonus = 0.0
            hard_penalty = 0.0
            low = text_value.lower()
            has_price_markers = any(m in low for m in ("цен", "стоим", "тенге", "kzt", "руб"))
            has_digits = any(ch.isdigit() for ch in text_value)
            has_penalty_markers = any(m in low for m in ("пен", "неусто", "штраф", "просроч"))
            if price_intent and any(m in low for m in ("цен", "стоим", "тенге", "kzt", "руб")):
                bonus += 0.10
            if price_intent and any(ch.isdigit() for ch in text_value):
                bonus += 0.06
            if penalty_intent and any(m in low for m in ("пен", "неусто", "штраф", "просроч")):
                bonus += 0.12
            if price_intent and not (has_price_markers and has_digits):
                hard_penalty += 0.35
            if penalty_intent and not has_penalty_markers:
                hard_penalty += 0.35
            if overlap == 0.0:
                hard_penalty += 0.12

            intent_match = (price_intent and has_price_markers and has_digits) or (penalty_intent and has_penalty_markers)
            final_score = base + 0.40 * overlap + bonus - boiler - length_penalty - hard_penalty
            x["score"] = final_score
            x["_base_score"] = base
            x["_overlap"] = overlap
            x["_boiler"] = boiler
            x["_length_penalty"] = length_penalty
            x["_hard_penalty"] = hard_penalty
            x["_intent_match"] = 1 if intent_match else 0
            reranked.append(x)

        reranked.sort(
            key=lambda r: (
                int(r.get("_intent_match") or 0),
                float(r.get("score") or 0.0),
                float(r.get("_overlap") or 0.0),
            ),
            reverse=True,
        )
        # Hard intent filter: if we found intent-matching chunks, drop non-matching noise.
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
            location="backend/app/services/vector_search.py:70",
            message="pgvector:top_scores",
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
                        "vector_score": float(x.get("vector_score") or 0.0),
                        "lexical_score_ru": float(x.get("lexical_score_ru") or 0.0),
                        "lexical_score_simple": float(x.get("lexical_score_simple") or 0.0),
                        "phrase_bonus": float(x.get("phrase_bonus") or 0.0),
                        "chunk_index": int(x.get("chunk_index") or 0),
                    }
                    for x in out[:3]
                ]
            },
        )
        for row in out:
            row.pop("vector_score", None)
            row.pop("lexical_score_ru", None)
            row.pop("lexical_score_simple", None)
            row.pop("phrase_bonus", None)
            row.pop("_base_score", None)
            row.pop("_overlap", None)
            row.pop("_boiler", None)
            row.pop("_length_penalty", None)
            row.pop("_hard_penalty", None)
            row.pop("_intent_match", None)
        debug_log(
            hypothesisId="H_db",
            location="backend/app/services/vector_search.py:56",
            message="pgvector:ok",
            data={"hits": len(out)},
        )
        return out
    except Exception as e:
        debug_log(
            hypothesisId="H_db",
            location="backend/app/services/vector_search.py:66",
            message="pgvector:error",
            data={"type": type(e).__name__, "msg": str(e)},
        )
        raise

