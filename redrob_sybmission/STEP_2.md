# Step 2 - Digital Twin Pairwise Ranker

## What was built

The second system is a local pairwise learning-to-rank model implemented with
NumPy. It uses no hosted AI API, GPU, scikit-learn, LightGBM, or XGBoost.

The model is trained from the reviewed project evidence produced in Step 1.

## Why pairwise ranking

Recruiters compare candidates rather than assigning isolated absolute scores.
The model therefore learns questions such as:

- Which of two candidates has stronger demonstrated ranking ownership?
- Given equivalent work evidence, which candidate is more realistically
  hireable?
- Does a production search project beat an unsupported AI skill list?
- Does a plain-language matching project beat a fashionable RAG demo?

## Training comparison families

1. **Behavioral twins**
   - Identical project archetypes.
   - Different activity, response, notice, location, and credibility evidence.

2. **Within-tier hard pairs**
   - Similar technical relevance.
   - Different ownership, production, evaluation, and supporting projects.

3. **Cross-tier pairs**
   - Direct retrieval/ranking evidence compared with adjacent or irrelevant
     work.

## Leakage control

The dominant project archetype determines train, validation, or test placement.
Candidates whose strongest evidence comes from the same repeated archetype
cannot appear in multiple splits.

## Run

```powershell
python .\src\create_reviewed_labels.py
python .\src\train_pairwise_ranker.py
python .\src\score_with_pairwise_model.py
```

## Verified internal results

- Candidates processed: 100,000
- Model features: 23
- Training pairs: 78,399
- Validation pairs: 19,747
- Test pairs: 19,645
- Held-out pairwise accuracy: 93.07%
- Correlation with reviewed evidence target: 0.944

These metrics measure consistency with our reviewed evidence rubric and digital
twin constraints. They are not hidden-leaderboard accuracy.

## Outputs

- `data/labels/reviewed_archetype_labels.csv`
- `models/pairwise_ranker/model.json`
- `reports/step2_training_report.json`
- `reports/step2_ranked_candidates.csv`
- `reports/step2_top100.csv`

## Next system

Step 3 will stress-test the saved model by removing skills, injecting keywords,
neutralizing employer prestige, removing production evidence, and changing
availability. It will produce a Rank Stability Certificate for every top
candidate.
