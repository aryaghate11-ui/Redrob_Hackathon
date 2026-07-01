#!/usr/bin/env python3
"""Stress-test the saved WorkDNA ranker and issue Rank Stability Certificates."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

import train_pairwise_ranker as ranker


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "pairwise_ranker" / "model.json"
TOP100_PATH = ROOT / "reports" / "step2_top100.csv"
OUTPUT_DIR = ROOT / "reports" / "counterfactual"
RAW_CANDIDATES = (
    ROOT.parent
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
    / "candidates.jsonl"
)

INDEX = {name: index for index, name in enumerate(ranker.FEATURE_NAMES)}


def set_feature(vector: np.ndarray, name: str, value: float) -> np.ndarray:
    result = vector.copy()
    result[INDEX[name]] = value
    return result


def score(
    vector: np.ndarray, weights: np.ndarray, mean: np.ndarray, scale: np.ndarray
) -> float:
    return float(((vector - mean) / scale) @ weights)


def counterfactuals(vector: np.ndarray) -> dict[str, np.ndarray]:
    cases = {}

    # Skills do not independently create technical relevance.
    cases["skills_removed"] = set_feature(
        vector, "skill_assessment_corroboration", 0.0
    )
    cases["perfect_keywords_injected"] = vector.copy()

    # Company names are absent; only broad product/service context is retained.
    employer_neutral = set_feature(vector, "product_company_history", 0.0)
    employer_neutral = set_feature(
        employer_neutral, "services_only_history", 0.0
    )
    cases["employer_neutralized"] = employer_neutral

    # Neutral values represent an average, reachable candidate.
    behavior_neutral = vector.copy()
    for name, value in {
        "activity_score": 0.5,
        "open_to_work": 0.5,
        "recruiter_response_rate": 0.5,
        "notice_fit": 0.5,
        "github_fit": 0.5,
        "saved_by_recruiters_log": 2.0,
    }.items():
        behavior_neutral[INDEX[name]] = value
    cases["behavior_neutralized"] = behavior_neutral

    unavailable = vector.copy()
    for name, value in {
        "activity_score": 0.0,
        "open_to_work": 0.0,
        "recruiter_response_rate": 0.05,
        "notice_fit": 0.0,
        "saved_by_recruiters_log": 0.0,
    }.items():
        unavailable[INDEX[name]] = value
    cases["made_unavailable"] = unavailable

    contradiction = vector.copy()
    contradiction[INDEX["contradiction_count"]] += 1.0
    cases["contradiction_injected"] = contradiction

    no_production = set_feature(vector, "best_production", 0.0)
    no_production[INDEX["mission_coverage"]] = max(
        0.0, no_production[INDEX["mission_coverage"]] - 1.0
    )
    cases["production_evidence_removed"] = no_production

    no_evaluation = set_feature(vector, "best_evaluation", 0.0)
    no_evaluation[INDEX["mission_coverage"]] = max(
        0.0, no_evaluation[INDEX["mission_coverage"]] - 1.0
    )
    cases["evaluation_evidence_removed"] = no_evaluation

    no_ownership = set_feature(vector, "best_ownership", 0.0)
    no_ownership[INDEX["mission_coverage"]] = max(
        0.0, no_ownership[INDEX["mission_coverage"]] - 1.0
    )
    cases["ownership_evidence_removed"] = no_ownership

    no_projects = vector.copy()
    for name in [
        "best_relevance",
        "second_relevance",
        "best_production",
        "best_retrieval",
        "best_evaluation",
        "best_ownership",
        "best_transferability",
        "mission_coverage",
        "relevant_project_count",
    ]:
        no_projects[INDEX[name]] = 0.0
    cases["all_project_evidence_removed"] = no_projects
    return cases


def rank_against_pool(
    candidate_id: str,
    candidate_score: float,
    baseline_scores: np.ndarray,
    candidate_ids: np.ndarray,
) -> int:
    other_candidate = candidate_ids != candidate_id
    higher = int(
        np.sum(other_candidate & (baseline_scores > candidate_score))
    )
    tied_before = int(
        np.sum(
            other_candidate
            & (np.isclose(baseline_scores, candidate_score, atol=1e-12))
            & (candidate_ids < candidate_id)
        )
    )
    return higher + tied_before + 1


def load_profiles(candidate_ids: set[str]) -> dict[str, dict]:
    profiles = {}
    with RAW_CANDIDATES.open(encoding="utf-8") as handle:
        for line in handle:
            candidate = json.loads(line)
            candidate_id = candidate["candidate_id"]
            if candidate_id not in candidate_ids:
                continue
            profile = candidate["profile"]
            profiles[candidate_id] = {
                "current_title": profile["current_title"],
                "current_company": profile["current_company"],
                "years_of_experience": profile["years_of_experience"],
                "location": profile["location"],
            }
            if len(profiles) == len(candidate_ids):
                break
    return profiles


def bounded_score(value: float) -> int:
    return int(round(max(0.0, min(100.0, value))))


def stability_scores(
    baseline_rank: int,
    results: dict[str, dict],
) -> dict[str, int]:
    skill_drop = max(0, results["skills_removed"]["rank"] - baseline_rank)
    keyword_move = abs(
        results["perfect_keywords_injected"]["rank"] - baseline_rank
    )
    employer_move = abs(
        results["employer_neutralized"]["rank"] - baseline_rank
    )
    project_drop = max(
        0, results["all_project_evidence_removed"]["rank"] - baseline_rank
    )
    contradiction_drop = max(
        0, results["contradiction_injected"]["rank"] - baseline_rank
    )
    unavailable_drop = max(
        0, results["made_unavailable"]["rank"] - baseline_rank
    )

    keyword_independence = bounded_score(100 - min(keyword_move, 100))
    skill_independence = bounded_score(100 - min(skill_drop, 100))
    prestige_independence = bounded_score(100 - min(employer_move * 2, 100))
    project_reliance = bounded_score(100 * (1 - math.exp(-project_drop / 500)))
    credibility_sensitivity = bounded_score(
        100 * (1 - math.exp(-contradiction_drop / 50))
    )
    availability_sensitivity = bounded_score(
        100 * (1 - math.exp(-unavailable_drop / 100))
    )
    overall = bounded_score(
        0.25 * keyword_independence
        + 0.20 * skill_independence
        + 0.15 * prestige_independence
        + 0.30 * project_reliance
        + 0.10 * credibility_sensitivity
    )
    return {
        "overall_stability": overall,
        "keyword_independence": keyword_independence,
        "skill_list_independence": skill_independence,
        "company_context_independence": prestige_independence,
        "project_evidence_reliance": project_reliance,
        "credibility_sensitivity": credibility_sensitivity,
        "availability_sensitivity": availability_sensitivity,
    }


def verdict(scores: dict[str, int]) -> str:
    if (
        scores["overall_stability"] >= 85
        and scores["project_evidence_reliance"] >= 85
    ):
        return "robust_evidence_driven"
    if scores["overall_stability"] >= 70:
        return "acceptable_with_review"
    return "fragile_requires_review"


def aggregate_full_pool_tests(
    vectors: np.ndarray,
    baseline_scores: np.ndarray,
    weights: np.ndarray,
    mean: np.ndarray,
    scale: np.ndarray,
    relevance: np.ndarray,
) -> dict:
    keyword_scores = baseline_scores.copy()
    contradiction_vectors = vectors.copy()
    contradiction_vectors[:, INDEX["contradiction_count"]] += 1
    contradiction_scores = ((contradiction_vectors - mean) / scale) @ weights

    skill_vectors = vectors.copy()
    skill_vectors[:, INDEX["skill_assessment_corroboration"]] = 1.0
    skill_scores = ((skill_vectors - mean) / scale) @ weights

    no_project_vectors = vectors.copy()
    for name in [
        "best_relevance",
        "second_relevance",
        "best_production",
        "best_retrieval",
        "best_evaluation",
        "best_ownership",
        "best_transferability",
        "mission_coverage",
        "relevant_project_count",
    ]:
        no_project_vectors[:, INDEX[name]] = 0.0
    no_project_scores = ((no_project_vectors - mean) / scale) @ weights

    original_top100 = set(np.argsort(-baseline_scores)[:100])
    keyword_top100 = set(np.argsort(-keyword_scores)[:100])
    skill_top100 = set(np.argsort(-skill_scores)[:100])
    irrelevant = relevance <= 1

    return {
        "keyword_injection": {
            "maximum_absolute_score_change": float(
                np.max(np.abs(keyword_scores - baseline_scores))
            ),
            "top100_membership_changes": len(
                original_top100.symmetric_difference(keyword_top100)
            ),
            "passed": bool(np.array_equal(keyword_scores, baseline_scores)),
        },
        "perfect_skill_corroboration": {
            "irrelevant_candidates_entering_top100": int(
                sum(index in skill_top100 for index in np.flatnonzero(irrelevant))
            ),
            "top100_membership_changes": len(
                original_top100.symmetric_difference(skill_top100)
            ),
            "passed": not any(
                index in skill_top100 for index in np.flatnonzero(irrelevant)
            ),
        },
        "contradiction_injection": {
            "candidates_with_lower_score": int(
                np.sum(contradiction_scores < baseline_scores)
            ),
            "candidate_count": len(vectors),
            "passed": bool(np.all(contradiction_scores < baseline_scores)),
        },
        "project_evidence_removal": {
            "median_score_drop": float(
                np.median(baseline_scores - no_project_scores)
            ),
            "tier5_median_score_drop": float(
                np.median(
                    baseline_scores[relevance == 5]
                    - no_project_scores[relevance == 5]
                )
            ),
            "passed": bool(
                np.median(
                    baseline_scores[relevance == 5]
                    - no_project_scores[relevance == 5]
                )
                > 1.0
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    labels = ranker.load_labels(ranker.LABELS_PATH)
    records, vectors = ranker.load_candidates(ranker.FEATURES_PATH, labels)
    weights = np.array(model["weights"])
    mean = np.array(model["mean"])
    scale = np.array(model["scale"])
    baseline_scores = ((vectors - mean) / scale) @ weights
    candidate_ids = np.array([record["candidate_id"] for record in records])
    relevance = np.array([record["best_relevance"] for record in records])
    index_by_id = {
        candidate_id: index for index, candidate_id in enumerate(candidate_ids)
    }
    baseline_order = sorted(
        range(len(records)),
        key=lambda index: (-baseline_scores[index], records[index]["candidate_id"]),
    )
    baseline_rank = {
        records[index]["candidate_id"]: rank
        for rank, index in enumerate(baseline_order, 1)
    }
    shortlisted_ids = [
        records[index]["candidate_id"] for index in baseline_order[: args.top_k]
    ]
    profiles = load_profiles(set(shortlisted_ids))

    args.output.mkdir(parents=True, exist_ok=True)
    certificate_dir = args.output / "certificates"
    certificate_dir.mkdir(exist_ok=True)
    certificates = []

    for candidate_id in shortlisted_ids:
        index = index_by_id[candidate_id]
        vector = vectors[index]
        base_score = float(baseline_scores[index])
        base_rank = baseline_rank[candidate_id]
        results = {}
        for test_name, mutated in counterfactuals(vector).items():
            changed_score = score(mutated, weights, mean, scale)
            changed_rank = rank_against_pool(
                candidate_id, changed_score, baseline_scores, candidate_ids
            )
            results[test_name] = {
                "score": round(changed_score, 8),
                "score_delta": round(changed_score - base_score, 8),
                "rank": changed_rank,
                "rank_delta": changed_rank - base_rank,
            }

        scores = stability_scores(base_rank, results)
        certificate = {
            "candidate_id": candidate_id,
            "profile": profiles.get(candidate_id, {}),
            "baseline": {
                "rank": base_rank,
                "score": round(base_score, 8),
                "relevance_tier": records[index]["best_relevance"],
                "best_archetype_id": records[index]["best_archetype_id"],
            },
            "stability_scores": scores,
            "verdict": verdict(scores),
            "counterfactual_results": results,
        }
        certificates.append(certificate)
        (certificate_dir / f"{candidate_id}.json").write_text(
            json.dumps(certificate, indent=2) + "\n", encoding="utf-8"
        )

    with (args.output / "rank_stability_certificates.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for certificate in certificates:
            handle.write(json.dumps(certificate) + "\n")

    csv_path = args.output / "rank_stability_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "candidate_id",
            "baseline_rank",
            "baseline_score",
            "verdict",
            "overall_stability",
            "keyword_independence",
            "skill_list_independence",
            "company_context_independence",
            "project_evidence_reliance",
            "credibility_sensitivity",
            "availability_sensitivity",
            "rank_without_skills",
            "rank_with_keywords_injected",
            "rank_without_project_evidence",
            "rank_with_contradiction",
            "rank_if_unavailable",
        ])
        for certificate in certificates:
            result = certificate["counterfactual_results"]
            stability = certificate["stability_scores"]
            writer.writerow([
                certificate["candidate_id"],
                certificate["baseline"]["rank"],
                certificate["baseline"]["score"],
                certificate["verdict"],
                *[stability[name] for name in [
                    "overall_stability",
                    "keyword_independence",
                    "skill_list_independence",
                    "company_context_independence",
                    "project_evidence_reliance",
                    "credibility_sensitivity",
                    "availability_sensitivity",
                ]],
                result["skills_removed"]["rank"],
                result["perfect_keywords_injected"]["rank"],
                result["all_project_evidence_removed"]["rank"],
                result["contradiction_injected"]["rank"],
                result["made_unavailable"]["rank"],
            ])

    full_pool = aggregate_full_pool_tests(
        vectors, baseline_scores, weights, mean, scale, relevance
    )
    verdict_counts = Counter(certificate["verdict"] for certificate in certificates)
    aggregate = {
        "shortlist_size": len(certificates),
        "full_pool_size": len(records),
        "verdict_counts": dict(verdict_counts),
        "average_scores": {
            name: round(
                float(
                    np.mean(
                        [
                            certificate["stability_scores"][name]
                            for certificate in certificates
                        ]
                    )
                ),
                3,
            )
            for name in certificates[0]["stability_scores"]
        },
        "full_pool_invariance_tests": full_pool,
        "all_required_tests_passed": all(
            test["passed"] for test in full_pool.values()
        ),
        "artifacts": {
            "summary_csv": str(csv_path.resolve()),
            "certificates_jsonl": str(
                (args.output / "rank_stability_certificates.jsonl").resolve()
            ),
            "certificate_directory": str(certificate_dir.resolve()),
        },
    }
    (args.output / "counterfactual_audit_report.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
