# scripts/chunk_and_index.py
import json, re, argparse, hashlib
from pathlib import Path
from typing import Iterable, Dict, Any, Tuple, List, Optional

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# ---------- DEFAULTS ----------
DEF_EMB_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"
DEF_CHUNK_CHARS = 3000
DEF_OVERLAP     = 300
DEF_MIN_CHARS   = 200
# ------------------------------

RE_WIKI   = re.compile(r"^={2,6}\s*(.*?)\s*={2,6}\s*$", re.M)
RE_MD     = re.compile(r"^#{1,6}\s*(.*?)\s*$", re.M)
RE_WS     = re.compile(r"\s+")

def _norm_space(s: str) -> str:
    return RE_WS.sub(" ", (s or "").strip())

def _hash_id(*parts: str) -> str:
    h = hashlib.blake2b(digest_size=12)
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()

def _from_anycrawl(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Adapt a full AnyCrawl JSON blob into a simple doc dict, else None."""
    d = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(d, dict):
        return None
    title = d.get("title") or "Untitled"
    url   = d.get("url") or d.get("pageURL") or raw.get("url") or ""
    md    = d.get("markdown") or ""

    return {
        "title": title,
        "url": url,
        "text": md,
        "doc_type": raw.get("doc_type", ""),
        "is_redirect": "Redirected from" in md if isinstance(md, str) else False
    }

def _from_simple_line(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Accepts a 'clean' line like {title,url,text,section?,doc_type?}
    Returns a doc (whole-page view); section is ignored here—we’ll re-chunk.
    """
    # Must have at least title/url/text
    if not all(k in raw for k in ("title","url","text")):
        return None
    return {
        "title": raw["title"],
        "url": raw["url"],
        "text": raw["text"],
        "doc_type": raw.get("doc_type",""),
        "is_redirect": bool(raw.get("is_redirect", False))
    }

def parse_input_line(line: str) -> Optional[Dict[str, Any]]:
    try:
        raw = json.loads(line)
    except Exception:
        return None
    d = _from_simple_line(raw)
    if d: return d
    d = _from_anycrawl(raw)
    return d

def split_sections(title: str, text: str) -> List[Tuple[str,str]]:
    """Return list of (section_path, body). Handles Markdown and MediaWiki headings."""
    if not text:
        return []

    # Try Markdown first
    parts = RE_MD.split(text)
    if len(parts) > 1:
        out = []
        prelude = parts[0].strip()
        if prelude:
            out.append((f"{title} > Introduction", prelude))
        for i in range(1, len(parts), 2):
            heading = parts[i].strip() or "Section"
            body    = parts[i+1].strip()
            if body:
                out.append((f"{title} > {heading}", body))
        return out

    # Fallback to MediaWiki
    parts = RE_WIKI.split(text)
    if len(parts) > 1:
        out = []
        prelude = parts[0].strip()
        if prelude:
            out.append((f"{title} > Introduction", prelude))
        for i in range(1, len(parts), 2):
            heading = parts[i].strip() or "Section"
            body    = parts[i+1].strip()
            if body:
                out.append((f"{title} > {heading}", body))
        return out

    # No headings at all
    body = text.strip()
    return [(f"{title} > Full", body)] if body else []

def overlap_chunks(text: str, max_chars: int, overlap: int) -> Iterable[Tuple[int,str]]:
    i, n = 0, len(text)
    while i < n:
        j = min(i + max_chars, n)
        seg = text[i:j].strip()
        if seg:
            yield (i, seg)          # Start offset for stable IDs
        if j == n:
            break
        i = j - overlap

def yield_chunks(doc: Dict[str, Any], max_chars: int, overlap: int, min_chars: int) -> Iterable[Dict[str, Any]]:
    title = doc.get("title") or "Untitled"
    url   = doc.get("url") or ""
    text  = doc.get("text") or ""
    doc_type    = doc.get("doc_type","")
    is_redirect = bool(doc.get("is_redirect", False))

    for sec_path, body in split_sections(title, text):
        for start, seg in overlap_chunks(body, max_chars, overlap):
            if len(seg) < min_chars:
                continue
            chunk_id = _hash_id(url, sec_path, str(start))
            yield {
                "id": chunk_id,
                "url": url,
                "title": title,
                "section": sec_path,
                "text": seg,
                "doc_type": doc_type,
                "is_redirect": is_redirect
            }

def build(args):
    in_path   = Path(args.input)
    out_dir   = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.jsonl"
    index_path= out_dir / "faiss.index"

    model = SentenceTransformer(args.model)

    metas: List[Dict[str, Any]] = []
    vecs:  List[np.ndarray] = []

    total = sum(1 for _ in open(in_path, encoding="utf-8"))
    with open(in_path, encoding="utf-8") as fin:
        for line in tqdm(fin, total=total, desc="Chunking & embedding"):
            line = line.strip()
            if not line:
                continue
            doc = parse_input_line(line)
            if not doc:
                continue
            # optional filter
            if args.contains and args.contains.lower() not in (doc.get("title","") + " " + doc.get("url","")).lower():
                continue
            if args.exclude and args.exclude.lower() in (doc.get("title","") + " " + doc.get("url","")).lower():
                continue

            for ch in yield_chunks(doc, args.chunk_chars, args.overlap, args.min_chars):
                emb = model.encode(ch["text"], normalize_embeddings=True)
                vecs.append(emb.astype("float32"))
                metas.append(ch)

    if not vecs:
        raise SystemExit("No chunks produced — check input data and filters.")

    X = np.vstack(vecs).astype("float32")
    index = faiss.IndexFlatIP(X.shape[1])   # Cosine (vectors are normalized)
    index.add(X)
    faiss.write_index(index, str(index_path))

    with open(meta_path, "w", encoding="utf-8") as fout:
        for m in metas:
            fout.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"Indexed {len(metas)} chunks to {index_path}")
    print(f"Meta written to {meta_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/raw/docs.jsonl")
    ap.add_argument("--out-dir", default="index/faiss")
    ap.add_argument("--model", default=DEF_EMB_MODEL)
    ap.add_argument("--chunk-chars", type=int, default=DEF_CHUNK_CHARS)
    ap.add_argument("--overlap", type=int, default=DEF_OVERLAP)
    ap.add_argument("--min-chars", type=int, default=DEF_MIN_CHARS)
    ap.add_argument("--contains", default="", help="Only include docs whose title/url contains this substring (case-insensitive).")
    ap.add_argument("--exclude", default="", help="Exclude docs whose title/url contains this substring.")
    args = ap.parse_args()
    build(args)
