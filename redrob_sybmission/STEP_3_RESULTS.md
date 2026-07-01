# Step 3 results

The Counterfactual Ranking Lab tested all 100,000 candidates and generated an
individual Rank Stability Certificate for every top-100 candidate.

## Outcome

- 83 candidates: `robust_evidence_driven`
- 17 candidates: `acceptable_with_review`
- 0 candidates: `fragile_requires_review`
- Average overall stability: 89.54/100
- Average keyword independence: 100/100
- Average skill-list independence: 95.4/100
- Average project-evidence reliance: 100/100

## Full-pool tests

### Keyword injection

- Maximum score change: 0
- Top-100 membership changes: 0
- Result: passed

The model cannot promote a candidate merely because fashionable JD keywords
are added.

### Perfect skill corroboration

- Irrelevant candidates entering the top 100: 0
- Top-100 membership changes among relevant candidates: 4
- Result: passed

Skills can refine ordering, but cannot rescue irrelevant career evidence.

### Contradiction injection

- Candidates receiving a lower score: 100,000 of 100,000
- Result: passed

### Project-evidence removal

- Median score drop across the pool: 1.007
- Median score drop for Tier-5 candidates: 8.668
- Result: passed

The top ranking is causally dependent on demonstrated work rather than résumé
decoration.

## Interpretation

Company context has more influence than keywords or skills because the JD
explicitly distinguishes product-company experience from service-only careers.
The model does not use raw employer names or prestige rankings.

These are internal robustness results. They do not represent hidden-label
leaderboard accuracy.
