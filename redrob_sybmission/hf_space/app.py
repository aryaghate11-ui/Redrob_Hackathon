import csv
import io
import json
import math
import os
import re
import tempfile
from datetime import datetime

import gradio as gr
import pandas as pd


DEFAULT_JD = """Build an AI system that ranks candidates the way a great recruiter would.
The role needs strong AI/ML judgment, retrieval/search understanding, evaluation rigor,
production engineering, ownership, and the ability to turn ambiguous hiring signals into
a trustworthy shortlist. The system should avoid keyword stuffing and prefer candidates
whose projects prove the claimed skills."""


MISSION_KEYWORDS = {
    "production": [
        "production", "deployed", "shipped", "serving", "latency", "sla",
        "monitoring", "observability", "on-call", "reliability", "api", "backend"
    ],
    "retrieval": [
        "retrieval", "search", "ranking", "recommendation", "vector", "embedding",
        "semantic", "rerank", "rag", "milvus", "faiss", "elasticsearch"
    ],
    "evaluation": [
        "evaluation", "eval", "benchmark", "ab test", "a/b", "metrics",
        "quality", "precision", "recall", "accuracy", "validation", "test"
    ],
    "ownership": [
        "owned", "led", "architected", "designed", "drove", "launched",
        "built", "managed", "responsible", "end-to-end", "0 to 1"
    ],
    "transferability": [
        "cross-functional", "stakeholder", "ambiguous", "undefined", "research",
        "platform", "collaborated", "business", "impact", "customer"
    ],
}

OWNERSHIP_WORDS = re.compile(r"\b(owned|led|architected|designed|drove|launched|built|managed|end-to-end|0 to 1)\b", re.I)
ASSIST_WORDS = re.compile(r"\b(assisted|supported|helped|contributed|shadowed)\b", re.I)
PRODUCTION_WORDS = re.compile(r"\b(production|deployed|shipped|serving|launched|on-call|sla|monitoring|observability)\b", re.I)
AMBIGUITY_WORDS = re.compile(r"\b(ambiguous|undefined|0 to 1|research|greenfield|new product|from scratch)\b", re.I)
IMPACT_NUMBERS = re.compile(r"(\$[\d,.]+|[\d,.]+\s?(%|percent|users|requests|req/sec|gb|tb|million|m|k|hours|days))", re.I)


def text_blob(candidate):
    parts = []
    profile = candidate.get("profile") or {}
    for key in ("headline", "summary", "current_title", "current_industry"):
        if profile.get(key):
            parts.append(str(profile[key]))
    for role in candidate.get("career_history") or []:
        for key in ("title", "industry", "description"):
            if role.get(key):
                parts.append(str(role[key]))
    for project in candidate.get("projects") or []:
        if isinstance(project, dict):
            parts.extend(str(v) for v in project.values() if v)
        else:
            parts.append(str(project))
    return "\n".join(parts).lower()


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10])
    except Exception:
        return None


def analyze_jd(jd):
    jd_l = (jd or "").lower()
    weights = {}
    total = 0.0
    for name, words in MISSION_KEYWORDS.items():
        raw = sum(1 for w in words if w in jd_l)
        # keep all signals alive; boost what the JD explicitly asks for
        weight = 1.0 + raw
        weights[name] = weight
        total += weight
    return {k: round(v / total, 3) for k, v in weights.items()}


def mission_fit(candidate, jd_weights):
    blob = text_blob(candidate)
    scores = {}
    for name, words in MISSION_KEYWORDS.items():
        hits = sum(1 for w in words if w in blob)
        scores[name] = clamp((hits / max(3, len(words) * 0.55)) * 100)
    weighted = sum(scores[k] * jd_weights.get(k, 0.2) for k in scores)
    return weighted, scores


