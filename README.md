# Assignment 5 — Annual Report Fanciness and Profit

This project studies the association between visual sophistication of annual reports (score 1–5) and company profit for Copenhagen-listed companies.

## Status
- [x] SDU Orbis export obtained locally (139 preliminary company records)
- [ ] Verify current listed-company universe and avoid duplicate share classes
- [ ] Gather the latest annual-report PDFs and record source URLs and years
- [ ] Review and approve the vision model's definition of *fancy*
- [ ] Generate scores based only on visual report pages
- [ ] Run OLS regression against Orbis net income (million DKK)
- [ ] Report the coefficient, p-value and company count; complete class results form

## Contents
- `classify_reports.py` — local Ollama vision analysis of report PDFs
- `regression.py` — estimates OLS from a locally joined, company-level dataset
- `report_manifest_template.csv` — template for PDF report identification
- `requirements.txt` — Python dependencies

## Setup
Install [Ollama](https://ollama.com/) and download the free local vision model:

```powershell
ollama pull gemma3:4b
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Populate a **local** CSV named `report_manifest.csv` with columns `company_name,bvd_id,report_url,report_year`. All URLs must point directly to publicly accessible HTTPS PDF files (or manually place PDFs under `reports/<bvd_id>.pdf`). Report year and current listing status must be verified.

Start with:

```powershell
.\.venv\Scripts\python.exe classify_reports.py --limit 2
```

Before classifying anything, the script asks the actual LLM for its definition of *fancy*, prints it, and requires the user to enter `YES` after reviewing. It never uses profit to assign design scores. Classification outputs a local `scores.csv` file. Run without `--limit` to process all identified PDFs.

## Regression
Locally create `private_data/analysis_dataset.csv` with one row per company and columns `bvd_id,profit_m_dkk,fanciness`. The script accepts positive and negative profit and drops missing values. Run:

```powershell
.\.venv\Scripts\python.exe regression.py --input private_data/analysis_dataset.csv
```

The script writes statistical output locally in `results/`. It estimates `profit_m_dkk = intercept + beta * fanciness + error`. The estimated beta is the average association in DKK millions for a one-point increase in fanciness, not a causal effect. The required p-value and number of companies are also reported.

## Data handling
**Do not publicly upload the Orbis financial export, linked financial dataset, or other licensed records without checking SDU's database terms.** This repository intentionally includes only source code, documentation, and blank templates. Report PDFs may have separate rights and are excluded from version control. The local workbook and reports are not published here.

No annual-report scores or regression estimates have yet been produced. The 139 Orbis results are a preliminary search outcome, not a confirmed count of currently listed issuers.
