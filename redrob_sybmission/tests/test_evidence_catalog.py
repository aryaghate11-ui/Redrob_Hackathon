import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "build_evidence_catalog.py"
)
SPEC = importlib.util.spec_from_file_location("build_evidence_catalog", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_retrieval_archetype_gets_top_preliminary_tier():
    description = (
        "Owned a production hybrid retrieval system using BM25 and BGE embeddings. "
        "Designed NDCG and MRR evaluation, led the rollout, and improved engagement 18%."
    )
    evidence = MODULE.extract_archetype_evidence(description)

    assert evidence["retrieval"] == 1
    assert evidence["embeddings"] == 1
    assert evidence["evaluation"] == 1
    assert evidence["production"] == 1
    assert evidence["ownership"] == 1
    assert MODULE.preliminary_tier(evidence) == 5


def test_keyword_only_profile_does_not_get_high_tier():
    description = "Experimented with ChatGPT and prompt engineering for content."
    evidence = MODULE.extract_archetype_evidence(description)

    assert evidence["llm_demo_risk"] == 1
    assert MODULE.preliminary_tier(evidence) <= 1


def test_archetype_id_is_stable_under_whitespace_and_case():
    first = MODULE.stable_archetype_id("Built a ranking system")
    second = MODULE.stable_archetype_id("  BUILT   A ranking SYSTEM ")

    assert first == second

