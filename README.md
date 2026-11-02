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


## Discover annual reports (next stage)

The **139-company Orbis list is preliminary**, not proof every company remains listed.
Keep the original financial workbook and full company manifest locally rather than committing them to this public repository.

Download the previously prepared `report_manifest.csv` from the private classifier package and place it alongside these scripts. It should have the columns `company_name,bvd_id,report_url,report_year`.

Search for candidate publicly available PDFs with:

```powershell
.\.venv\Scripts\python.exe discover_reports.py --limit 5
```

The script uses public search results and HTML links to find **candidates**, checks whether links return PDF bytes, and creates `report_candidates.csv`. A verified PDF link is **not** proof that it is the latest report, is a complete annual report, or belongs to the right issuer. Check each candidate against the company's investor-relations website, confirm the year and listing status, and then manually copy the accepted HTTPS PDF URL and annual year into your local `report_manifest.csv`. Never assume that a report from search is correct merely because its URL contains "annual report".

When the first few entries are validated, run `classify_reports.py --limit 2`, review the vision model's definition before accepting, and inspect the results. The process samples pages 1, 3, 6 and 10; these are not a substitute for reviewing an entire PDF and can miss the report's best graphical material.

**Example of a verified official 2025 PDF:** Vestas: https://www.vestas.com/content/dam/vestas-com/global/en/investor/reports-and-presentations/financial/2025/fy-2025/Vestas%20Annual%20Report%202025.pdf.coredownload.inline.pdf

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

## Troubleshooting and retry behavior

The classifier uses two JPEG pages (pages 1 and 6 where present) at reduced resolution, limits the model's generated tokens and uses a 180-second request timeout. A 403 download error is recorded rather than treated as a valid classification. The script now writes `scores.csv` after each attempt so earlier outcomes are preserved. `--limit 2` means *attempt the first two companies*, regardless of success.

To retry one company (for example, Novo Nordisk), create a local single-row CSV manifest with its original `company_name,bvd_id,report_url,report_year`. Use `--manifest name.csv --limit 1` and place any manually downloaded PDF under `reports/<bvd_id>.pdf`. It will be reused instead of downloaded. Check the generated score manually before running the full sample. These improvements reduce model workload but do not guarantee local machine capacity or accuracy; testing remains necessary.

## Google Colab GPU notebook

[Open the Assignment 5 notebook in Google Colab](https://colab.research.google.com/github/MVEST22/annual-report-fanciness-analysis/blob/main/Assignment_5_Colab_Classifier.ipynb). The notebook clones this repository, checks for an NVIDIA GPU, installs Ollama and the public dependencies, loads Gemma 3 4B, prompts for an annual-report manifest and verified PDF, has the researcher review the model's definition, scores one report using the existing Python classifier, and offers CSV results for download. **Colab GPUs are not guaranteed or permanently available.** Download outputs before a session ends. Do not upload licensed financial records to Colab or public GitHub. The pilot runs one PDF; the full company universe still needs verified annual reports and systematic processing.

## Multi-company Colab batches

The notebook now contains an optional **Batch processing with checkpoints** section. It accepts an archive of verified annual-report PDFs named by BvD ID, invokes `batch_classify.py`, saves `batch_scores.csv` after each company, and supports restarting without rescoring previous successful records. Checkpoint CSVs and the ZIP of public report PDFs remain local to the Colab session until downloaded. **Do not commit Orbis exports or private licensed data.** The pilot score for Vestas used pages 1 and 6; the updated final classifier samples page 1, page 6, the middle, and the later portion of each report. Re-score Vestas with the final methodology before pooling results.

## Bulk annual-report collection (Section 8 in Colab)

The Google Colab notebook includes a **Bulk report discovery and download** section. Upload the separate 139-company **names/identifiers-only** manifest, run `discover_reports.py` to propose public PDF candidates, then **manually verify issuer, financial year, and current listing** before putting approved URLs and years into your local manifest. Run `download_reports.py --manifest report_manifest.csv --limit 5` to test downloads (or omit `--limit` once verified). It saves verified PDF bytes to `reports/<bvd_id>.pdf` and an audit log `download_log.csv`. Blocked links (e.g. HTTP 403), missing URLs, and non-PDF downloads remain flagged; they are not silently accepted. The notebook can export a ZIP of successful PDFs, and Section 7 handles resume-safe scoring. Do **not** upload licensed Orbis financial data to Colab or GitHub.

These tools do not themselves prove that all 139 Orbis results are active Copenhagen-listed companies, and no comprehensive annual-report collection has yet been completed. The financial and design dataset must be joined and regression run only once the valid report sample is ready.

## Official investor-page candidate extraction (Colab Section 10)

Run `extract_official_report_links.py` against a local manifest with `official_source_page` columns. It visits known company-owned investor-relations pages, finds possible annual-report PDF links, and writes `official_page_candidates.csv` for manual source/year verification. This intentionally does not use SEC EDGAR, does not invent company domains, and does not automatically label HTML or false-positive links as verified PDF reports. Some official sites are script-rendered or rate-limited, so zero candidate results are possible. Scoring still requires a verified PDF for each company.
