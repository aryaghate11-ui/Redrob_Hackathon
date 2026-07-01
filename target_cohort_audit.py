import json
import re
from collections import Counter
from pathlib import Path


BASE = (
    Path(__file__).resolve().parent
    / "[PUB] India_runs_data_and_ai_challenge"
    / "India_runs_data_and_ai_challenge"
)
DATA = BASE / "candidates.jsonl"

SERVICE_COMPANIES = {
    "tcs",
    "infosys",
    "wipro",
    "accenture",
    "cognizant",
    "capgemini",
    "hcl",
    "tech mahindra",
    "mindtree",
    "mphasis",
}
PRODUCT_COMPANIES = {
    "flipkart",
    "swiggy",
    "zomato",
    "razorpay",
    "cred",
    "meesho",
    "inmobi",
    "nykaa",
    "zoho",
    "freshworks",
    "vedantu",
    "ola",
}

PHRASES = {
    "retrieval_core": [
        r"\binformation retrieval\b",
        r"\bsemantic search\b",
        r"\bvector search\b",
        r"\bhybrid (search|retrieval)\b",
        r"\blearning[- ]to[- ]rank\b",
        r"\branking system\b",
        r"\brecommendation system\b",
        r"\brecommender system\b",
    ],
    "retrieval_general": [
        r"\bretrieval\b",
        r"\branking\b",
        r"\brecommendation\b",
        r"\brecommender\b",
        r"\bsearch relevance\b",
    ],
    "embedding": [r"\bembeddings?\b", r"\bsentence[- ]transformers?\b", r"\bbge\b"],
    "vector_db": [
        r"\bfaiss\b",
        r"\bpinecone\b",
        r"\bweaviate\b",
        r"\bqdrant\b",
        r"\bmilvus\b",
        r"\bpgvector\b",
        r"\belasticsearch\b",
        r"\bopensearch\b",
    ],
    "evaluation": [
        r"\bndcg\b",
        r"\bmrr\b",
        r"\bmean average precision\b",
        r"\boffline evaluation\b",
        r"\bonline evaluation\b",
        r"\ba/b test",
        r"\bevaluation framework\b",
    ],
    "production": [
        r"\bproduction\b",
        r"\bdeployed\b",
        r"\bshipped\b",
        r"\breal users\b",
        r"\bat scale\b",
    ],
    "llm_only_risk": [r"\blangchain\b", r"\bprompt engineering\b", r"\bchatgpt\b"],
    "research_risk": [r"\bresearch[- ]only\b", r"\bacademic lab\b", r"\bph\.?d\b"],
}


def norm(value):
    return " ".join(str(value or "").lower().split())


def has_any(text, patterns):
    return any(re.search(pattern, text) for pattern in patterns)


def main():
    summaries = Counter()
    descriptions = Counter()
    headlines = Counter()
    cohort_counts = Counter()
    candidates = []

    with DATA.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            c = json.loads(line)
            p = c["profile"]
            career = c["career_history"]
            signals = c["redrob_signals"]

            summaries[norm(p["summary"])] += 1
            headlines[norm(p["headline"])] += 1
            descriptions.update(norm(role["description"]) for role in career)

            career_text = norm(
                " ".join(
                    f'{r["title"]} {r["industry"]} {r["description"]}' for r in career
                )
            )
            profile_text = norm(
                f'{p["headline"]} {p["summary"]} {p["current_title"]} {p["current_industry"]}'
            )
            skill_text = norm(" ".join(s["name"] for s in c["skills"]))
            evidence_text = f"{profile_text} {career_text}"

            hits = {
                name: has_any(evidence_text, patterns)
                for name, patterns in PHRASES.items()
            }
            skill_hits = {
                name: has_any(skill_text, patterns)
                for name, patterns in PHRASES.items()
            }
            for name, value in hits.items():
                if value:
                    cohort_counts[f"evidence_{name}"] += 1
            for name, value in skill_hits.items():
                if value:
                    cohort_counts[f"skill_{name}"] += 1

            companies = {norm(r["company"]) for r in career}
            product_history = bool(companies & PRODUCT_COMPANIES)
            services_only = bool(companies) and companies <= SERVICE_COMPANIES
            recent_hands_on = any(
                token in career_text
                for token in [
                    "implemented",
                    "built",
                    "designed",
                    "deployed",
                    "shipped",
                    "wrote",
                    "owned",
                ]
            )

            score = 0.0
            score += 8 if hits["retrieval_core"] else 0
            score += 4 if hits["retrieval_general"] else 0
            score += 4 if hits["embedding"] else 0
            score += 3 if hits["vector_db"] else 0
            score += 5 if hits["evaluation"] else 0
            score += 3 if hits["production"] else 0
            score += 3 if product_history else 0
            score += 2 if recent_hands_on else 0
            score += 2 if 4 <= p["years_of_experience"] <= 10 else 0
            score += 1.5 if p["country"].lower() == "india" else -2
            score += 1 if signals["open_to_work_flag"] else 0
            score += min(signals["recruiter_response_rate"], 0.9)
            score += min(signals["github_activity_score"], 80) / 100
            score -= signals["notice_period_days"] / 120
            score -= 4 if services_only else 0
            score -= 2 if hits["research_risk"] and not hits["production"] else 0
            score -= 1.5 if hits["llm_only_risk"] and not hits["retrieval_general"] else 0

            if (
                hits["retrieval_general"]
                or hits["embedding"]
                or hits["evaluation"]
                or "ml engineer" in norm(p["current_title"])
                or "data scientist" in norm(p["current_title"])
                or "ai research engineer" in norm(p["current_title"])
            ):
                cohort_counts["plausible_target_pool"] += 1
                candidates.append(
                    {
                        "candidate_id": c["candidate_id"],
                        "score": round(score, 3),
                        "title": p["current_title"],
                        "company": p["current_company"],
                        "years": p["years_of_experience"],
                        "location": p["location"],
                        "country": p["country"],
                        "career_companies": [r["company"] for r in career],
                        "hits": [name for name, value in hits.items() if value],
                        "skill_only_hits": [
                            name
                            for name, value in skill_hits.items()
                            if value and not hits[name]
                        ],
                        "open_to_work": signals["open_to_work_flag"],
                        "response_rate": signals["recruiter_response_rate"],
                        "notice_days": signals["notice_period_days"],
                        "github": signals["github_activity_score"],
                        "summary": p["summary"],
                        "career": [
                            {
                                "title": r["title"],
                                "company": r["company"],
                                "description": r["description"],
                            }
                            for r in career
                        ],
                    }
                )

    candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    report = {
        "template_reuse": {
            "unique_summaries": len(summaries),
            "unique_headlines": len(headlines),
            "unique_career_descriptions": len(descriptions),
            "top_repeated_summaries": summaries.most_common(10),
            "top_repeated_descriptions": descriptions.most_common(20),
        },
        "cohort_counts": dict(cohort_counts),
        "top_40_heuristic_candidates": candidates[:40],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
