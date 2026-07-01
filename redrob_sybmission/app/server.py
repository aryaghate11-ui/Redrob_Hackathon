#!/usr/bin/env python3
"""WorkDNA offline application server.

Serves the React production build and exposes local-only ranking APIs.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import mimetypes
import os
import sys
import tempfile
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import build_evidence_catalog as evidence  # noqa: E402
import train_pairwise_ranker as ranker  # noqa: E402


DEFAULT_DATASET = (
    ROOT.parent
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
    / "candidates.jsonl"
)
MODEL_PATH = ROOT / "models" / "pairwise_ranker" / "model.json"
LABELS_PATH = ROOT / "data" / "labels" / "reviewed_archetype_labels.csv"
STABILITY_PATH = (
    ROOT / "reports" / "counterfactual" / "rank_stability_certificates.jsonl"
)
WEB_DIST = ROOT / "web" / "dist"
IMPORT_DIR = ROOT / "data" / "imports"


SKILL_ALIASES = {
    "python": ("python", "pytorch", "flask", "fastapi"),
    "information retrieval": ("retrieval", "search relevance", "bm25"),
    "machine learning": ("machine learning", "ml model", "predictive model"),
    "nlp": ("nlp", "natural language", "text classification"),
    "fine-tuning llms": ("fine-tuned", "fine-tuning", "lora", "qlora"),
    "learning to rank": ("learning-to-rank", "ranking model", "re-ranking"),
    "recommendation systems": ("recommendation", "recommender", "personalization"),
    "vector databases": ("faiss", "pinecone", "qdrant", "milvus", "pgvector"),
    "mlops": ("mlflow", "kubeflow", "model monitoring", "feature store"),
}


def skill_evidence_metrics(candidate: dict) -> dict:
    career_text = " ".join(
        f"{role['title']} {role['description']}" for role in candidate["career_history"]
    ).lower()
    assessments = {
        str(name).strip().lower(): float(score)
        for name, score in candidate["redrob_signals"]["skill_assessment_scores"].items()
    }
    supported, unsupported = [], []
    for skill in candidate.get("skills", []):
        name = str(skill["name"]).strip().lower()
        aliases = SKILL_ALIASES.get(name, (name,))
        text_support = any(alias in career_text for alias in aliases)
        assessment = assessments.get(name)
        assessment_support = assessment is not None and assessment >= 50
        duration_support = int(skill.get("duration_months", 0)) >= 12
        endorsement_support = int(skill.get("endorsements", 0)) >= 10
        evidence_points = 2 * int(text_support) + 2 * int(assessment_support) + int(duration_support) + int(endorsement_support)
        detail = {
            "name": skill["name"],
            "supported": evidence_points >= 2,
            "text_support": text_support,
            "assessment_support": assessment_support,
            "duration_months": skill.get("duration_months", 0),
            "endorsements": skill.get("endorsements", 0),
        }
        (supported if detail["supported"] else unsupported).append(detail)
    total = len(supported) + len(unsupported)
    ratio = 100.0 * len(supported) / total if total else 0.0
    return {
        "ratio": round(ratio, 2),
        "supported_count": len(supported),
        "claimed_count": total,
        "supported": supported[:12],
        "unsupported": unsupported[:12],
    }


def role_complexity(role: dict, label: dict) -> float:
    """Fast, explainable project-complexity rubric for the Career Physics MVP."""
    text = role.get("description", "").lower()
    base = (
        0.24 * label["ownership"]
        + 0.22 * label["production_depth"]
        + 0.20 * label["retrieval_ranking_depth"]
        + 0.18 * label["evaluation_maturity"]
        + 0.16 * label["transferability"]
    ) * 16
    scale_bonus = 5 if any(token in text for token in ("million", "users", "requests/sec", "latency", "scale")) else 0
    impact_bonus = 5 if any(token in text for token in ("%", "reduced", "improved", "increased", "revenue", "saved")) else 0
    operations_bonus = 4 if any(token in text for token in ("production", "deployed", "monitoring", "incident", "on-call")) else 0
    return round(min(100.0, base + scale_bonus + impact_bonus + operations_bonus), 2)

def career_physics_raw(candidate: dict, labels: dict[str, dict]) -> dict:
    roles = sorted(candidate["career_history"], key=lambda role: role.get("start_date", ""))
    points = []
    for index, role in enumerate(roles):
        label = labels[role["_archetype_id"]]
        date_text = role.get("start_date", "")
        try:
            midpoint = int(date_text[:4]) + int(date_text[5:7] or 1) / 12
        except (TypeError, ValueError):
            midpoint = float(index)
        points.append({
            "label": f"{role['title']} at {role['company']}",
            "date": role.get("start_date"),
            "complexity": role_complexity(role, label),
            "time": midpoint,
        })
    complexities = np.array([point["complexity"] for point in points])
    times = np.array([point["time"] for point in points])
    if len(points) >= 2:
        centered_time = times - times.mean()
        denominator = float(np.dot(centered_time, centered_time))
        velocity = float(np.dot(centered_time, complexities - complexities.mean()) / denominator) if denominator else 0.0
    else:
        velocity = 0.0
    if len(points) >= 3:
        acceleration = float((complexities[-1] - complexities[-2]) - (complexities[-2] - complexities[-3]))
    elif len(points) == 2:
        acceleration = float(complexities[-1] - complexities[-2])
    else:
        acceleration = 0.0
    recovery = 0.0
    for index in range(1, len(complexities) - 1):
        if complexities[index] < complexities[index - 1]:
            recovery = max(recovery, float(complexities[-1] - complexities[index]))

    first_year = int(np.floor(times.min()))
    last_year = int(np.floor(times.max()))
    historical_years = np.arange(first_year, last_year + 1, dtype=float)
    if len(points) >= 2 and last_year > first_year:
        historical_values = np.interp(historical_years, times, complexities)
    else:
        historical_years = np.array([float(last_year)])
        historical_values = np.array([float(complexities[-1])])
    historical = [
        {"year": int(year), "complexity": round(float(value), 1)}
        for year, value in zip(historical_years, historical_values)
    ]

    # Five-year bounded scenario projection. This is not a promotion prediction.
    recent_velocity = velocity
    if len(points) >= 3:
        recent_times = times[-3:]
        centered_recent = recent_times - recent_times.mean()
        recent_denominator = float(np.dot(centered_recent, centered_recent))
        if recent_denominator:
            recent_velocity = float(np.dot(centered_recent, complexities[-3:] - complexities[-3:].mean()) / recent_denominator)
    blended_velocity = float(np.clip(0.55 * recent_velocity + 0.45 * velocity, -6.0, 6.0))
    bounded_acceleration = float(np.clip(acceleration / max(len(points), 1), -1.0, 1.0))
    residual = float(np.std(complexities - (complexities.mean() + velocity * (times - times.mean())))) if len(points) >= 3 else 8.0
    evidence_uncertainty = 5.0 + min(12.0, residual) + (8.0 if len(points) < 3 else 0.0)
    forecast = []
    current_level = float(complexities[-1])
    unconstrained_target = current_level + 3.0 * blended_velocity + 0.8 * bounded_acceleration
    personalized_target = float(np.clip(unconstrained_target, current_level - 12.0, current_level + 12.0))
    personalized_target = float(np.clip(personalized_target, 20.0, 98.0))
    for horizon in range(1, 6):
        convergence = 1.0 - np.exp(-horizon / 2.2)
        projected = current_level + (personalized_target - current_level) * convergence
        uncertainty = min(28.0, evidence_uncertainty * (0.65 + 0.28 * horizon))
        forecast.append({
            "year": last_year + horizon,
            "complexity": round(float(np.clip(projected, 0.0, 100.0)), 1),
            "low": round(max(0.0, projected - uncertainty), 1),
            "high": round(min(100.0, projected + uncertainty), 1),
        })
    confidence = round(max(20.0, min(90.0, 82.0 - evidence_uncertainty * 2.0 + min(len(points), 5) * 3.0)), 1)
    return {
        "points": points,
        "historical": historical,
        "forecast": forecast,
        "forecast_confidence": confidence,
        "forecast_method": "bounded cohort-relative trajectory projection",
        "current_complexity": float(complexities[-1]),
        "peak_complexity": float(complexities.max()),
        "velocity": round(velocity, 4),
        "acceleration": round(acceleration, 4),
        "recovery": round(recovery, 4),
    }

def percentile(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    result = np.empty(len(values), dtype=float)
    result[order] = np.linspace(0, 100, len(values))
    return result

def strict_evidence_audit(
    candidate: dict,
    project: dict,
    skill_evidence: dict,
    project_reliance: float,
    context_independence: float,
) -> dict:
    """Candidate-level audit. High scores require every independent proof gate."""
    relevant_roles = []
    quantified = production = ownership = 0
    relevant_archetypes = set()
    for role in candidate["career_history"]:
        label = project["labels_by_id"][role["_archetype_id"]]
        if label["relevance_tier"] < 3:
            continue
        relevant_roles.append(role)
        relevant_archetypes.add(role["_archetype_id"])
        text = role.get("description", "").lower()
        quantified += int(any(character.isdigit() for character in text) or any(token in text for token in ("%", "revenue", "saved", "latency")))
        production += int(any(token in text for token in ("production", "deployed", "shipped", "monitoring", "on-call")))
        ownership += int(any(token in text for token in ("led", "owned", "architected", "designed", "drove")))

    role_count = len(relevant_roles)
    breadth = min(100.0, 24.0 * role_count + 10.0 * len(relevant_archetypes))
    if role_count:
        specificity = 100.0 * (quantified + production + ownership) / (3.0 * role_count)
    else:
        specificity = 0.0
    contradictions = sum(evidence.credibility_flags(candidate).values())
    disqualifiers = int(project.get("disqualifier_count", 0))
    credibility = max(0.0, 100.0 - 38.0 * contradictions - 28.0 * disqualifiers)
    skill_proof = float(skill_evidence["ratio"])

    components = {
        "skill_proof": skill_proof,
        "project_breadth": breadth,
        "narrative_specificity": specificity,
        "project_reliance": float(project_reliance),
        "context_independence": float(context_independence),
        "credibility": credibility,
    }
    weights = {
        "skill_proof": 0.22,
        "project_breadth": 0.20,
        "narrative_specificity": 0.18,
        "project_reliance": 0.18,
        "context_independence": 0.10,
        "credibility": 0.12,
    }
    score = 100.0
    for name, weight in weights.items():
        score *= max(components[name], 1.0) ** weight / (100.0 ** weight)

    failed_gates = []
    if role_count < 2:
        score = min(score, 69.0)
        failed_gates.append("fewer than two relevant career proofs")
    if skill_proof < 70:
        score = min(score, 74.0)
        failed_gates.append("less than 70% of claimed skills are supported")
    if specificity < 50:
        score = min(score, 72.0)
        failed_gates.append("career evidence lacks quantified production and ownership detail")
    if production == 0:
        score = min(score, 68.0)
        failed_gates.append("no explicit shipped or production evidence")
    if contradictions or disqualifiers:
        score = min(score, 64.0)
        failed_gates.append("credibility or disqualifier flag present")

    score = round(max(0.0, min(99.0, score)), 1)
    if score >= 85:
        verdict = "strongly_verified"
    elif score >= 70:
        verdict = "credible_with_gaps"
    elif score >= 50:
        verdict = "manual_review_required"
    else:
        verdict = "fragile_evidence"
    return {
        "stability_scores": {
            "overall_stability": score,
            **{name: round(value, 1) for name, value in components.items()},
        },
        "verdict": verdict,
        "hard_checks": {
            "relevant_roles": role_count,
            "distinct_relevant_projects": len(relevant_archetypes),
            "quantified_roles": quantified,
            "production_roles": production,
            "ownership_roles": ownership,
            "failed_gates": failed_gates,
        },
    }

def normalize_score(scores: np.ndarray) -> np.ndarray:
    if len(scores) == 0:
        return scores
    low, high = float(scores.min()), float(scores.max())
    if high - low < 1e-12:
        return np.full_like(scores, 50.0)
    return 100.0 * (scores - low) / (high - low)


def reasoning(candidate: dict, feature: dict, project_label: dict) -> str:
    profile = candidate["profile"]
    career = candidate["career_history"]
    signals = candidate["redrob_signals"]
    strongest = max(
        career,
        key=lambda role: (
            len(role.get("description", "")),
            int(role.get("duration_months", 0)),
        ),
    )
    strengths = []
    if project_label["retrieval_ranking_depth"] >= 4:
        strengths.append("direct retrieval/ranking delivery")
    if project_label["evaluation_maturity"] >= 4:
        strengths.append("strong evaluation ownership")
    if project_label["production_depth"] >= 4:
        strengths.append("production ML depth")
    if not strengths:
        strengths.append("transferable engineering experience")

    concern = ""
    if signals["notice_period_days"] >= 90:
        concern = f" Notice period is {signals['notice_period_days']} days."
    elif not signals["open_to_work_flag"]:
        concern = " They are not currently marked open to work."
    elif signals["recruiter_response_rate"] < 0.35:
        concern = " Recruiter response behavior is below average."

    return (
        f"{profile['current_title']} with {profile['years_of_experience']:.1f} years; "
        f"{', '.join(strengths)}. Their work at {strongest['company']} shows "
        f"{strongest['title'].lower()} responsibility aligned to the role."
        f"{concern}"
    )


def public_candidate(
    candidate: dict,
    feature_record: dict,
    model_score: float,
    normalized: float,
    rank: int,
    project: dict,
    stability: dict | None,
) -> dict:
    profile = candidate["profile"]
    signals = candidate["redrob_signals"]
    best_label = project["best_label"]
    evidence_items = []
    for role in candidate["career_history"]:
        label = project["labels_by_id"][role["_archetype_id"]]
        if label["relevance_tier"] >= 3:
            evidence_items.append(
                {
                    "company": role["company"],
                    "title": role["title"],
                    "description": role["description"],
                    "tier": label["relevance_tier"],
                    "production": label["production_depth"],
                    "retrieval": label["retrieval_ranking_depth"],
                    "evaluation": label["evaluation_maturity"],
                    "ownership": label["ownership"],
                }
            )
    evidence_items.sort(
        key=lambda item: (
            item["tier"],
            item["retrieval"],
            item["production"],
        ),
        reverse=True,
    )

    return {
        "candidate_id": candidate["candidate_id"],
        "rank": rank,
        "score": round(float(normalized), 2),
        "raw_score": round(float(model_score), 6),
        "tier": project["best_relevance"],
        "best_archetype_id": project["best_archetype_id"],
        "name": profile["anonymized_name"],
        "headline": profile["headline"],
        "summary": profile["summary"],
        "current_title": profile["current_title"],
        "current_company": profile["current_company"],
        "years": profile["years_of_experience"],
        "location": profile["location"],
        "country": profile["country"],
        "open_to_work": signals["open_to_work_flag"],
        "notice_days": signals["notice_period_days"],
        "response_rate": signals["recruiter_response_rate"],
        "last_active_date": signals["last_active_date"],
        "github_score": signals["github_activity_score"],
        "activity_score": round(feature_record["activity_score"] * 100, 1),
        "contradictions": feature_record["contradiction_count"],
        "mission": {
            "production": best_label["production_depth"] * 20,
            "retrieval": best_label["retrieval_ranking_depth"] * 20,
            "evaluation": best_label["evaluation_maturity"] * 20,
            "ownership": best_label["ownership"] * 20,
            "transferability": best_label["transferability"] * 20,
        },
        "evidence": evidence_items[:5],
        "skills": candidate.get("skills", [])[:15],
        "career_history": [
            {key: value for key, value in role.items() if key != "_archetype_id"}
            for role in candidate["career_history"]
        ],
        "reasoning": reasoning(candidate, feature_record, best_label),
        "stability": stability,
    }


@dataclass
class DatasetState:
    name: str
    path: Path
    imported: bool
    loaded_at: float
    candidates: list[dict]
    summary: dict
    benchmark: dict


class WorkDNAEngine:
    def __init__(self) -> None:
        model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.weights = np.array(model["weights"])
        self.mean = np.array(model["mean"])
        self.scale = np.array(model["scale"])
        self.labels = ranker.load_labels(LABELS_PATH)
        self.stability = self._load_stability()
        self.lock = threading.Lock()
        self.state: DatasetState | None = None

    @staticmethod
    def _load_stability() -> dict[str, dict]:
        if not STABILITY_PATH.exists():
            return {}
        records = {}
        with STABILITY_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                certificate = json.loads(line)
                records[certificate["candidate_id"]] = certificate
        return records

    def load(self, path: Path, name: str, imported: bool = False) -> DatasetState:
        started = time.perf_counter()
        raw_candidates = []
        feature_records = []
        vectors = []
        supplemental = []

        for candidate in evidence.iter_candidates(path):
            career = candidate.get("career_history", [])
            if not career:
                continue
            project_ids = []
            for role in career:
                archetype_id = evidence.stable_archetype_id(role["description"])
                role["_archetype_id"] = archetype_id
                project_ids.append(archetype_id)
            unknown = [project_id for project_id in project_ids if project_id not in self.labels]
            if unknown:
                # Unknown projects receive a conservative adjacent-engineering label.
                for project_id in unknown:
                    self.labels[project_id] = {
                        "relevance_tier": 1,
                        "production_depth": 2,
                        "retrieval_ranking_depth": 0,
                        "evaluation_maturity": 1,
                        "ownership": 2,
                        "transferability": 2,
                        "disqualifier": 0,
                    }

            profile = candidate["profile"]
            signals = candidate["redrob_signals"]
            companies = {evidence.normalize(role["company"]) for role in career}
            flags = evidence.credibility_flags(candidate)
            skill_names = {
                evidence.normalize(skill.get("name"))
                for skill in candidate.get("skills", [])
            }
            assessment_names = {
                evidence.normalize(skill)
                for skill in signals.get("skill_assessment_scores", {})
            }
            feature_record = {
                "candidate_id": candidate["candidate_id"],
                "project_archetype_ids": project_ids,
                "unique_project_archetypes": len(set(project_ids)),
                "years_of_experience": profile["years_of_experience"],
                "product_company_history": int(
                    bool(companies & evidence.PRODUCT_COMPANIES)
                ),
                "services_only_history": int(
                    bool(companies) and companies <= evidence.SERVICE_COMPANIES
                ),
                "location_fit": evidence.location_fit(profile, signals),
                "activity_score": evidence.activity_score(signals),
                "open_to_work": int(signals["open_to_work_flag"]),
                "recruiter_response_rate": signals["recruiter_response_rate"],
                "notice_period_days": signals["notice_period_days"],
                "github_activity_score": signals["github_activity_score"],
                "saved_by_recruiters_log": round(
                    evidence.safe_log1p(signals["saved_by_recruiters_30d"]), 6
                ),
                "skill_count": len(skill_names),
                "corroborated_skill_count": len(skill_names & assessment_names),
                "contradiction_count": sum(flags.values()),
            }
            vector, project = ranker.feature_vector(feature_record, self.labels)
            project["labels_by_id"] = self.labels
            project["best_label"] = self.labels[project["best_archetype_id"]]
            raw_candidates.append(candidate)
            feature_records.append((feature_record, project))
            vectors.append(vector)
            supplemental.append({
                "skill_evidence": skill_evidence_metrics(candidate),
                "career_physics": career_physics_raw(candidate, self.labels),
            })

        if not vectors:
            raise ValueError("No valid candidate records were found.")

        matrix = np.vstack(vectors)
        scores = ((matrix - self.mean) / self.scale) @ self.weights
        normalized = normalize_score(scores)
        project_removed = matrix.copy()
        project_removed[:, :10] = 0.0
        project_removed_scores = ((project_removed - self.mean) / self.scale) @ self.weights
        project_reliance_pct = percentile(np.maximum(0.0, scores - project_removed_scores))
        context_removed = matrix.copy()
        context_removed[:, 10:21] = 0.0
        context_removed_scores = ((context_removed - self.mean) / self.scale) @ self.weights
        context_dependence_pct = percentile(np.abs(scores - context_removed_scores))
        context_independence_pct = 100.0 - context_dependence_pct
        skill_ratios = np.array([item["skill_evidence"]["ratio"] for item in supplemental])
        skill_scores = 0.65 * skill_ratios + 0.35 * normalized
        velocity_pct = percentile(np.array([item["career_physics"]["velocity"] for item in supplemental]))
        acceleration_pct = percentile(np.array([item["career_physics"]["acceleration"] for item in supplemental]))
        recovery_pct = percentile(np.array([item["career_physics"]["recovery"] for item in supplemental]))
        current_complexity = np.array([item["career_physics"]["current_complexity"] for item in supplemental])
        physics_scores = 0.35 * current_complexity + 0.35 * velocity_pct + 0.20 * acceleration_pct + 0.10 * recovery_pct
        workdna_rank = np.empty(len(scores), dtype=int)
        skill_rank = np.empty(len(scores), dtype=int)
        physics_rank = np.empty(len(scores), dtype=int)
        for ranking, values in [(workdna_rank, scores), (skill_rank, skill_scores), (physics_rank, physics_scores)]:
            ranking[np.argsort(-values, kind="stable")] = np.arange(1, len(values) + 1)
        for index, item in enumerate(supplemental):
            item["skill_evidence"].update({"score": round(float(skill_scores[index]), 2), "rank": int(skill_rank[index])})
            item["career_physics"].update({
                "score": round(float(physics_scores[index]), 2),
                "rank": int(physics_rank[index]),
                "velocity_percentile": round(float(velocity_pct[index]), 2),
                "acceleration_percentile": round(float(acceleration_pct[index]), 2),
                "recovery_percentile": round(float(recovery_pct[index]), 2),
            })
        for index, item in enumerate(supplemental):
            item["strict_audit"] = strict_evidence_audit(
                raw_candidates[index],
                feature_records[index][1],
                item["skill_evidence"],
                project_reliance_pct[index],
                context_independence_pct[index],
            )
        order = sorted(
            range(len(raw_candidates)),
            key=lambda index: (
                -scores[index],
                raw_candidates[index]["candidate_id"],
            ),
        )
        public = []
        for rank_value, index in enumerate(order, 1):
            candidate_id = raw_candidates[index]["candidate_id"]
            item = public_candidate(
                raw_candidates[index],
                feature_records[index][0],
                scores[index],
                normalized[index],
                rank_value,
                feature_records[index][1],
                self.stability.get(candidate_id),
            )
            item["rankings"] = {
                "workdna": int(workdna_rank[index]),
                "skill_evidence": int(skill_rank[index]),
                "career_physics": int(physics_rank[index]),
            }
            item["model_scores"] = {
                "workdna": round(float(normalized[index]), 2),
                "skill_evidence": round(float(skill_scores[index]), 2),
                "career_physics": round(float(physics_scores[index]), 2),
            }
            item.update(supplemental[index])
            item["legacy_stability"] = item.get("stability")
            item["stability"] = supplemental[index]["strict_audit"]
            public.append(item)

        tier_counts = {}
        for item in public:
            tier_counts[str(item["tier"])] = tier_counts.get(str(item["tier"]), 0) + 1
        audit_scores = np.array([item["stability"]["stability_scores"]["overall_stability"] for item in public])
        summary = {
            "candidate_count": len(public),
            "strict_audit_distribution": {
                "median": round(float(np.median(audit_scores)), 1),
                "p90": round(float(np.percentile(audit_scores, 90)), 1),
                "maximum": round(float(audit_scores.max()), 1),
                "scores_90_plus": int(np.sum(audit_scores >= 90)),
                "scores_80_plus": int(np.sum(audit_scores >= 80)),
                "scores_below_70": int(np.sum(audit_scores < 70)),
            },
            "tier_counts": tier_counts,
            "open_to_work_count": sum(item["open_to_work"] for item in public),
            "contradiction_count": sum(item["contradictions"] > 0 for item in public),
            "processing_seconds": round(time.perf_counter() - started, 3),
            "model": "WorkDNA Pairwise Ranker",
            "offline": True,
        }
        mission_names = ["production", "retrieval", "evaluation", "ownership", "transferability"]
        benchmark = {
            "population_size": len(public),
            "workdna": {
                name: round(float(np.median([item["mission"][name] for item in public])), 1)
                for name in mission_names
            },
            "career": {
                "current_complexity": round(float(np.median([item["career_physics"]["current_complexity"] for item in public])), 1),
                "velocity": round(float(np.median([item["career_physics"]["velocity"] for item in public])), 2),
                "acceleration": round(float(np.median([item["career_physics"]["acceleration"] for item in public])), 2),
                "recovery": round(float(np.median([item["career_physics"]["recovery"] for item in public])), 1),
                "forecast": [
                    round(float(np.median([item["career_physics"]["forecast"][horizon]["complexity"] for item in public])), 1)
                    for horizon in range(5)
                ],
            },
        }
        state = DatasetState(name, path, imported, time.time(), public, summary, benchmark)
        with self.lock:
            self.state = state
        return state

    def ensure_loaded(self) -> DatasetState:
        with self.lock:
            state = self.state
        if state is None:
            return self.load(DEFAULT_DATASET, "Redrob challenge dataset")
        return state


ENGINE = WorkDNAEngine()


class Handler(BaseHTTPRequestHandler):
    server_version = "WorkDNA/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[WorkDNA] {self.address_string()} - {fmt % args}")

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        self.serve_static(parsed.path)

    def handle_api_get(self, parsed: urllib.parse.ParseResult) -> None:
        state = ENGINE.ensure_loaded()
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/status":
            self.send_json(
                {
                    "dataset": {
                        "name": state.name,
                        "path": str(state.path),
                        "imported": state.imported,
                    },
                    "summary": state.summary,
                }
            )
            return
        if parsed.path == "/api/candidates":
            search = query.get("search", [""])[0].strip().lower()
            tier = query.get("tier", ["all"])[0]
            availability = query.get("availability", ["all"])[0]
            model = query.get("model", ["workdna"])[0]
            limit = min(int(query.get("limit", ["100"])[0]), 500)
            filtered = sorted(state.candidates, key=lambda item: item["rankings"].get(model, item["rank"]))
            if search:
                filtered = [
                    item
                    for item in filtered
                    if search
                    in " ".join(
                        [
                            item["candidate_id"],
                            item["name"],
                            item["current_title"],
                            item["current_company"],
                            item["location"],
                            item["headline"],
                        ]
                    ).lower()
                ]
            if tier != "all":
                filtered = [item for item in filtered if item["tier"] == int(tier)]
            if availability == "open":
                filtered = [item for item in filtered if item["open_to_work"]]
            elif availability == "fast":
                filtered = [item for item in filtered if item["notice_days"] <= 30]
            self.send_json(
                {
                    "total": len(filtered),
                    "items": filtered[:limit],
                    "benchmark": state.benchmark,
                }
            )
            return
        if parsed.path.startswith("/api/candidates/"):
            candidate_id = parsed.path.rsplit("/", 1)[-1]
            item = next(
                (
                    candidate
                    for candidate in state.candidates
                    if candidate["candidate_id"] == candidate_id
                ),
                None,
            )
            if item is None:
                self.send_json({"error": "Candidate not found"}, 404)
            else:
                self.send_json(item)
            return
        if parsed.path == "/api/export":
            top_k = min(int(query.get("top_k", ["100"])[0]), len(state.candidates))
            model = query.get("model", ["workdna"])[0]
            ranked = sorted(state.candidates, key=lambda item: item["rankings"].get(model, item["rank"]))
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["candidate_id", "rank", "score", "reasoning"])
            for item in ranked[:top_k]:
                writer.writerow(
                    [
                        item["candidate_id"],
                        item["rankings"].get(model, item["rank"]),
                        f"{item['model_scores'].get(model, item['score']) / 100:.6f}",
                        item["reasoning"],
                    ]
                )
            body = buffer.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="workdna_shortlist.csv"',
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json({"error": "Unknown endpoint"}, 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/import":
            self.send_json({"error": "Unknown endpoint"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("The uploaded file is empty.")
            if length > 600_000_000:
                raise ValueError("Dataset exceeds the 600 MB offline limit.")
            query = urllib.parse.parse_qs(parsed.query)
            filename = Path(query.get("filename", ["candidates.jsonl"])[0]).name
            suffix = Path(filename).suffix.lower()
            if suffix not in {".jsonl", ".json"}:
                raise ValueError("Upload a .jsonl or .json candidate dataset.")
            IMPORT_DIR.mkdir(parents=True, exist_ok=True)
            destination = IMPORT_DIR / f"{int(time.time())}_{filename}"
            with destination.open("wb") as handle:
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    handle.write(chunk)
                    remaining -= len(chunk)
            if suffix == ".json":
                data = json.loads(destination.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    raise ValueError("JSON imports must contain a candidate array.")
                converted = destination.with_suffix(".jsonl")
                with converted.open("w", encoding="utf-8") as handle:
                    for item in data:
                        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
                destination = converted
            state = ENGINE.load(destination, filename, imported=True)
            self.send_json({"ok": True, "summary": state.summary})
        except Exception as error:
            self.send_json({"error": str(error)}, 400)

    def serve_static(self, request_path: str) -> None:
        if not WEB_DIST.exists():
            self.send_json(
                {
                    "error": "Frontend build not found.",
                    "hint": "Run npm install and npm run build inside ML Project/web.",
                },
                503,
            )
            return
        relative = request_path.lstrip("/") or "index.html"
        target = (WEB_DIST / relative).resolve()
        if WEB_DIST.resolve() not in target.parents and target != WEB_DIST.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            target = WEB_DIST / "index.html"
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()

    ENGINE.load(args.dataset, args.dataset.name)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"WorkDNA is running offline at http://{args.host}:{args.port}")
    print(f"Dataset: {ENGINE.state.name} ({ENGINE.state.summary['candidate_count']:,} candidates)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping WorkDNA.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

