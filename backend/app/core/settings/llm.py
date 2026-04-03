from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    # ML / Embeddings
    embedding_model_name: str = Field(default="BAAI/bge-small-en-v1.5")

    # LLM (OpenAI-compatible)
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_max_context_tokens: int = Field(default=6000)
    llm_temperature: float = Field(default=0.2)

    # Precision-first decision thresholds
    answer_threshold: float = Field(default=0.62, ge=0.0, le=1.0)
    clarify_threshold: float = Field(default=0.42, ge=0.0, le=1.0)
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
