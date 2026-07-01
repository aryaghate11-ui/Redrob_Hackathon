import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


BASE = (
    Path(__file__).resolve().parent
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
)
DATA = BASE / "candidates.jsonl"

TOP_N = 30
REFERENCE_DATE = date(2026, 6, 18)


def quantiles(values):
    if not values:
        return {}
    ordered = sorted(values)

    def at(q):
        index = (len(ordered) - 1) * q
        lo = math.floor(index)
        hi = math.ceil(index)
        if lo == hi:
            return ordered[lo]
        return ordered[lo] * (hi - index) + ordered[hi] * (index - lo)

    return {
        "min": ordered[0],
        "p10": at(0.10),
        "p25": at(0.25),
        "median": at(0.50),
        "p75": at(0.75),
        "p90": at(0.90),
        "p95": at(0.95),
        "p99": at(0.99),
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def normalize(value):
    return " ".join(str(value or "").lower().split())


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def main():
    counts = Counter()
    counters = defaultdict(Counter)
    numeric = defaultdict(list)
    booleans = defaultdict(Counter)
    assessment_keys = Counter()
    field_presence = Counter()
    sample_profiles = []
    candidate_ids = set()

    keyword_groups = {
        "retrieval": [
            "retrieval",
            "search",
            "information retrieval",
            "ranking",
            "recommendation",
            "recommender",
            "semantic search",
            "vector search",
        ],
        "embeddings": ["embedding", "sentence transformer", "bge", " e5 "],
        "vector_db": [
            "faiss",
            "pinecone",
            "weaviate",
            "qdrant",
            "milvus",
            "opensearch",
            "elasticsearch",
        ],
        "evaluation": ["ndcg", "mrr", "mean average precision", " a/b ", "ab test"],
        "llm": ["llm", "large language model", "rag", "langchain", "lora", "qlora", "peft"],
        "production": ["production", "deployed", "deployment", "real users", "at scale"],
        "nlp": ["nlp", "natural language processing", "language model"],
        "python": ["python"],
    }
    keyword_hits = Counter()
    impossible = Counter()

    with DATA.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            candidate = json.loads(line)
            counts["records"] += 1
            cid = candidate["candidate_id"]
            if cid in candidate_ids:
                counts["duplicate_candidate_ids"] += 1
            candidate_ids.add(cid)

            for key in candidate:
                field_presence[key] += 1

            profile = candidate["profile"]
            career = candidate["career_history"]
            education = candidate.get("education", [])
            skills = candidate.get("skills", [])
            certs = candidate.get("certifications", [])
            languages = candidate.get("languages", [])
            signals = candidate["redrob_signals"]

            counters["current_title"][normalize(profile["current_title"])] += 1
            counters["current_company"][normalize(profile["current_company"])] += 1
            counters["industry"][normalize(profile["current_industry"])] += 1
            counters["location"][normalize(profile["location"])] += 1
            counters["country"][normalize(profile["country"])] += 1
            counters["company_size"][profile["current_company_size"]] += 1
            counters["education_tier"].update(
                item.get("tier", "missing") for item in education
            )
            counters["preferred_work_mode"][signals["preferred_work_mode"]] += 1
            counters["notice_period_days"][str(signals["notice_period_days"])] += 1
            counters["career_roles_per_candidate"][str(len(career))] += 1
            counters["skills_per_candidate"][str(len(skills))] += 1
            counters["education_per_candidate"][str(len(education))] += 1
            counters["certifications_per_candidate"][str(len(certs))] += 1
            counters["languages_per_candidate"][str(len(languages))] += 1

            numeric["years_of_experience"].append(profile["years_of_experience"])
            numeric["career_duration_months"].append(
                sum(item["duration_months"] for item in career)
            )
            numeric["profile_completeness_score"].append(
                signals["profile_completeness_score"]
            )
            numeric["recruiter_response_rate"].append(
                signals["recruiter_response_rate"]
            )
            numeric["avg_response_time_hours"].append(
                signals["avg_response_time_hours"]
            )
            numeric["github_activity_score"].append(
                signals["github_activity_score"]
            )
            numeric["interview_completion_rate"].append(
                signals["interview_completion_rate"]
            )
            numeric["offer_acceptance_rate"].append(
                signals["offer_acceptance_rate"]
            )
            numeric["profile_views_received_30d"].append(
                signals["profile_views_received_30d"]
            )
            numeric["applications_submitted_30d"].append(
                signals["applications_submitted_30d"]
            )
            numeric["search_appearance_30d"].append(
                signals["search_appearance_30d"]
            )
            numeric["saved_by_recruiters_30d"].append(
                signals["saved_by_recruiters_30d"]
            )
            numeric["notice_period_days"].append(signals["notice_period_days"])
            numeric["salary_min_lpa"].append(
                signals["expected_salary_range_inr_lpa"]["min"]
            )
            numeric["salary_max_lpa"].append(
                signals["expected_salary_range_inr_lpa"]["max"]
            )

            last_active = parse_date(signals["last_active_date"])
            if last_active:
                numeric["days_since_active"].append(
                    (REFERENCE_DATE - last_active).days
                )

            for key in [
                "open_to_work_flag",
                "willing_to_relocate",
                "verified_email",
                "verified_phone",
                "linkedin_connected",
            ]:
                booleans[key][str(signals[key]).lower()] += 1

            for skill in skills:
                skill_name = normalize(skill["name"])
                counters["skill_name"][skill_name] += 1
                counters["skill_proficiency"][skill["proficiency"]] += 1
                numeric["skill_duration_months"].append(
                    skill.get("duration_months", 0)
                )
                if (
                    skill["proficiency"] == "expert"
                    and skill.get("duration_months", 0) == 0
                ):
                    impossible["expert_skill_zero_months"] += 1

            assessment_keys.update(
                normalize(key) for key in signals["skill_assessment_scores"]
            )

            full_text = normalize(
                " ".join(
                    [
                        profile["headline"],
                        profile["summary"],
                        profile["current_title"],
                        profile["current_industry"],
                        *[
                            " ".join(
                                [
                                    item["title"],
                                    item["industry"],
                                    item["description"],
                                ]
                            )
                            for item in career
                        ],
                        *[item["name"] for item in skills],
                    ]
                )
            )
            for group, terms in keyword_groups.items():
                if any(term in f" {full_text} " for term in terms):
                    keyword_hits[group] += 1

            career_months = sum(item["duration_months"] for item in career)
            stated_months = profile["years_of_experience"] * 12
            if abs(career_months - stated_months) > 36:
                impossible["career_vs_stated_gap_over_36m"] += 1

            for item in career:
                start = parse_date(item["start_date"])
                end = parse_date(item["end_date"]) or REFERENCE_DATE
                if start and end and start > end:
                    impossible["career_start_after_end"] += 1
                if start and end:
                    actual = (end.year - start.year) * 12 + end.month - start.month
                    if abs(actual - item["duration_months"]) > 2:
                        impossible["career_duration_date_mismatch_over_2m"] += 1

            if len(sample_profiles) < 3:
                sample_profiles.append(candidate)

    report = {
        "dataset": {
            "path": str(DATA),
            "records": counts["records"],
            "unique_candidate_ids": len(candidate_ids),
            "duplicate_candidate_ids": counts["duplicate_candidate_ids"],
            "top_level_field_presence": dict(field_presence),
        },
        "top_values": {
            name: counter.most_common(TOP_N)
            for name, counter in counters.items()
        },
        "numeric_distributions": {
            name: quantiles(values) for name, values in numeric.items()
        },
        "boolean_distributions": {
            name: dict(counter) for name, counter in booleans.items()
        },
        "assessment_keys": assessment_keys.most_common(TOP_N),
        "keyword_candidate_counts": dict(keyword_hits),
        "integrity_flags": dict(impossible),
        "sample_profiles": sample_profiles,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
