import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
RAW = ROOT.parent / "[PUB] India_runs_data_and_ai_challenge" / "India_runs_data_and_ai_challenge" / "candidates.jsonl"
OUT = ROOT / "reports" / "team_xxx.csv"

sys.path.insert(0, str(APP))
import server  # noqa: E402


def clamp01(value):
    return max(0.0, min(1.0, float(value) / 100.0))


def hard_trap(candidate):
    audit = candidate.get("strict_audit") or candidate.get("stability") or {}
    checks = audit.get("hard_checks", {})
    failed = " | ".join(checks.get("failed_gates", []))
    skill = candidate.get("skill_evidence", {})
    physics = candidate.get("career_physics", {})

    if candidate.get("contradictions", 0) > 0:
        return True, "credibility contradiction"
    if "credibility or disqualifier" in failed:
        return True, "strict audit disqualifier"
    if skill.get("ratio", 0) < 45 and candidate.get("model_scores", {}).get("workdna", 0) < 95:
        return True, "weak skill proof"
    if candidate.get("tier", 0) < 3:
        return True, "low relevance tier"
    if physics.get("current_complexity", 0) < 35 and candidate.get("model_scores", {}).get("skill_evidence", 0) < 80:
        return True, "low current complexity"
    return False, ""


def behavior_score(candidate):
    response = max(0.0, min(1.0, float(candidate.get("response_rate", 0))))
    open_work = 1.0 if candidate.get("open_to_work") else 0.0
    notice = max(0.0, 1.0 - float(candidate.get("notice_days", 180)) / 180.0)
    activity = max(0.0, min(1.0, float(candidate.get("activity_score", 0)) / 100.0))
    return 100.0 * (0.35 * response + 0.25 * open_work + 0.20 * notice + 0.20 * activity)


def ensemble_score(candidate):
    scores = candidate.get("model_scores", {})
    mission = candidate.get("mission", {})
    audit = candidate.get("strict_audit") or candidate.get("stability") or {}
    audit_score = audit.get("stability_scores", {}).get("overall_stability", 0)
    mission_score = (
        0.20 * mission.get("production", 0)
        + 0.25 * mission.get("retrieval", 0)
        + 0.25 * mission.get("evaluation", 0)
        + 0.15 * mission.get("ownership", 0)
        + 0.15 * mission.get("transferability", 0)
    )
    no_production_penalty = 4.0 if (audit.get("hard_checks", {}).get("production_roles", 0) == 0 and scores.get("workdna", 0) < 96) else 0.0
    return (
        0.20 * scores.get("workdna", 0)      # intentionally lower than proof/trajectory
        + 0.30 * scores.get("skill_evidence", 0)
        + 0.23 * scores.get("career_physics", 0)
        + 0.14 * mission_score
        + 0.08 * audit_score
        + 0.05 * behavior_score(candidate)
        - no_production_penalty
    )


def reasoning(candidate):
    scores = candidate.get("model_scores", {})
    skill = candidate.get("skill_evidence", {})
    physics = candidate.get("career_physics", {})
    role = f"{candidate.get('current_title')} at {candidate.get('current_company')}"
    bits = []
    if candidate.get("evidence"):
        ev = candidate["evidence"][0]
        desc = ev.get("description", "")
        if "ranking" in desc.lower() or "search" in desc.lower():
            bits.append("direct search/ranking project evidence")
        elif "rag" in desc.lower() or "retrieval" in desc.lower():
            bits.append("retrieval/RAG delivery evidence")
        elif ev.get("production", 0) >= 4:
            bits.append("production ML/project evidence")
    if skill.get("claimed_count"):
        bits.append(f"{skill.get('supported_count', 0)} of {skill.get('claimed_count', 0)} claimed skills supported")
    if physics.get("velocity_percentile", 0) >= 75:
        bits.append("strong capability velocity")
    elif physics.get("current_complexity", 0) >= 75:
        bits.append("high current project complexity")
    concern = ""
    if candidate.get("notice_days", 0) >= 90:
        concern = f" Notice period is {candidate.get('notice_days')} days."
    elif not candidate.get("open_to_work"):
        concern = " Not currently marked open to work."
    elif candidate.get("response_rate", 1) < 0.35:
        concern = " Recruiter response rate is below average."
    detail = "; ".join(bits[:3]) or candidate.get("reasoning", "Evidence-backed profile fit.")
    return f"{role} with {candidate.get('years')} years; {detail}. Ensemble scores: WorkDNA {scores.get('workdna', 0):.1f}, Skill Evidence {scores.get('skill_evidence', 0):.1f}, Career Physics {scores.get('career_physics', 0):.1f}.{concern}"


def main():
    print("Loading full dataset and model; this can take a few minutes...")
    engine = server.WorkDNAEngine()
    state = engine.load(RAW, "candidates.jsonl")
    rows = []
    dropped = []
    for c in state.candidates:
        is_trap, why = hard_trap(c)
        if is_trap:
            dropped.append((c["candidate_id"], why, c.get("model_scores", {})))
            continue
        rows.append((ensemble_score(c), c))
    rows.sort(key=lambda item: (-item[0], item[1]["candidate_id"]))
    top = rows[:100]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # normalize to 0..1, monotonic, with enough spread but no ties at the top
    max_score = top[0][0]
    min_score = top[-1][0]
    denom = max(max_score - min_score, 1e-9)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (score, c) in enumerate(top, 1):
            normalized = 0.45 + 0.54 * ((score - min_score) / denom)
            # tiny deterministic rank decrement preserves strict monotonicity after rounding
            normalized = max(0.0, min(0.999999, normalized - rank * 1e-6))
            writer.writerow([c["candidate_id"], rank, f"{normalized:.6f}", reasoning(c)])
    print(f"Wrote {OUT}")
    print("Top 10:")
    for rank, (score, c) in enumerate(top[:10], 1):
        print(rank, c["candidate_id"], round(score, 3), c.get("model_scores"), c.get("rankings"))
    print("Dropped candidates due to hard safety gates:", len(dropped))
    print("Dropped from original WorkDNA top100:")
    original_top100 = {c["candidate_id"] for c in state.candidates if c.get("rankings", {}).get("workdna", 999999) <= 100}
    for item in dropped:
        if item[0] in original_top100:
            print(item)


if __name__ == "__main__":
    main()
