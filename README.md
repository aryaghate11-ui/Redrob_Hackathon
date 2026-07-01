# Redrob Ranker

An evidence-based candidate ranking system built for the **India.RUNS × Redrob Data & AI Challenge**.

Instead of ranking candidates using only keyword matching, Redrob evaluates candidates based on actual career evidence, skill validation, work history, job description fit, and profile credibility.

---

## Features

- Evidence-based candidate ranking
- Skill validation from work experience
- Career growth and trajectory analysis
- Job Description (JD) matching
- Profile credibility checks
- Generates submission-ready ranking CSV

---

## Project Links

**GitHub Repository**

https://github.com/aryaghate11-ui/Redrob_Hackathon

**Hugging Face Demo**

https://huggingface.co/spaces/RogerDev-1234/Redrob-ranker

---

## Project Structure

```
app/                Backend
web/                Frontend
hf_space/           Hugging Face demo

reports/
    team_xxx.csv    Final ranked output

make_final_submission.py
START_WORKDNA.ps1

Idea_Submission_Template_Redrob_Filled_Final.pptx
```

---

## Running the Project

### 1. Open PowerShell

Navigate to the project folder:

```powershell
Set-Location -LiteralPath "C:\Users\Aarya\Downloads\[PUB] India_runs_data_and_ai_challenge\redrob_submission"
```

Start the application:

```powershell
.\START_WORKDNA.ps1
```

Open:

```
http://127.0.0.1:8765
```

---

## Generate Final Submission CSV

Run:

```powershell
python .\make_final_submission.py
```

Output:

```
reports/team_xxx.csv
```

---

## Validate the CSV

Use the official validator:

```powershell
python "...\validate_submission.py" "...\reports\team_xxx.csv"
```

Expected output:

```
Submission is valid.
```

---

## Ranking Model

The final score combines multiple evidence-based signals:

| Component | Weight |
|-----------|--------|
| Skill Evidence | 30% |
| Career Physics | 23% |
| WorkDNA | 20% |
| JD Mission Fit | 14% |
| Credibility Audit | 8% |
| Behavioral Signal | 5% |

### What they measure

- **Skill Evidence** – Confirms skills using real work and project experience.
- **Career Physics** – Evaluates career growth, responsibility, and progression.
- **WorkDNA** – Measures ownership, production work, and overall career profile.
- **JD Mission Fit** – Compares candidate experience against the job description.
- **Credibility Audit** – Detects inconsistent or unrealistic profiles.
- **Behavioral Signal** – Adds lightweight hireability indicators.

---

## Submission Checklist

- GitHub Repository
- Hugging Face Demo
- Pitch Deck (PPT/PDF)
- Final CSV (`reports/team_xxx.csv`)

If required, rename `team_xxx.csv` to your official team or participant ID before submission.

---

## Development

This project was developed with the assistance of **OpenAI Codex** for faster implementation, code generation, debugging, and model integration.

The repository was managed and uploaded using **Antigravity**, which streamlined version control and GitHub workflows.

---
