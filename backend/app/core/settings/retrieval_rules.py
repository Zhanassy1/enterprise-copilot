"""Tunable weights for domain-specific retrieval rules (post-RRF heuristics)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalRuleWeights(BaseModel):
    """Scale RRF fusion score so it aligns with ``retrieval_min_score`` and additive bonuses."""

    rrf_score_scale: float = Field(
        default=50.0,
        ge=1.0,
        le=2000.0,
        description="Multiply raw RRF score before adding overlap/bonuses (historically tuned to min_score).",
    )
    overlap_weight: float = Field(default=0.40, ge=0.0, le=2.0)
    bonus_contract_value_with_amount: float = Field(default=0.22, ge=0.0, le=1.0)
    hard_penalty_security_deposit_mismatch: float = Field(default=0.55, ge=0.0, le=2.0)
    bonus_price_line_markers: float = Field(default=0.10, ge=0.0, le=1.0)
    bonus_price_monetary_amount: float = Field(default=0.06, ge=0.0, le=1.0)
    bonus_penalty_markers: float = Field(default=0.12, ge=0.0, le=1.0)
    bonus_termination_markers: float = Field(default=0.12, ge=0.0, le=1.0)
    hard_penalty_intent_mismatch: float = Field(default=0.35, ge=0.0, le=2.0)
    hard_penalty_zero_keyword_overlap: float = Field(default=0.12, ge=0.0, le=2.0)
    length_penalty_chars_threshold: int = Field(default=1200, ge=0, le=50000)
    length_penalty_divisor: float = Field(default=5000.0, ge=1.0, le=50000.0)
    length_penalty_cap: float = Field(default=0.12, ge=0.0, le=1.0)
