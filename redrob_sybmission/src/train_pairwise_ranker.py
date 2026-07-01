#!/usr/bin/env python3
"""Train a local NumPy pairwise ranking model from WorkDNA digital twins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = ROOT / "data" / "processed" / "candidate_features.jsonl"
LABELS_PATH = ROOT / "data" / "labels" / "reviewed_archetype_labels.csv"
MODEL_DIR = ROOT / "models" / "pairwise_ranker"
REPORT_DIR = ROOT / "reports"

FEATURE_NAMES = [
    "best_relevance", "second_relevance", "best_production", "best_retrieval",
    "best_evaluation", "best_ownership", "best_transferability",
    "mission_coverage", "relevant_project_count", "unique_project_archetypes",
    "years_fit", "product_company_history", "services_only_history",
    "location_fit", "activity_score", "open_to_work",
    "recruiter_response_rate", "notice_fit", "github_fit",
    "saved_by_recruiters_log", "skill_assessment_corroboration",
    "contradiction_count", "disqualifier_count",
]


def load_labels(path: Path) -> dict[str, dict[str, int]]:
    labels = {}
    for row in csv.DictReader(path.open(encoding="utf-8-sig")):
        labels[row["archetype_id"]] = {
            key: int(row[key])
            for key in [
                "relevance_tier", "production_depth",
                "retrieval_ranking_depth", "evaluation_maturity",
                "ownership", "transferability", "disqualifier",
            ]
        }
    return labels


def aggregate_projects(project_ids: list[str], labels: dict[str, dict]) -> dict:
    projects = [labels[project_id] for project_id in project_ids]
    ordered_ids = sorted(
        project_ids,
        key=lambda project_id: (
            labels[project_id]["relevance_tier"],
            labels[project_id]["retrieval_ranking_depth"],
            labels[project_id]["production_depth"],
            project_id,
        ),
        reverse=True,
    )
    ordered = [labels[project_id] for project_id in ordered_ids]
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else defaultdict(int)
    dimensions = [
        "production_depth", "retrieval_ranking_depth", "evaluation_maturity",
        "ownership", "transferability",
    ]
    return {
        "best_relevance": best["relevance_tier"],
        "second_relevance": second["relevance_tier"],
        "best_production": max(p["production_depth"] for p in projects),
        "best_retrieval": max(p["retrieval_ranking_depth"] for p in projects),
        "best_evaluation": max(p["evaluation_maturity"] for p in projects),
        "best_ownership": max(p["ownership"] for p in projects),
        "best_transferability": max(p["transferability"] for p in projects),
        "mission_coverage": sum(
            max(project[dimension] for project in projects) >= 4
            for dimension in dimensions
        ),
        "relevant_project_count": sum(p["relevance_tier"] >= 3 for p in projects),
        "disqualifier_count": sum(p["disqualifier"] for p in projects),
        "best_archetype_id": ordered_ids[0],
    }


def feature_vector(record: dict, labels: dict[str, dict]) -> tuple[np.ndarray, dict]:
    project = aggregate_projects(record["project_archetype_ids"], labels)
    years = float(record["years_of_experience"])
    values = {
        **{name: float(project[name]) for name in FEATURE_NAMES if name in project},
        "unique_project_archetypes": float(record["unique_project_archetypes"]),
        "years_fit": math.exp(-((years - 7.0) / 4.0) ** 2),
        "product_company_history": float(record["product_company_history"]),
        "services_only_history": float(record["services_only_history"]),
        "location_fit": float(record["location_fit"]),
        "activity_score": float(record["activity_score"]),
        "open_to_work": float(record["open_to_work"]),
        "recruiter_response_rate": float(record["recruiter_response_rate"]),
        "notice_fit": max(
            0.0, 1.0 - float(record["notice_period_days"]) / 180.0
        ),
        "github_fit": (
            0.0
            if float(record["github_activity_score"]) < 0
            else min(float(record["github_activity_score"]) / 100.0, 1.0)
        ),
        "saved_by_recruiters_log": float(record["saved_by_recruiters_log"]),
        "skill_assessment_corroboration": min(
            float(record["corroborated_skill_count"])
            / max(int(record["skill_count"]), 1),
            1.0,
        ),
        "contradiction_count": float(record["contradiction_count"]),
        "disqualifier_count": float(project["disqualifier_count"]),
    }
    return np.array([values[name] for name in FEATURE_NAMES]), project


def teacher_score(vector: np.ndarray) -> float:
    f = dict(zip(FEATURE_NAMES, vector))
    technical = (
        10.0 * f["best_relevance"]
        + 2.5 * f["second_relevance"]
        + 2.2 * f["best_production"]
        + 3.0 * f["best_retrieval"]
        + 2.4 * f["best_evaluation"]
        + 2.0 * f["best_ownership"]
        + 1.8 * f["best_transferability"]
        + 1.5 * f["mission_coverage"]
        + 0.8 * min(f["relevant_project_count"], 3)
    )
    context = (
        1.8 * f["years_fit"]
        + 1.5 * f["product_company_history"]
        - 2.5 * f["services_only_history"]
        + 0.8 * f["location_fit"]
        + 0.7 * f["skill_assessment_corroboration"]
    )
    hireability = (
        1.1 * f["activity_score"]
        + 0.5 * f["open_to_work"]
        + 0.8 * f["recruiter_response_rate"]
        + 0.5 * f["notice_fit"]
        + 0.25 * f["github_fit"]
        + 0.15 * min(f["saved_by_recruiters_log"], 4.0)
    )
    penalty = 5.0 * f["contradiction_count"] + 18.0 * f["disqualifier_count"]
    return technical + context + hireability - penalty


def split_name(archetype_id: str) -> str:
    value = int(hashlib.sha256(archetype_id.encode()).hexdigest()[:8], 16) % 10
    return "train" if value < 7 else "validation" if value < 9 else "test"


def load_candidates(
    features_path: Path, labels: dict[str, dict]
) -> tuple[list[dict], np.ndarray]:
    records, vectors = [], []
    with features_path.open(encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            vector, project = feature_vector(raw, labels)
            records.append({
                "candidate_id": raw["candidate_id"],
                "best_archetype_id": project["best_archetype_id"],
                "project_signature": "|".join(
                    sorted(set(raw["project_archetype_ids"]))
                ),
                "teacher_score": teacher_score(vector),
                "best_relevance": project["best_relevance"],
                "split": split_name(project["best_archetype_id"]),
            })
            vectors.append(vector)
    return records, np.vstack(vectors)


def build_pairs(
    records: list[dict],
    vectors: np.ndarray,
    split: str,
    max_pairs: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, dict]:
    rng = np.random.default_rng(seed)
    indices = [
        index for index, record in enumerate(records)
        if record["split"] == split
    ]
    groups = defaultdict(list)
    by_tier = defaultdict(list)
    for index in indices:
        groups[records[index]["project_signature"]].append(index)
        by_tier[int(records[index]["best_relevance"])].append(index)

    pairs = []
    pair_types = Counter()

    # Behavioral twins have identical project evidence.
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda i: records[i]["teacher_score"])
        for better, worse in [
            (ordered[-1], ordered[0]),
            (ordered[-1], ordered[len(ordered) // 2]),
        ]:
            if records[better]["teacher_score"] - records[worse]["teacher_score"] > 0.35:
                pairs.append((better, worse))
                pair_types["behavioral_twins"] += 1

    tiers = sorted(by_tier)
    for _ in range(min(max_pairs // 2, 150_000)):
        low, high = sorted(rng.choice(tiers, 2, replace=False))
        better = int(rng.choice(by_tier[int(high)]))
        worse = int(rng.choice(by_tier[int(low)]))
        pairs.append((better, worse))
        pair_types["cross_tier"] += 1

    for _ in range(max(0, min(max_pairs - len(pairs), 150_000))):
        tier = int(rng.choice(tiers))
        pool = by_tier[tier]
        if len(pool) < 2:
            continue
        first, second = map(int, rng.choice(pool, 2, replace=False))
        difference = records[first]["teacher_score"] - records[second]["teacher_score"]
        if abs(difference) < 0.25:
            continue
        pairs.append((first, second) if difference > 0 else (second, first))
        pair_types["within_tier"] += 1

    if len(pairs) > max_pairs:
        selected = rng.choice(len(pairs), max_pairs, replace=False)
        pairs = [pairs[index] for index in selected]
    differences = np.vstack([vectors[a] - vectors[b] for a, b in pairs])
    signs = rng.choice(np.array([-1.0, 1.0]), size=len(pairs))
    differences *= signs[:, None]
    labels_out = (signs > 0).astype(np.float64)
    return differences, labels_out, dict(pair_types)


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -35, 35)))


def accuracy(x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float:
    return float(np.mean((sigmoid(x @ weights) >= 0.5) == y))


def train_ranknet(
    x: np.ndarray,
    y: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
    epochs: int = 12,
    seed: int = 42,
) -> tuple[np.ndarray, list[dict]]:
    rng = np.random.default_rng(seed)
    weights = np.zeros(x.shape[1])
    best_weights = weights.copy()
    best_validation = -1.0
    history = []
    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(x))
        for start in range(0, len(x), 4096):
            batch = order[start : start + 4096]
            xb, yb = x[batch], y[batch]
            gradient = xb.T @ (sigmoid(xb @ weights) - yb) / len(batch)
            weights -= 0.035 * (gradient + 0.002 * weights)
        train_acc = accuracy(x, y, weights)
        validation_acc = accuracy(validation_x, validation_y, weights)
        history.append({
            "epoch": epoch,
            "train_pairwise_accuracy": round(train_acc, 6),
            "validation_pairwise_accuracy": round(validation_acc, 6),
        })
        if validation_acc > best_validation:
            best_validation = validation_acc
            best_weights = weights.copy()
    return best_weights, history


def ndcg_at_k(scores: np.ndarray, relevance: np.ndarray, k: int) -> float:
    order = np.argsort(-scores)[:k]
    ideal = np.argsort(-relevance)[:k]
    discounts = np.log2(np.arange(2, len(order) + 2))
    dcg = np.sum((2.0 ** relevance[order] - 1.0) / discounts)
    idcg = np.sum((2.0 ** relevance[ideal] - 1.0) / discounts)
    return float(dcg / idcg) if idcg else 0.0


def explain(
    vector: np.ndarray, weights: np.ndarray, mean: np.ndarray, scale: np.ndarray
) -> list[str]:
    contributions = ((vector - mean) / scale) * weights
    return [
        FEATURE_NAMES[index]
        for index in np.argsort(-contributions)
        if contributions[index] > 0
    ][:3]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-train-pairs", type=int, default=80_000)
    parser.add_argument("--max-eval-pairs", type=int, default=20_000)
    args = parser.parse_args()

    labels = load_labels(LABELS_PATH)
    records, vectors = load_candidates(FEATURES_PATH, labels)
    train_x, train_y, train_types = build_pairs(
        records, vectors, "train", args.max_train_pairs, 42
    )
    validation_x, validation_y, validation_types = build_pairs(
        records, vectors, "validation", args.max_eval_pairs, 43
    )
    test_x, test_y, test_types = build_pairs(
        records, vectors, "test", args.max_eval_pairs, 44
    )

    mean, scale = train_x.mean(axis=0), train_x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    train_scaled = (train_x - mean) / scale
    validation_scaled = (validation_x - mean) / scale
    test_scaled = (test_x - mean) / scale
    weights, history = train_ranknet(
        train_scaled, train_y, validation_scaled, validation_y
    )

    candidate_scaled = (vectors - mean) / scale
    model_scores = candidate_scaled @ weights
    teacher_scores = np.array([record["teacher_score"] for record in records])
    relevance = np.array([record["best_relevance"] for record in records])
    order = sorted(
        range(len(records)),
        key=lambda index: (-model_scores[index], records[index]["candidate_id"]),
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "model.json"
    model_path.write_text(json.dumps({
        "model_type": "numpy_pairwise_logistic_ranker",
        "feature_names": FEATURE_NAMES,
        "weights": weights.tolist(),
        "mean": mean.tolist(),
        "scale": scale.tolist(),
    }, indent=2) + "\n", encoding="utf-8")

    ranking_path = REPORT_DIR / "step2_ranked_candidates.csv"
    with ranking_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "candidate_id", "rank", "model_score", "relevance_tier",
            "teacher_score", "best_archetype_id", "top_positive_factors",
        ])
        for rank, index in enumerate(order, 1):
            writer.writerow([
                records[index]["candidate_id"], rank, f"{model_scores[index]:.8f}",
                records[index]["best_relevance"], f"{teacher_scores[index]:.5f}",
                records[index]["best_archetype_id"],
                "|".join(explain(vectors[index], weights, mean, scale)),
            ])

    report = {
        "candidate_count": len(records),
        "feature_count": len(FEATURE_NAMES),
        "pair_counts": {
            "train": len(train_y), "validation": len(validation_y),
            "test": len(test_y),
        },
        "pair_types": {
            "train": train_types, "validation": validation_types,
            "test": test_types,
        },
        "metrics": {
            "train_pairwise_accuracy": accuracy(train_scaled, train_y, weights),
            "validation_pairwise_accuracy": accuracy(
                validation_scaled, validation_y, weights
            ),
            "test_pairwise_accuracy": accuracy(test_scaled, test_y, weights),
            "ndcg_at_10_vs_reviewed_tiers": ndcg_at_k(
                model_scores, relevance, 10
            ),
            "ndcg_at_50_vs_reviewed_tiers": ndcg_at_k(
                model_scores, relevance, 50
            ),
            "score_teacher_correlation": float(
                np.corrcoef(model_scores, teacher_scores)[0, 1]
            ),
        },
        "split_candidate_counts": dict(Counter(r["split"] for r in records)),
        "learned_weights": dict(zip(FEATURE_NAMES, weights.tolist())),
        "last_training_epoch": history[-1],
        "artifacts": {
            "model": str(model_path.resolve()),
            "ranking": str(ranking_path.resolve()),
        },
    }
    report_path = REPORT_DIR / "step2_training_report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
