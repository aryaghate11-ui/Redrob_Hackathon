---
title: WorkDNA Redrob Ranker
emoji: 🧬
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.19.0
app_file: app.py
pinned: false
---

# WorkDNA Redrob Ranker

Offline-style Gradio sandbox for the Redrob candidate-ranking challenge.

This Space demonstrates the product idea on bundled sample candidates and on uploaded JSON/JSONL files:

- JD understanding instead of pure keyword matching
- lower-weight WorkDNA score
- Skill Evidence Ratio to penalize unsupported skill stuffing
- Career Physics to score complexity, velocity, resilience, and production work
- strict credibility audit for impossible/honeypot-like profiles

The full 100K-candidate ranking is generated locally in the main repository because the challenge dataset is large and should not be uploaded into a public demo Space.
