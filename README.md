# RT BDI AI Reporting Assistant

This repository contains the first implementation scaffold for an assistant that answers plain-English questions by using the RT BDI reporting website.

## What is included

- A report knowledge map in `knowledge/report_map.json` built from the provided screenshots and spreadsheet exports.
- Spreadsheet readers for CSV, XLS, XLSX, and HTML-style XLS exports.
- Date-range parsing that avoids the site's empty "today only" default by falling back to month-to-date.
- Numeric parsing for currency, percentages, and totals.
- A lightweight query planner that maps user language to report candidates, metrics, filters, joins, and date ranges.
- An OpenAI-backed planning adapter that reads `OPENAI_API_KEY` from the environment.
- A Playwright automation skeleton for login/session reuse, report navigation, Select2 filters, date setting, generation, and export download.

Raw customer screenshots and exports are intentionally not committed. Keep them outside git and pass their folder path to the inspection script.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

## Inspect provided assets

```bash
python scripts/inspect_assets.py /path/to/extracted/assets --json
```

## Plan a question

```bash
rtbdi plan "Top seller's plan mix, their store inventory, and gross profit vs #2 last month"
```

The planner returns the reports it would use and the date range it resolved. Live execution still needs credentials or a reusable authenticated browser storage state.

Preview the OpenAI prompt without spending API calls:

```bash
rtbdi prompt-preview "What is Natalie's conversion ratio last month?"
```

Use OpenAI to refine the report plan:

```bash
OPENAI_API_KEY=... rtbdi ai-plan "Top 5 employees by accessories last month"
```

## Environment for live automation

The browser runner expects either credentials or an authenticated Playwright storage state. Do not commit secrets.

Suggested environment variables:

- `RTBDI_BASE_URL=https://www.myrtpos.com/newbdi/`
- `RTBDI_USERNAME=...`
- `RTBDI_PASSWORD=...`
- `RTBDI_STORAGE_STATE=/secure/path/storage-state.json`
- `OPENAI_API_KEY=...`
- `OPENAI_MODEL=gpt-4.1-mini`

You can verify the RT BDI login and save a reusable authenticated session:

```bash
RTBDI_BASE_URL=https://www.myrtpos.com/newbdi/index.fwx \
RTBDI_USERNAME=... \
RTBDI_PASSWORD=... \
rtbdi login-session --storage-state /secure/path/rtbdi-storage-state.json
```

After that, set `RTBDI_STORAGE_STATE=/secure/path/rtbdi-storage-state.json` for live report runs.

Generate and download a live report export:

```bash
RTBDI_STORAGE_STATE=/secure/path/rtbdi-storage-state.json \
rtbdi live-export employee_conversion_ratio --start 2026-06-01 --end 2026-06-21
```

The command prints the downloaded export path plus detected sheet/column metadata.

Answer a supported live question:

```bash
RTBDI_STORAGE_STATE=/secure/path/rtbdi-storage-state.json \
rtbdi live-answer "What is Natalie Gonzalez's conversion ratio?"
```

The first live-answer scope supports simple employee/store questions backed by
Employee Conversion Ratio and Employee Performance exports, including conversion
ratio, qpay count, employee store/name/user ID, activations, hours, accessory
sales/profit, employee counts, and store totals.

It also supports the first ranking and merged-report questions:

```bash
rtbdi live-answer "Top 5 employees by accessory sales."
rtbdi live-answer "Top 5 stores by total accessory sales."
rtbdi live-answer "Top accessory seller - what's their gross profit and store?"
rtbdi live-answer "Top seller's plan mix, their store inventory, and gross profit vs #2."
rtbdi live-answer "Total financed amount."
rtbdi live-answer "Which employee had the highest financed dollar amount and their gross profit?"
rtbdi live-answer "How many trade-ins applied, by carrier?"
rtbdi live-answer "How many Samsung phones in stock?"
rtbdi live-answer "Top 5 fastest-selling phones in the last 30 days."
rtbdi live-answer "Total open PO amount by vendor."
rtbdi live-answer "Total transfer cost between stores last month."
```

The merged examples generate multiple reports, join by employee/store, and then
calculate the answer from the downloaded exports.

Validate live report export coverage:

```bash
rtbdi validate-reports employee_conversion_ratio finance_report inventory_report \
  --start 2026-06-01 --end 2026-06-21 --continue-on-error

rtbdi validate-reports --all --start 2026-06-01 --end 2026-06-21 --continue-on-error
```

Evaluate a numbered question-bank PDF against the planner:

```bash
rtbdi eval-question-bank /path/to/RTBDI_BIG_Question_Bank.pdf --allow-clarifications
```

See `docs/live_validation_summary.md` for the latest live validation matrix and
known report-specific edge cases.

## Current status

The map is a working seed from the supplied files. Reports with exports have exact column names. Reports represented only by screenshots are included with page/filter metadata where visible and marked for live validation before answering production questions.
