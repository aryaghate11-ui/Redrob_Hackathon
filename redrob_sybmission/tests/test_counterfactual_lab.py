import sys
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import run_counterfactual_lab as lab
import train_pairwise_ranker as ranker


def sample_vector():
    values = np.zeros(len(ranker.FEATURE_NAMES))
    values[lab.INDEX["best_relevance"]] = 5
    values[lab.INDEX["second_relevance"]] = 4
    values[lab.INDEX["best_production"]] = 5
    values[lab.INDEX["best_retrieval"]] = 5
    values[lab.INDEX["best_evaluation"]] = 5
    values[lab.INDEX["best_ownership"]] = 5
    values[lab.INDEX["best_transferability"]] = 5
    values[lab.INDEX["mission_coverage"]] = 5
    values[lab.INDEX["relevant_project_count"]] = 2
    values[lab.INDEX["skill_assessment_corroboration"]] = 0.5
    return values


def test_keyword_injection_is_invariant():
    vector = sample_vector()
    changed = lab.counterfactuals(vector)["perfect_keywords_injected"]
    assert np.array_equal(vector, changed)


def test_project_removal_removes_technical_evidence():
    changed = lab.counterfactuals(sample_vector())["all_project_evidence_removed"]
    for name in [
        "best_relevance",
        "best_production",
        "best_retrieval",
        "best_evaluation",
        "best_ownership",
    ]:
        assert changed[lab.INDEX[name]] == 0


def test_contradiction_injection_adds_one_flag():
    vector = sample_vector()
    changed = lab.counterfactuals(vector)["contradiction_injected"]
    assert (
        changed[lab.INDEX["contradiction_count"]]
        == vector[lab.INDEX["contradiction_count"]] + 1
    )
