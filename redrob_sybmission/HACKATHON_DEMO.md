# WorkDNA hackathon demonstration

## Recommended presentation sequence

### 1. Overview

Open **Overview** in the left navigation.

Explain the five-stage pipeline:

1. Convert the JD into success missions.
2. Extract project evidence from career history.
3. Create digital-twin comparisons.
4. Train the local pairwise ranking model.
5. Stress-test the resulting ranking.

This page also restates the hackathon constraints: top 100, CPU only, no
network, and factual reasoning.

### 2. Evidence Lab

Open **Evidence Lab**.

Show how a raw profile becomes:

```text
Raw profile
  -> Project DNA
  -> Reviewed archetype
  -> 23 model features
```

Use the live candidate example to explain production, retrieval, evaluation,
ownership, and transferability scores.

Highlight the anti-keyword result:

- perfect AI keyword injection changes zero scores;
- removing genuine project evidence severely reduces the ranking.

### 3. Stability Audit

Open **Stability Audit**.

The displayed candidates are a real digital-twin pair from the loaded dataset.
They share the same dominant project archetype.

The comparison keeps work evidence constant and shows differences such as:

- open-to-work status;
- recruiter response rate;
- notice period;
- recent activity.

Click **Next real twin** to show another comparison.

Explain that behavioral evidence only reorders candidates after technical work
evidence is comparable. It cannot promote an irrelevant candidate.

### 4. Candidates

Open **Candidates**.

Demonstrate:

- ranked candidate ledger;
- evidence-tier filter;
- availability filter;
- title/company/location search;
- mission readiness;
- strongest project evidence;
- complete career history;
- counterfactual rank changes.

### 5. Recruiter rating

At the bottom of the candidate inspector:

- choose a rating from one to five stars;
- write interview or hiring notes;
- reload the page.

The rating and notes remain stored locally on the recruiter’s machine.
Recruiter judgment is deliberately separate from the model score.

### 6. Dataset import and export

Use **Import dataset** to upload a compatible `.json` or `.jsonl` file.

Use **Export shortlist** to download:

```csv
candidate_id,rank,score,reasoning
```

The supplied dataset remains unchanged and all ranking happens offline.

## Digital twin explanation

A digital twin is not a synthetic person. It is a real candidate paired with
another real candidate sharing the same dominant project-evidence archetype.

Example:

```text
Candidate A and Candidate B
  same ranking/search project evidence
  same relevance tier

Candidate A
  open to work
  stronger response behavior
  shorter notice period

Candidate B
  inactive
  weaker response behavior
  longer notice period
```

The model learns:

```text
With technical evidence held constant, Candidate A should rank above B.
```

Cross-tier pairs separately teach:

```text
Production ranking engineer > AI-keyword-heavy irrelevant profile
```

This prevents behavioral signals from overriding technical relevance.
