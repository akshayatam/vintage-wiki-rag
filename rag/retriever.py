# rag/retriever.py
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


class Retriever:
    def __init__(
        self,
        index_dir: str,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        use_gpu: bool = False,
        gpu_id: int = 0,
        skip_redirects: bool = True,
        allowed_doc_types: Optional[Set[str]] = None,
    ):
        """
        index_dir: folder with faiss.index + meta.jsonl
        skip_redirects: drop chunks where meta['is_redirect'] is True
        allowed_doc_types: if provided, only keep chunks whose doc_type is in the set
        """
        self.index_dir = Path(index_dir)
        self.metas: List[Dict[str, Any]] = []
        with (self.index_dir / "meta.jsonl").open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                m = json.loads(line)
                m.setdefault("chunk_id", m.get("id", ""))   # old -> new
                m.setdefault("section", m.get("title", "")) # safety
                m.setdefault("doc_type", "")
                m.setdefault("is_redirect", False)
                self.metas.append(m)

        if not self.metas:
            raise RuntimeError("No metadata loaded from meta.jsonl")

        self.index = faiss.read_index(str(self.index_dir / "faiss.index"))

        self.model = SentenceTransformer(model_name)
        # if use_gpu:
        #     self.model = self.model.to(f"cuda:{gpu_id}")

        self.skip_redirects = skip_redirects
        self.allowed_doc_types = allowed_doc_types

    def _passes_filters(self, m: Dict[str, Any]) -> bool:
        if self.skip_redirects and m.get("is_redirect", False):
            return False
        if self.allowed_doc_types is not None and m.get("doc_type", "") not in self.allowed_doc_types:
            return False
        return True

    def search(
        self,
        query: str,
        k: int = 5,
        dedupe_by_url: bool = False,
        max_per_url: int = 1,
        min_score: float = -1.0,
    ) -> List[Dict[str, Any]]:
        """
        dedupe_by_url: if True, limit results per URL to max_per_url
        min_score: drop results with score below this (cosine similarity, -1..1)
        """
        qv = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        D, I = self.index.search(qv, max(k * 4, k))  # overfetch a bit, then filter
        D, I = D[0].tolist(), I[0].tolist()

        results: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {}
        for score, idx in zip(D, I):
            if idx == -1:
                continue
            if score < min_score:
                continue
            m = self.metas[idx]
            if not self._passes_filters(m):
                continue

            url = m.get("url", "")
            if dedupe_by_url:
                c = counts.get(url, 0)
                if c >= max_per_url:
                    continue
                counts[url] = c + 1

            results.append({
                "score": float(score),
                "url": url,
                "title": m.get("title", ""),
                "section": m.get("section", m.get("title", "")),
                "chunk_id": m.get("chunk_id", m.get("id", "")),
                "text": m.get("text", ""),
                "doc_type": m.get("doc_type", ""),
                "is_redirect": bool(m.get("is_redirect", False)),
            })

            if len(results) >= k and not dedupe_by_url:
                break

            # When deduping, we may need to keep scanning to fill k diverse hits
            if dedupe_by_url and len(results) >= k:
                break

        return results