def skill_evidence(candidate):
    skills = candidate.get("skills") or []
    blob = text_blob(candidate)
    if not skills:
        return 0.0, 0, 0
    supported = 0
    for skill in skills:
        if isinstance(skill, dict):
            name = str(skill.get("name", "")).strip()
            months = float(skill.get("duration_months") or 0)
            endorsements = float(skill.get("endorsements") or 0)
            proficiency = str(skill.get("proficiency") or "").lower()
        else:
            name, months, endorsements, proficiency = str(skill), 0, 0, ""
        token = re.escape(name.lower())
        direct_text = bool(name and re.search(rf"\b{token}\b", blob))
        credible_duration = months >= 12 and proficiency in {"intermediate", "advanced", "expert"}
        social_proof = endorsements >= 8 and months >= 6
        if direct_text or credible_duration or social_proof:
            supported += 1
    ratio = supported / max(1, len(skills))
    # Small penalty for very huge skill lists: keyword stuffing should not win.
    stuffing_penalty = max(0, len(skills) - 18) * 1.4
    return clamp(ratio * 100 - stuffing_penalty), supported, len(skills)


def role_complexity(role):
    desc = str(role.get("description") or "")
    title = str(role.get("title") or "")
    text = f"{title} {desc}"
    ownership = 24 if OWNERSHIP_WORDS.search(text) else 10
    if ASSIST_WORDS.search(text) and not OWNERSHIP_WORDS.search(text):
        ownership -= 5
    ambiguity = 14 if AMBIGUITY_WORDS.search(text) else 4
    production = 22 if PRODUCTION_WORDS.search(text) else 5
    impact = min(18, 4 * len(IMPACT_NUMBERS.findall(text)))
    scale = 0
    numbers = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
    if numbers:
        largest = max(float(n) for n in numbers)
        scale = min(18, math.log10(largest + 1) * 5)
    return clamp(ownership + ambiguity + production + impact + scale)


def career_physics(candidate):
    roles = candidate.get("career_history") or []
    points = []
    for idx, role in enumerate(roles):
        start = parse_date(role.get("start_date"))
        year = start.year if start else 2020 + idx
        points.append((year, role_complexity(role), str(role.get("title") or "Role")))
    if not points:
        return 0.0, 0.0, 0.0, 0.0, []
    points.sort(key=lambda x: x[0])
    current = points[-1][1]
    if len(points) == 1:
        velocity = 0
    else:
        years = [p[0] for p in points]
        values = [p[1] for p in points]
        xbar = sum(years) / len(years)
        ybar = sum(values) / len(values)
        denom = sum((x - xbar) ** 2 for x in years) or 1
        velocity = sum((x - xbar) * (y - ybar) for x, y in zip(years, values)) / denom
    dips = []
    values = [p[1] for p in points]
    for i in range(1, len(values)):
        if values[i] < values[i - 1] - 8:
            recovery = values[i + 1] - values[i] if i + 1 < len(values) else 0
            dips.append(recovery)
    resilience = clamp(50 + (max(dips) if dips else 8) * 2)
    velocity_score = clamp(50 + velocity * 6)
    physics = clamp(0.45 * current + 0.35 * velocity_score + 0.20 * resilience)
    return physics, current, velocity_score, resilience, points


def credibility_audit(candidate):
    flags = []
    profile = candidate.get("profile") or {}
    years = float(profile.get("years_of_experience") or 0)
    total_months = sum(float((r or {}).get("duration_months") or 0) for r in candidate.get("career_history") or [])
    if total_months and years and abs((total_months / 12) - years) > 2.5:
        flags.append("experience mismatch")
    for role in candidate.get("career_history") or []:
        start = parse_date(role.get("start_date"))
        end = parse_date(role.get("end_date"))
        if start and end and start > end:
            flags.append("role date impossible")
    for skill in candidate.get("skills") or []:
        if isinstance(skill, dict):
            if str(skill.get("proficiency", "")).lower() == "expert" and float(skill.get("duration_months") or 0) == 0:
                flags.append("expert skill with zero months")
    return sorted(set(flags))


def workdna(candidate, mission_scores):
    profile = candidate.get("profile") or {}
    summary = str(profile.get("summary") or "")
    years = float(profile.get("years_of_experience") or 0)
    seniority = clamp(years * 9)
    narrative = clamp(len(summary) / 9)
    mission_base = sum(mission_scores.values()) / max(1, len(mission_scores))
    return clamp(0.40 * mission_base + 0.35 * seniority + 0.25 * narrative)


