import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import train_pairwise_ranker as ranker


def test_reviewed_labels_cover_all_archetypes():
    labels = ranker.load_labels(ranker.LABELS_PATH)
    assert len(labels) == 44


def test_direct_ranking_project_beats_keyword_only_project():
    labels = ranker.load_labels(ranker.LABELS_PATH)
    assert labels["ARCH_F73BD00561A1"]["relevance_tier"] == 5
    assert labels["ARCH_460937C10B75"]["relevance_tier"] == 0


def test_plain_language_hidden_gems_are_tier_five():
    labels = ranker.load_labels(ranker.LABELS_PATH)
    assert labels["ARCH_9A851BF2052F"]["relevance_tier"] == 5
    assert labels["ARCH_BB08D1841FC6"]["relevance_tier"] == 5
