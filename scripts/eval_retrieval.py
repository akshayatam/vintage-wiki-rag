# scripts/eval_retrieval.py
import json, argparse
from pathlib import Path
from statistics import mean
from rag.retriever import Retriever


def eval_retrieval(index_dir, qa_path, k=10):
    R = Retriever(index_dir)
    qs, recalls, mrrs, first_ranks, zeros = 0, [], [], [], 0

    with open(qa_path, encoding="utf-8") as f:
        for line in f:
            ex = json.loads(line)
            qs += 1
            gold = set(ex["gold_ids"])
            hits = R.search(ex["query"], k=k)
            rank = None
            for i, h in enumerate(hits, 1):
                if h["chunk_id"] in gold:
                    rank = i
                    break
            if rank is None:
                zeros += 1
                recalls.append(0.0)
                mrrs.append(0.0)
                first_ranks.append(None)
            else:
                recalls.append(1.0)
                mrrs.append(1.0 / rank)
                first_ranks.append(rank)

    print(f"Queries: {qs}")
    print(f"Recall@{k}: {mean(recalls):.3f}")
    print(f"MRR@{k}: {mean(mrrs):.3f}")
    fr = [r for r in first_ranks if r is not None]
    if fr:
        print(f"Mean first-hit rank: {mean(fr):.2f}")
    print(f"Zero-hit rate: {zeros/qs:.3f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-dir", default="index/alps")
    ap.add_argument("--qa", default="data/eval/alps_qa.jsonl")
    ap.add_argument("-k", type=int, default=10)
    args = ap.parse_args()
    eval_retrieval(args.index_dir, args.qa, k=args.k)
