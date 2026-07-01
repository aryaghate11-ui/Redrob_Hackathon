# WorkDNA Candidate Ranking

WorkDNA ranks candidates by demonstrated work, production ownership, career
trajectory, credibility, and real-world hireability. Skills are treated as
supporting evidence, not as the primary source of truth.

## System priority

1. **WorkDNA Evidence Engine — highest priority**
   - Converts career entries into reusable project archetypes.
   - Extracts production, retrieval, ranking, evaluation, ownership, scale,
     outcome, and leadership evidence.
   - Detects contradictions and creates compact candidate-level ML features.
   - Required before either of the later systems can work reliably.

2. **Digital Twin Pairwise Ranker — second priority**
   - Finds candidates with similar work but different skills or behavior.
   - Creates pairwise training examples from defensible ordering constraints.
   - Trains a LightGBM learning-to-rank model optimized for NDCG.

3. **Counterfactual Ranking Lab — third priority**
   - Removes skills, injects keywords, neutralizes company prestige, and changes
     behavioral availability.
   - Measures whether rankings move for the correct reasons.
   - Produces a Rank Stability Certificate for shortlisted candidates.

## Concise build sequence

1. Build the evidence catalog and candidate feature store.
2. Manually review and label the small set of unique project archetypes.
3. Create candidate relevance tiers and pairwise comparisons.
4. Train and cross-validate the learning-to-rank model.
5. Add bounded behavioral and contradiction adjustments.
6. Generate the top 100 with evidence-grounded reasoning.
7. Stress-test the ranking with digital twins and counterfactual profiles.
8. Validate runtime, CSV format, Docker reproduction, and hosted demo.

## Step 1: current implementation

Run from this folder:

```powershell
python .\src\build_evidence_catalog.py
```

Optional explicit paths:

```powershell
python .\src\build_evidence_catalog.py `
  --candidates "..\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\candidates.jsonl" `
  --output ".\data\processed"
```

The script uses only the Python standard library and streams the 487 MB JSONL,
so it does not load all 100,000 candidates into memory.

### Generated artifacts

- `data/processed/project_archetypes.csv`: unique career-project descriptions,
  frequencies, and initial evidence flags.
- `data/processed/archetype_label_template.csv`: review sheet for human labels.
- `data/processed/candidate_features.jsonl`: compact candidate-level features.
- `data/processed/dataset_summary.json`: counts, distributions, and QA results.

The automatic archetype tier is only a bootstrap label. The manually reviewed
label becomes the supervised target in Step 2.

