#!/usr/bin/env python3
"""Build the Step 1 WorkDNA evidence catalog and compact feature store."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


REFERENCE_DATE = date(2026, 6, 18)

DEFAULT_CANDIDATES = (
    Path(__file__).resolve().parents[2]
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
    / "candidates.jsonl"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "processed"

SERVICE_COMPANIES = {
    "accenture",
    "capgemini",
    "cognizant",
    "hcl",
    "infosys",
    "mindtree",
    "mphasis",
    "tcs",
    "tech mahindra",
    "wipro",
}

PRODUCT_COMPANIES = {
    "cred",
    "flipkart",
    "freshworks",
    "inmobi",
    "meesho",
    "nykaa",
    "ola",
    "razorpay",
    "swiggy",
    "vedantu",
    "zoho",
    "zomato",
}

LOCATION_CITIES = {
    "pune": 1.0,
    "noida": 1.0,
    "delhi": 0.9,
    "gurgaon": 0.9,
    "mumbai": 0.8,
    "hyderabad": 0.8,
    "bangalore": 0.8,
}

EVIDENCE_PATTERNS = {
    "retrieval": (
        r"\binformation retrieval\b",
        r"\bsemantic search\b",
        r"\bvector search\b",
        r"\bhybrid (?:search|retrieval)\b",
        r"\bretrieval\b",
        r"\bbm25\b",
    ),
    "ranking": (
        r"\blearning[- ]to[- ]rank\b",
        r"\branking (?:layer|model|pipeline|system|algorithm)\b",
        r"\bre-?rank",
        r"\brecommendation system\b",
        r"\brecommender system\b",
        r"\bpersonalization\b",
    ),
    "embeddings": (
        r"\bembeddings?\b",
        r"\bsentence[- ]transformers?\b",
        r"\bbge(?:-|\b)",
        r"\bvector recall\b",
    ),
    "vector_infrastructure": (
        r"\bfaiss\b",
        r"\bpinecone\b",
        r"\bweaviate\b",
        r"\bqdrant\b",
        r"\bmilvus\b",
        r"\bpgvector\b",
        r"\belasticsearch\b",
        r"\bopensearch\b",
        r"\bhnsw\b",
    ),
    "evaluation": (
        r"\bndcg\b",
        r"\bmrr\b",
        r"\brecall@",
        r"\bmean average precision\b",
        r"\boffline[- /]online\b",
        r"\ba/b test",
        r"\beval(?:uation)? framework\b",
        r"\bhuman relevance judgments?\b",
    ),
    "production": (
        r"\bproduction\b",
        r"\bdeployed\b",
        r"\bdeployment\b",
        r"\bshipped\b",
        r"\bserving\b",
        r"\breal users\b",
        r"\blive engagement\b",
    ),
    "ownership": (
        r"\bowned\b",
        r"\bled\b",
        r"\bdesigned\b",
        r"\barchitect",
        r"\bdrove\b",
        r"\bfrom scratch\b",
        r"\bend[- ]to[- ]end\b",
    ),
    "scale": (
        r"\b\d+(?:\.\d+)?[mkb]\+?\b",
        r"\bmillions?\b",
        r"\bbillions?\b",
        r"\b\d+\s*(?:queries|users|documents|items|requests)\b",
        r"\bp95\b",
        r"\blow latency\b",
    ),
    "measured_outcome": (
        r"\bimproved\b",
        r"\breduced\b",
        r"\bincreased\b",
        r"\bdropped\b",
        r"\bcut\b",
        r"\b\d+(?:\.\d+)?%\b",
    ),
    "operations": (
        r"\bdrift\b",
        r"\bmonitoring\b",
        r"\brollback\b",
        r"\bindex refresh\b",
        r"\bversioning\b",
        r"\bretraining\b",
        r"\bon-call\b",
        r"\bobser(?:vability|vability)\b",
    ),
    "leadership": (
        r"\bmentored\b",
        r"\bmanaged a team\b",
        r"\bled a team\b",
        r"\bteam of \d+\b",
        r"\bcross-functional\b",
    ),
    "hands_on": (
        r"\bimplemented\b",
        r"\bbuilt\b",
        r"\bwrote\b",
        r"\btrained\b",
        r"\bfine-tuned\b",
        r"\bdeveloped\b",
    ),
    "llm_demo_risk": (
        r"\bchatgpt\b",
        r"\blangchain\b",
        r"\bprompt engineering\b",
        r"\bai-assisted content\b",
    ),
    "non_target_domain": (
        r"\bcomputer vision\b",
        r"\bimage moderation\b",
        r"\bobject detection\b",
        r"\bspeech recognition\b",
        r"\brobotics\b",
    ),
}

COMPILED_PATTERNS = {
    name: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for name, patterns in EVIDENCE_PATTERNS.items()
}


def normalize(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def stable_archetype_id(description: str) -> str:
    digest = hashlib.sha256(normalize(description).encode("utf-8")).hexdigest()
    return f"ARCH_{digest[:12].upper()}"


def matches(text: str, evidence_name: str) -> bool:
    return any(pattern.search(text) for pattern in COMPILED_PATTERNS[evidence_name])


def parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_log1p(value: float) -> float:
    return math.log1p(max(0.0, value))


def location_fit(profile: dict, signals: dict) -> float:
    if normalize(profile.get("country")) != "india":
        return 0.25 if signals.get("willing_to_relocate") else 0.0
    city = normalize(profile.get("location")).split(",", 1)[0]
    base = LOCATION_CITIES.get(city, 0.55)
    if signals.get("willing_to_relocate"):
        base = max(base, 0.85)
    return base


def activity_score(signals: dict) -> float:
    last_active = parse_date(signals.get("last_active_date"))
    if last_active is None:
        return 0.0
    days = max(0, (REFERENCE_DATE - last_active).days)
    recency = math.exp(-days / 120.0)
    open_to_work = 1.0 if signals.get("open_to_work_flag") else 0.0
    response = clamp(float(signals.get("recruiter_response_rate", 0.0)))
    interview = clamp(float(signals.get("interview_completion_rate", 0.0)))
    return round(
        0.35 * recency + 0.25 * open_to_work + 0.25 * response + 0.15 * interview,
        6,
    )


def credibility_flags(candidate: dict) -> dict[str, int]:
    profile = candidate["profile"]
    career = candidate["career_history"]
    skills = candidate.get("skills", [])
    flags = Counter()

    career_months = sum(int(role.get("duration_months", 0)) for role in career)
    stated_months = float(profile.get("years_of_experience", 0.0)) * 12
    if abs(career_months - stated_months) > 36:
        flags["career_total_mismatch"] = 1

    for role in career:
        start = parse_date(role.get("start_date"))
        end = parse_date(role.get("end_date")) or REFERENCE_DATE
        if start and end and start > end:
            flags["career_start_after_end"] = 1
        if start and end:
            calculated = (end.year - start.year) * 12 + end.month - start.month
            if abs(calculated - int(role.get("duration_months", 0))) > 2:
                flags["career_duration_mismatch"] = 1

    expert_zero = sum(
        1
        for skill in skills
        if normalize(skill.get("proficiency")) == "expert"
        and int(skill.get("duration_months", 0)) == 0
    )
    if expert_zero:
        flags["expert_skill_zero_months"] = expert_zero

    return dict(flags)


def preliminary_tier(evidence: dict[str, int]) -> int:
    direct_ir = evidence["retrieval"] or evidence["ranking"]
    production = evidence["production"]
    evaluation = evidence["evaluation"]
    ownership = evidence["ownership"]

    if direct_ir and production and evaluation and ownership:
        return 5
    if direct_ir and production and (evaluation or ownership):
        return 4
    if direct_ir or (
        production and evidence["embeddings"] and evidence["hands_on"]
    ):
        return 3
    if production and evidence["hands_on"]:
        return 2
    if evidence["llm_demo_risk"] or evidence["non_target_domain"]:
        return 1
    return 0


def extract_archetype_evidence(description: str) -> dict[str, int]:
    text = normalize(description)
    return {
        name: int(matches(text, name))
        for name in COMPILED_PATTERNS
    }


@dataclass
class ArchetypeAggregate:
    archetype_id: str
    description: str
    evidence: dict[str, int]
    frequency: int = 0


def iter_candidates(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at line {line_number}: {error}") from error


def build(candidates_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    features_path = output_dir / "candidate_features.jsonl"

    archetypes: dict[str, ArchetypeAggregate] = {}
    seen_candidate_ids: set[str] = set()
    summary = Counter()
    distributions: dict[str, Counter] = defaultdict(Counter)

    with features_path.open("w", encoding="utf-8", newline="\n") as feature_file:
        for candidate in iter_candidates(candidates_path):
            candidate_id = candidate["candidate_id"]
            summary["candidate_count"] += 1
            if candidate_id in seen_candidate_ids:
                summary["duplicate_candidate_ids"] += 1
            seen_candidate_ids.add(candidate_id)

            profile = candidate["profile"]
            signals = candidate["redrob_signals"]
            career = candidate["career_history"]
            companies = {normalize(role.get("company")) for role in career}

            project_ids: list[str] = []
            project_tiers: list[int] = []
            evidence_totals = Counter()

            for role in career:
                description = role["description"].strip()
                archetype_id = stable_archetype_id(description)
                if archetype_id not in archetypes:
                    evidence = extract_archetype_evidence(description)
                    archetypes[archetype_id] = ArchetypeAggregate(
                        archetype_id=archetype_id,
                        description=description,
                        evidence=evidence,
                    )
                archetype = archetypes[archetype_id]
                archetype.frequency += 1
                project_ids.append(archetype_id)
                project_tiers.append(preliminary_tier(archetype.evidence))
                evidence_totals.update(archetype.evidence)

            flags = credibility_flags(candidate)
            contradictions = sum(flags.values())
            services_only = bool(companies) and companies <= SERVICE_COMPANIES
            product_history = bool(companies & PRODUCT_COMPANIES)

            skill_names = {normalize(skill.get("name")) for skill in candidate.get("skills", [])}
            assessment_names = {
                normalize(name)
                for name in signals.get("skill_assessment_scores", {})
            }
            corroborated_skills = len(skill_names & assessment_names)

            feature_record = {
                "candidate_id": candidate_id,
                "project_archetype_ids": project_ids,
                "best_preliminary_project_tier": max(project_tiers, default=0),
                "second_best_preliminary_project_tier": (
                    sorted(project_tiers, reverse=True)[1]
                    if len(project_tiers) > 1
                    else 0
                ),
                "unique_project_archetypes": len(set(project_ids)),
                "project_count": len(project_ids),
                "evidence_counts": dict(evidence_totals),
                "years_of_experience": profile.get("years_of_experience", 0),
                "experience_band_distance": round(
                    max(
                        0.0,
                        5.0 - float(profile.get("years_of_experience", 0.0)),
                        float(profile.get("years_of_experience", 0.0)) - 9.0,
                    ),
                    3,
                ),
                "product_company_history": int(product_history),
                "services_only_history": int(services_only),
                "location_fit": round(location_fit(profile, signals), 6),
                "activity_score": activity_score(signals),
                "open_to_work": int(bool(signals.get("open_to_work_flag"))),
                "recruiter_response_rate": signals.get("recruiter_response_rate", 0),
                "notice_period_days": signals.get("notice_period_days", 0),
                "github_activity_score": signals.get("github_activity_score", -1),
                "saved_by_recruiters_log": round(
                    safe_log1p(signals.get("saved_by_recruiters_30d", 0)), 6
                ),
                "skill_count": len(skill_names),
                "assessment_count": len(assessment_names),
                "corroborated_skill_count": corroborated_skills,
                "credibility_flags": flags,
                "contradiction_count": contradictions,
            }
            feature_file.write(json.dumps(feature_record, ensure_ascii=False) + "\n")

            distributions["best_preliminary_project_tier"][
                str(feature_record["best_preliminary_project_tier"])
            ] += 1
            distributions["project_count"][str(len(project_ids))] += 1
            distributions["contradiction_count"][str(contradictions)] += 1
            if product_history:
                summary["candidates_with_product_history"] += 1
            if services_only:
                summary["services_only_candidates"] += 1
            if contradictions:
                summary["candidates_with_credibility_flags"] += 1

    archetype_fields = [
        "archetype_id",
        "frequency",
        "preliminary_tier",
        *COMPILED_PATTERNS.keys(),
        "description",
    ]
    archetypes_path = output_dir / "project_archetypes.csv"
    with archetypes_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=archetype_fields)
        writer.writeheader()
        for archetype in sorted(
            archetypes.values(), key=lambda item: (-item.frequency, item.archetype_id)
        ):
            writer.writerow(
                {
                    "archetype_id": archetype.archetype_id,
                    "frequency": archetype.frequency,
                    "preliminary_tier": preliminary_tier(archetype.evidence),
                    **archetype.evidence,
                    "description": archetype.description,
                }
            )

    label_fields = [
        "archetype_id",
        "frequency",
        "automatic_tier",
        "human_relevance_tier_0_to_5",
        "production_depth_0_to_5",
        "retrieval_ranking_depth_0_to_5",
        "evaluation_maturity_0_to_5",
        "ownership_0_to_5",
        "transferability_0_to_5",
        "disqualifier",
        "review_notes",
        "description",
    ]
    labels_path = output_dir / "archetype_label_template.csv"
    with labels_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=label_fields)
        writer.writeheader()
        for archetype in sorted(
            archetypes.values(),
            key=lambda item: (
                -preliminary_tier(item.evidence),
                -item.frequency,
                item.archetype_id,
            ),
        ):
            writer.writerow(
                {
                    "archetype_id": archetype.archetype_id,
                    "frequency": archetype.frequency,
                    "automatic_tier": preliminary_tier(archetype.evidence),
                    "human_relevance_tier_0_to_5": "",
                    "production_depth_0_to_5": "",
                    "retrieval_ranking_depth_0_to_5": "",
                    "evaluation_maturity_0_to_5": "",
                    "ownership_0_to_5": "",
                    "transferability_0_to_5": "",
                    "disqualifier": "",
                    "review_notes": "",
                    "description": archetype.description,
                }
            )

    result = {
        "source": str(candidates_path.resolve()),
        "reference_date": REFERENCE_DATE.isoformat(),
        "candidate_count": summary["candidate_count"],
        "unique_candidate_ids": len(seen_candidate_ids),
        "duplicate_candidate_ids": summary["duplicate_candidate_ids"],
        "career_entry_count": sum(item.frequency for item in archetypes.values()),
        "unique_project_archetypes": len(archetypes),
        "candidates_with_product_history": summary["candidates_with_product_history"],
        "services_only_candidates": summary["services_only_candidates"],
        "candidates_with_credibility_flags": summary[
            "candidates_with_credibility_flags"
        ],
        "distributions": {
            name: dict(sorted(values.items(), key=lambda item: item[0]))
            for name, values in distributions.items()
        },
        "artifacts": {
            "project_archetypes": str(archetypes_path.resolve()),
            "archetype_label_template": str(labels_path.resolve()),
            "candidate_features": str(features_path.resolve()),
        },
    }
    summary_path = output_dir / "dataset_summary.json"
    result["artifacts"]["dataset_summary"] = str(summary_path.resolve())
    summary_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build WorkDNA project archetypes and candidate features."
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DEFAULT_CANDIDATES,
        help="Path to candidates.jsonl.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for processed artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.candidates.is_file():
        raise SystemExit(f"Candidate dataset not found: {args.candidates}")
    result = build(args.candidates, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

