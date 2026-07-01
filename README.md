Redrob Ranker
Evidence-based candidate ranking system for the India.RUNS / Redrob Data & AI Challenge.
The system ranks candidates using proof from work history, skill evidence, career trajectory, JD fit, and credibility checks instead of only matching keywords.
Links
GitHub: https://github.com/aryaghate11-ui/Redrob_Hackathon
Hugging Face demo: https://huggingface.co/spaces/RogerDev-1234/Redrob-ranker
Main files
reports/team_xxx.csv                                  Final ranked output
Idea_Submission_Template_Redrob_Filled_Final.pptx     Pitch deck
make_final_submission.py                              Generates final CSV
START_WORKDNA.ps1                                     Starts local app
app/                                                  Backend
web/                                                  Frontend
hf_space/                                             Hugging Face demo
How to run the local app
Open PowerShell and go to the project folder:
Set-Location -LiteralPath "C:\Users\Aarya\Downloads\[PUB] India_runs_data_and_ai_challenge\redrob_sybmission"
Start the app:
.\START_WORKDNA.ps1
Open this in your browser:
http://127.0.0.1:8765
How to generate the final ranking CSV
From the project folder:
python .\make_final_submission.py
The final CSV is saved here:
reports/team_xxx.csv
How to validate the submission CSV
Use the validator provided in the original dataset folder:
python "C:\Users\Aarya\Downloads\[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\validate_submission.py" "C:\Users\Aarya\Downloads\[PUB] India_runs_data_and_ai_challenge\redrob_sybmission\reports\team_xxx.csv"
Expected output:
Submission is valid.
Model summary
Final ranking uses:
30% Skill Evidence
23% Career Physics
20% WorkDNA
14% JD Mission Fit
8% Credibility Audit
5% Behavioral / hireability signal
What these mean
Skill Evidence: checks whether claimed skills are supported by actual work/project text.
Career Physics: measures role complexity, career velocity, resilience, and growth into harder work.
WorkDNA: baseline profile from career history, ownership, production work, and role signals.
JD Mission Fit: compares candidate evidence against the job description needs.
Credibility Audit: penalizes suspicious or impossible profiles.
Behavior Signal: adds lightweight hireability/platform activity signals.
Submission checklist
Before final submission, include:
GitHub repo link
Hugging Face/demo link
Pitch deck PDF/PPTX
Final ranked CSV: reports/team_xxx.csv
If required by the organizers, rename team_xxx.csv to your official team or participant ID.stuffer risk while still preserving useful semantic/profile information.
