import re

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.core.debug_log import debug_log
from app.schemas.documents import SearchIn, SearchOut
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer,
    build_clarifying_question,
    build_next_step,
    decide_response_mode,
    is_penalty_intent,
    is_price_intent,
)
from app.services.vector_search import search_chunks_pgvector

router = APIRouter(prefix="/search", tags=["search"])


def _compact_hit_text(text: str, query: str, *, price_intent: bool) -> str:
    if not text:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return text[:800]

    q = (query or "").lower().strip()
    stems = {tok[:4] for tok in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", q) if len(tok) >= 3}
    penalty_intent = is_penalty_intent(query)
    price_markers = ("цена", "стоим", "тенге", "kzt", "руб", "usd")
    penalty_markers = ("пен", "неусто", "штраф", "просроч")

    def keep_line(line: str) -> bool:
        low = line.lower()
        if q and q in low:
            return True
        if stems and any(s in low for s in stems):
            return True
        if price_intent and any(m in low for m in price_markers):
            return True
        if penalty_intent and any(m in low for m in penalty_markers):
            return True
        if price_intent and any(ch.isdigit() for ch in line):
            return True
        return False

    matched = [ln for ln in lines if keep_line(ln)]
    if matched:
        return "\n".join(matched[:12])[:1200]
    return "\n".join(lines[:8])[:800]


@router.post("", response_model=SearchOut)
def search(payload: SearchIn, db: DbDep, user: CurrentUser) -> SearchOut:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Empty query")
    price_intent = is_price_intent(payload.query)
    penalty_intent = is_penalty_intent(payload.query)
    debug_log(
        hypothesisId="H_embed",
        location="backend/app/api/routers/search.py:17",
        message="search:start",
        data={
            "top_k": payload.top_k,
            "query_len": len(payload.query),
            "price_intent": price_intent,
            "penalty_intent": penalty_intent,
        },
    )
    try:
        qvec = embed_texts([payload.query])[0]
        debug_log(
            hypothesisId="H_embed",
            location="backend/app/api/routers/search.py:26",
            message="search:embedded",
            data={"qvec_len": len(qvec), "qvec_head": qvec[:5]},
        )
        hits = search_chunks_pgvector(
            db,
            owner_id=user.id,
            query_text=payload.query,
            query_embedding=qvec,
            top_k=payload.top_k,
        )
        for h in hits:
            raw = str(h.get("text") or "")
            h["text"] = _compact_hit_text(raw, payload.query, price_intent=price_intent)
        decision, confidence = decide_response_mode(
            payload.query,
            hits,
            answer_threshold=settings.answer_threshold,
            clarify_threshold=settings.clarify_threshold,
        )
        details: str | None = None
        clarifying_question: str | None = None
        if decision == "answer":
            answer = build_answer(payload.query, hits)
            details = "Ответ сформирован строго по найденным фрагментам документов."
        else:
            answer = ""
            clarifying_question = build_clarifying_question(payload.query)
        next_step = build_next_step(decision)
        top = hits[0] if hits else {}
        top_text = str(top.get("text") or "")
        debug_log(
            hypothesisId="H_relevance",
            location="backend/app/api/routers/search.py:43",
            message="search:top_hit_profile",
            data={
                "price_intent": price_intent,
                "top_score": float(top.get("score") or 0.0),
                "top_len": len(top_text),
                "contains_price_markers": any(m in top_text.lower() for m in ("цена", "стоимость", "тенге", "kzt", "руб")),
                "contains_penalty_markers": any(m in top_text.lower() for m in ("пен", "неусто", "штраф", "просроч")),
                "contains_digits": any(ch.isdigit() for ch in top_text),
                "top_compacted_len": len(top_text),
                "decision": decision,
                "confidence": confidence,
                "answer_len": len(answer or ""),
            },
        )
        debug_log(
            hypothesisId="H_db",
            location="backend/app/api/routers/search.py:35",
            message="search:done",
            data={"hits": len(hits)},
        )
        return SearchOut(
            answer=answer,
            details=details,
            decision=decision,
            confidence=confidence,
            clarifying_question=clarifying_question,
            next_step=next_step,
            evidence_collapsed_by_default=True,
            hits=hits,
        )
    except Exception as e:
        debug_log(
            hypothesisId="H_err",
            location="backend/app/api/routers/search.py:44",
            message="search:exception",
            data={"type": type(e).__name__, "msg": str(e)},
        )
        raise