def load_candidates(file_obj):
    if file_obj is None:
        with open("sample_candidates.json", "r", encoding="utf-8") as f:
            return json.load(f)
    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    raw = open(path, "r", encoding="utf-8").read().strip()
    if raw.startswith("["):
        return json.loads(raw)
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def rank_candidates(jd, file_obj):
    candidates = load_candidates(file_obj)
    jd_weights = analyze_jd(jd)
    rows = []
    for c in candidates:
        cid = c.get("candidate_id") or c.get("id") or "UNKNOWN"
        mission, mission_scores = mission_fit(c, jd_weights)
        evidence, supported, total_skills = skill_evidence(c)
        physics, current_complexity, velocity, resilience, points = career_physics(c)
        wdna = workdna(c, mission_scores)
        flags = credibility_audit(c)
        audit = 100 if not flags else max(0, 100 - 32 * len(flags))
        behavior = 58
        signals = c.get("redrob_signals") or c.get("behavioral_signals") or {}
        if isinstance(signals, dict) and signals:
            vals = [float(v) for v in signals.values() if isinstance(v, (int, float))]
            if vals:
                behavior = clamp(sum(vals) / len(vals))
        score = (
            0.20 * wdna
            + 0.30 * evidence
            + 0.23 * physics
            + 0.14 * mission
            + 0.08 * audit
            + 0.05 * behavior
        )
        if flags:
            score *= 0.62
        reasoning = (
            f"Evidence {supported}/{total_skills}; career complexity {current_complexity:.0f}; "
            f"velocity {velocity:.0f}; resilience {resilience:.0f}; "
            f"flags: {', '.join(flags) if flags else 'none'}."
        )
        rows.append({
            "candidate_id": cid,
            "score": round(score, 2),
            "workdna": round(wdna, 1),
            "skill_evidence": round(evidence, 1),
            "career_physics": round(physics, 1),
            "mission_fit": round(mission, 1),
            "audit": round(audit, 1),
            "reasoning": reasoning,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    ordered = ["candidate_id", "rank", "score", "workdna", "skill_evidence", "career_physics", "mission_fit", "audit", "reasoning"]
    df = pd.DataFrame(rows, columns=ordered)
    out_path = os.path.join(tempfile.gettempdir(), "workdna_ranked_output.csv")
    df[["candidate_id", "rank", "score", "reasoning"]].head(100).to_csv(out_path, index=False, quoting=csv.QUOTE_MINIMAL)
    summary = (
        f"### Ranked {len(df)} candidates\n\n"
        f"JD weights: `{jd_weights}`\n\n"
        "Score = 20% WorkDNA + 30% Skill Evidence + 23% Career Physics + "
        "14% JD Mission Fit + 8% Credibility Audit + 5% Behavior.\n\n"
        "WorkDNA is intentionally lower-weighted so keyword-stuffed profiles do not dominate."
    )
    return df.head(100), out_path, summary


CSS = """
.gradio-container {max-width: 1180px !important}
.hero {padding: 18px 22px; border-radius: 18px; background: linear-gradient(135deg,#0f172a,#0e7490); color: white}
.hero h1 {margin: 0 0 8px 0}
"""


with gr.Blocks(title="WorkDNA Redrob Ranker") as demo:
    gr.HTML("""
    <div class='hero'>
      <h1>🧬 WorkDNA Redrob Ranker</h1>
      <p>Ranks candidates by proof, trajectory, credibility, and JD mission fit — not raw keyword count.</p>
    </div>
    """)
    with gr.Row():
        with gr.Column(scale=2):
            jd = gr.Textbox(label="Job description", value=DEFAULT_JD, lines=8)
            file_input = gr.File(label="Optional candidate JSON/JSONL upload", file_types=[".json", ".jsonl"])
            run = gr.Button("Run ranking", variant="primary")
        with gr.Column(scale=1):
            notes = gr.Markdown("""
            **Judge demo script**

            1. Paste/change the JD.
            2. Run on sample candidates or upload JSON/JSONL.
            3. Show how unsupported skills and impossible profiles lose.
            4. Download the ranked CSV.
            """)
    table = gr.Dataframe(label="Ranked candidates", wrap=True)
    download = gr.File(label="Download submission-style CSV")
    summary = gr.Markdown()
    run.click(rank_candidates, inputs=[jd, file_input], outputs=[table, download, summary])
    demo.load(rank_candidates, inputs=[jd, file_input], outputs=[table, download, summary])


if __name__ == "__main__":
    demo.launch()
