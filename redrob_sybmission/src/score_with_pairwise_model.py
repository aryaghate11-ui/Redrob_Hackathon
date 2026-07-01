#!/usr/bin/env python3
"""Score the WorkDNA candidate feature store with the saved pairwise model."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import train_pairwise_ranker as ranker


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "models" / "pairwise_ranker" / "model.json"
DEFAULT_OUTPUT = ROOT / "reports" / "step2_top100.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--features", type=Path, default=ranker.FEATURES_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=100)
    args = parser.parse_args()

    model = json.loads(args.model.read_text(encoding="utf-8"))
    labels = ranker.load_labels(ranker.LABELS_PATH)
    records, vectors = ranker.load_candidates(args.features, labels)
    mean = np.array(model["mean"])
    scale = np.array(model["scale"])
    weights = np.array(model["weights"])
    scores = ((vectors - mean) / scale) @ weights
    order = sorted(
        range(len(records)),
        key=lambda index: (-scores[index], records[index]["candidate_id"]),
    )[: args.top_k]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "candidate_id", "rank", "score", "relevance_tier",
            "best_archetype_id", "top_positive_factors",
        ])
        for rank, index in enumerate(order, 1):
            writer.writerow([
                records[index]["candidate_id"],
                rank,
                f"{scores[index]:.8f}",
                records[index]["best_relevance"],
                records[index]["best_archetype_id"],
                "|".join(
                    ranker.explain(vectors[index], weights, mean, scale)
                ),
            ])
    print(f"Wrote {len(order)} ranked candidates to {args.out}")


if __name__ == "__main__":
    main()
