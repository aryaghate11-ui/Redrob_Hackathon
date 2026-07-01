# WorkDNA application architecture

## Offline runtime

```text
Browser
  -> React production frontend
  -> local Python HTTP API
  -> WorkDNA feature extraction
  -> saved NumPy pairwise ranker
  -> ranked candidates and CSV export
```

No hosted model, vector database, telemetry service, or cloud API is required.

## Dataset handling

- The original challenge dataset is read from its existing location.
- Importing a dataset writes a separate copy under `data/imports/`.
- `.jsonl` and JSON arrays are accepted.
- The original challenge files are never overwritten.
- Uploaded records are processed using the same candidate schema.
- Previously unseen project descriptions receive conservative scores until
  their archetypes are reviewed and added to the label catalog.

## User workflow

1. Start `START_WORKDNA.bat`.
2. Open `http://127.0.0.1:8765`.
3. Search and filter ranked candidates.
4. Inspect mission readiness, project evidence, career history, and stability.
5. Import another compatible dataset if required.
6. Export the top 100 as a challenge-format CSV.

## API

- `GET /api/status`
- `GET /api/candidates`
- `GET /api/candidates/{candidate_id}`
- `POST /api/import?filename=...`
- `GET /api/export?top_k=100`
