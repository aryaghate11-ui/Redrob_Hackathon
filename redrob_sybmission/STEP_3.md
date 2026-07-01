# Step 3 - Counterfactual Ranking Lab

## Purpose

The lab tests whether the ranking model succeeds for the right reasons.
Plausible output alone is not accepted as proof.

Every shortlisted candidate is reranked after controlled one-factor mutations:

1. Remove skill-list corroboration.
2. Inject perfect AI keywords.
3. Neutralize employer context.
4. Neutralize behavioral availability.
5. Make the candidate unavailable.
6. Inject a profile contradiction.
7. Remove production evidence.
8. Remove evaluation evidence.
9. Remove ownership evidence.
10. Remove all project evidence.

Each changed candidate is ranked against the unchanged 100,000-person pool.

## Run

```powershell
python .\src\run_counterfactual_lab.py
```

## Rank Stability Certificate

Each top-100 candidate receives:

- Keyword independence
- Skill-list independence
- Company-context independence
- Project-evidence reliance
- Credibility sensitivity
- Availability sensitivity
- Overall stability verdict
- Original and counterfactual ranks

## Expected behavior

| Mutation | Expected result |
|---|---|
| Add AI keywords | No score or rank change |
| Remove skills | Small or no change |
| Neutralize employer | Small change |
| Remove project evidence | Severe rank decline |
| Inject contradiction | Score and rank decline |
| Make unavailable | Moderate decline |
| Remove production/evaluation/ownership | Meaningful decline |

## Outputs

- `reports/counterfactual/counterfactual_audit_report.json`
- `reports/counterfactual/rank_stability_summary.csv`
- `reports/counterfactual/rank_stability_certificates.jsonl`
- `reports/counterfactual/certificates/CAND_XXXXXXX.json`

The audit is a model-quality test. It does not estimate the hidden leaderboard
score.
