# rag/api.py
import os
import time
from typing import List, Optional, Set

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from .retriever import Retriever

INDEX_DIR = os.getenv("RAG_INDEX_DIR", "index/alps")

app = FastAPI(title="Vintage Wiki RAG")

# Optional CORS for local Streamlit/UI
if os.getenv("RAG_ENABLE_CORS", "1") == "1":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Construct retriever at startup
try:
    retriever = Retriever(
        INDEX_DIR,
        skip_redirects=True,
        allowed_doc_types=None,   # e.g., {"switch"} if later want to limit
    )
except Exception as e:
    # Fail fast with a clear message if index isn't present
    raise RuntimeError(f"Failed to load index from {INDEX_DIR}: {e}")

class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(5, ge=1, le=50)

    # Optional knobs
    dedupe_by_url: bool = False
    max_per_url: int = Field(1, ge=1)
    min_score: float = -1.0
    skip_redirects: Optional[bool] = None
    allowed_doc_types: Optional[List[str]] = None

    @validator("min_score")
    def _score_range(cls, v):
        if v < -1.0 or v > 1.0:
            raise ValueError("min_score must be in [-1.0, 1.0]")
        return v


class Passage(BaseModel):
    score: float
    url: str
    title: str
    section: str
    chunk_id: str
    text: str
    doc_type: Optional[str] = None
    is_redirect: Optional[bool] = None


class AskResponse(BaseModel):
    query: str
    passages: List[Passage]
    took_ms: int

@app.get("/health")
def health():
    return {
        "ok": True,
        "chunks": len(retriever.metas),
        "index_dir": INDEX_DIR,
        "model": "sentence-transformers/all-MiniLM-L6-v2",
    }


@app.post("/search", response_model=AskResponse)
def search(req: AskRequest):
    t0 = time.time()

    # Apply request-level overrides without mutating the retriever
    original_skip = retriever.skip_redirects
    original_types = retriever.allowed_doc_types
    try:
        if req.skip_redirects is not None:
            retriever.skip_redirects = req.skip_redirects
        if req.allowed_doc_types is not None:
            retriever.allowed_doc_types = set(req.allowed_doc_types)

        hits = retriever.search(
            req.query,
            k=req.k,
            dedupe_by_url=req.dedupe_by_url,
            max_per_url=req.max_per_url,
            min_score=req.min_score,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")
    finally:
        retriever.skip_redirects = original_skip
        retriever.allowed_doc_types = original_types

    took_ms = int((time.time() - t0) * 1000)
    return {"query": req.query, "passages": hits, "took_ms": took_ms}
