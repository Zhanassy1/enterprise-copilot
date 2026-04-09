from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

AnswerStyle = Literal["concise", "narrative"]


class LLMSettings(BaseModel):
    # ML / Embeddings
    embedding_model_name: str = Field(default="BAAI/bge-small-en-v1.5")

    # LLM (OpenAI-compatible)
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    llm_model: str = Field(default="gpt-4o")
    llm_max_context_tokens: int = Field(default=6000)
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_request_timeout_seconds: float = Field(default=120.0, ge=5.0, le=600.0)

    # RAG: prior turns in session (budget for prompt; assistant replies truncated)
    chat_history_max_messages: int = Field(default=16, ge=2, le=64)
    chat_history_budget_tokens: int = Field(default=1200, ge=200, le=8000)
    chat_history_assistant_max_chars: int = Field(default=900, ge=200, le=8000)
    chat_history_user_max_chars: int = Field(default=1200, ge=200, le=8000)

    # Precision-first decision thresholds
    answer_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    clarify_threshold: float = Field(default=0.48, ge=0.0, le=1.0)
    retrieval_min_score: float = Field(default=0.22, ge=0.0, le=1.0)
    retrieval_max_near_duplicate_overlap: float = Field(default=0.90, ge=0.0, le=1.0)
    retrieval_hybrid_enabled: bool = Field(default=True)
    retrieval_rrf_k: int = Field(default=60, ge=1, le=2000)
    retrieval_rrf_weight_dense: float = Field(default=1.0, ge=0.0, le=10.0)
    retrieval_rrf_weight_keyword: float = Field(default=1.0, ge=0.0, le=10.0)
    retrieval_candidate_multiplier: int = Field(default=10, ge=2, le=100)
    retrieval_candidate_floor: int = Field(default=60, ge=10, le=1000)
    reranker_enabled: bool = Field(default=True)
    reranker_model_name: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    reranker_top_n: int = Field(default=30, ge=2, le=200)

    # RAG: concise = short grounded line for prices; narrative = 2–4 sentences with brief context
    default_answer_style: AnswerStyle = Field(default="concise")

    @model_validator(mode="after")
    def clarify_below_answer(self) -> Self:
        if self.clarify_threshold >= self.answer_threshold:
            raise ValueError("clarify_threshold must be strictly less than answer_threshold")
        return self
