#!/usr/bin/env python3
"""Create reviewed WorkDNA labels for the repeated project archetypes."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "processed" / "project_archetypes.csv"
OUTPUT = ROOT / "data" / "labels" / "reviewed_archetype_labels.csv"

# relevance, production, retrieval/ranking, evaluation, ownership,
# transferability, disqualifier, concise rationale
LABELS = {
    "ARCH_53D0BFD924BE": (0, 0, 0, 0, 1, 0, 1, "Enterprise sales; no hands-on ML evidence."),
    "ARCH_CF23682F804D": (0, 0, 0, 0, 2, 0, 1, "Support leadership but no technical ML delivery."),
    "ARCH_6915252CE7FD": (0, 0, 0, 0, 2, 0, 1, "Marketing leadership; unrelated to the engineering mandate."),
    "ARCH_20CFCCA9B379": (0, 0, 0, 0, 1, 0, 1, "AI advisory explicitly lacks technical depth."),
    "ARCH_5F24947901CE": (0, 0, 0, 0, 2, 0, 1, "Creative direction is outside the role domain."),
    "ARCH_26383B98F98F": (0, 1, 0, 0, 2, 0, 1, "Hardware production experience but no NLP or ranking transfer."),
    "ARCH_D39C815AC1A3": (0, 0, 0, 0, 2, 0, 1, "Accounting leadership is unrelated."),
    "ARCH_460937C10B75": (0, 0, 0, 0, 1, 0, 1, "AI content vocabulary without engineering proof."),
    "ARCH_6F49E2B948EF": (0, 1, 0, 1, 3, 1, 1, "Operations leadership but no software or ML evidence."),
    "ARCH_AD79F1FF6BA5": (1, 4, 0, 1, 4, 2, 0, "Useful infrastructure depth; weak application ML evidence."),
    "ARCH_13E0507B5091": (0, 3, 0, 0, 2, 1, 1, "Production mobile engineering does not transfer enough."),
    "ARCH_B5D654ADD12D": (0, 2, 0, 0, 3, 1, 1, "Strong frontend craft but not the intelligence layer."),
    "ARCH_C916877D0775": (1, 3, 0, 0, 2, 2, 0, "Backend and distributed-system adjacency only."),
    "ARCH_D4842997370B": (1, 3, 0, 0, 2, 2, 0, "Full-stack production exposure but little ML ownership."),
    "ARCH_D41E2390B623": (0, 2, 0, 1, 2, 1, 1, "QA career is outside the target role."),
    "ARCH_BD461378EC63": (1, 3, 0, 1, 3, 2, 0, "Data platform depth with limited ML relevance."),
    "ARCH_6F5F164C61A3": (2, 4, 0, 2, 3, 3, 0, "Strong pipelines, drift awareness, and ML adjacency."),
    "ARCH_A6D861E80934": (1, 3, 0, 1, 3, 2, 0, "Startup data infrastructure with minor predictive work."),
    "ARCH_C66B9C638389": (2, 4, 0, 2, 3, 3, 0, "Streaming and feature-pipeline experience transfers moderately."),
    "ARCH_47A28EF8F937": (2, 2, 0, 3, 2, 3, 0, "Applied ML and experimentation, but not an ML specialist."),
    "ARCH_0153D979F48F": (2, 4, 0, 1, 3, 3, 0, "Strong Python production engineering and model integration."),
    "ARCH_313F510C506C": (2, 4, 0, 2, 2, 3, 0, "Production ML serving depth; modeling ownership is secondary."),
    "ARCH_49FEDA11702A": (4, 3, 4, 3, 3, 5, 0, "Direct recommendation and reranking; deployment was external."),
    "ARCH_F709F0699C13": (1, 3, 0, 2, 2, 1, 0, "Production CV is outside the target NLP and IR domain."),
    "ARCH_83B89E47317C": (2, 3, 0, 2, 2, 2, 0, "Production forecasting ML with limited ranking transfer."),
    "ARCH_5E2468D70C08": (2, 2, 0, 2, 2, 3, 0, "Applied predictive modeling; weak production ownership."),
    "ARCH_8AD4D8100014": (2, 2, 0, 2, 2, 3, 0, "NLP modeling transfers, but systems depth is limited."),
    "ARCH_3C421D56A732": (5, 5, 5, 5, 5, 5, 0, "Owned search learning-to-rank, labels, evaluation, and impact."),
    "ARCH_A2AF0BEE2D8A": (5, 5, 5, 5, 5, 5, 0, "Direct ranking models with offline-online calibration."),
    "ARCH_C042CA80ABD9": (4, 4, 5, 4, 4, 5, 0, "Strong semantic search and human relevance evaluation."),
    "ARCH_087F15EEF125": (3, 4, 3, 3, 4, 3, 0, "Production RAG, but evaluation is generation-oriented."),
    "ARCH_DC5571975001": (5, 5, 5, 5, 4, 5, 0, "Large-scale recommendations, ranking, and A/B testing."),
    "ARCH_AEEBE85BA4BA": (3, 5, 1, 3, 4, 4, 0, "Strong production ML operations and mentoring."),
    "ARCH_3F7A692A243A": (3, 5, 2, 4, 4, 3, 0, "Candidate matching and deployment; retrieval is weaker."),
    "ARCH_F73BD00561A1": (5, 5, 5, 5, 5, 5, 0, "Exact recruiter-search architecture and evaluation match."),
    "ARCH_4E5A877F3084": (5, 5, 5, 5, 5, 5, 0, "End-to-end marketplace recommendation with experimentation."),
    "ARCH_E3C7EB061150": (5, 5, 5, 5, 5, 5, 0, "Exact candidate ranking and behavioral reranking."),
    "ARCH_6FB33F7B2B53": (5, 5, 5, 5, 5, 5, 0, "Candidate-search migration, operations, metrics, and mentoring."),
    "ARCH_813340E3696F": (5, 5, 5, 5, 5, 5, 0, "Hybrid retrieval with drift handling and team leadership."),
    "ARCH_BB08D1841FC6": (5, 5, 5, 4, 5, 5, 0, "Plain-language matching overhaul and team growth."),
    "ARCH_C215D256F73D": (4, 5, 4, 5, 4, 5, 0, "Personalization experiments and production operations."),
    "ARCH_CF92524D1B48": (5, 5, 5, 5, 5, 5, 0, "Flagship ranking ownership across data and operations."),
    "ARCH_9A851BF2052F": (5, 5, 5, 5, 5, 5, 0, "Plain-language search ownership with product judgment."),
    "ARCH_E51A75098E6B": (5, 5, 5, 4, 5, 5, 0, "Plain-language relevance infrastructure leadership."),
}

FIELDS = [
    "archetype_id", "frequency", "relevance_tier", "production_depth",
    "retrieval_ranking_depth", "evaluation_maturity", "ownership",
    "transferability", "disqualifier", "rationale", "description",
]


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8-sig")))
    source_ids = {row["archetype_id"] for row in rows}
    if source_ids != set(LABELS):
        raise SystemExit(
            f"Label mismatch. Missing={source_ids - set(LABELS)}; "
            f"extra={set(LABELS) - source_ids}"
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item["archetype_id"]):
            values = LABELS[row["archetype_id"]]
            writer.writerow({
                "archetype_id": row["archetype_id"],
                "frequency": row["frequency"],
                "relevance_tier": values[0],
                "production_depth": values[1],
                "retrieval_ranking_depth": values[2],
                "evaluation_maturity": values[3],
                "ownership": values[4],
                "transferability": values[5],
                "disqualifier": values[6],
                "rationale": values[7],
                "description": row["description"],
            })
    print(f"Wrote {len(rows)} reviewed labels to {OUTPUT}")


if __name__ == "__main__":
    main()
