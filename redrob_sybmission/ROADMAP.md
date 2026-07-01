# WorkDNA implementation roadmap

## 1. WorkDNA Evidence Engine

Status: **implemented**

1. Stream and validate all candidate records.
2. Deduplicate career descriptions into stable project archetypes.
3. Extract evidence flags and credibility checks.
4. Build compact candidate feature records.
5. Review and label each archetype from relevance tier 0 to 5.
6. Freeze the versioned evidence taxonomy.

Completion gate:

- 100,000 candidates processed with no duplicate IDs.
- All career entries mapped to a stable archetype ID.
- Archetype frequencies reproduce exactly on repeated runs.
- Human labels exist for every unique archetype.

## 2. Digital Twin Pairwise Ranker

Status: **implemented**

1. Build work twins, skill twins, and behavioral twins.
2. Generate high-confidence pairwise ordering constraints.
3. Split evaluation by archetype to prevent template leakage.
4. Train LightGBM LambdaRank/rank_xendcg.
5. Compare against rules-only, BM25, and embedding baselines.
6. Calibrate scores and produce relevance tiers.

Completion gate:

- Pairwise accuracy improves over the deterministic baseline.
- Strong work evidence beats skill-only keyword matches.
- Behavioral signals cannot rescue irrelevant candidates.
- Ranking completes in under five minutes on CPU.

## 3. Counterfactual Ranking Lab

Status: **implemented**

1. Remove skills while preserving work.
2. Inject perfect JD keywords into irrelevant profiles.
3. Neutralize employer names and titles.
4. Remove production, ownership, or evaluation evidence.
5. Change availability signals within realistic ranges.
6. Generate stability, keyword-dependence, and evidence-reliance scores.

Completion gate:

- Names and neutral employer substitutions do not materially affect rank.
- Keyword injection does not promote irrelevant candidates.
- Removing genuine project evidence causes a substantial rank decline.
- Every top-100 candidate has an auditable stability report.

