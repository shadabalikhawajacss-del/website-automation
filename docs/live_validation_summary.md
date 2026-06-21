# RT BDI Live Validation Summary

Date: 2026-06-21

This file records live validation performed with the supplied RT BDI login and a
saved Playwright storage state. Raw downloaded exports are not committed.

## Planner validation

- Uploaded question bank: `RTBDI_BIG_Question_Bank_c78c.pdf`
- Questions found: 122
- Planner result: 122/122 routed or correctly clarified

Command:

```bash
rtbdi eval-question-bank /path/to/RTBDI_BIG_Question_Bank_c78c.pdf --allow-clarifications
```

## Live report export validation

Reports validated as open/generate/export/parse:

### Employee

- Employee Conversion Ratio
- Employee Performance Report
- Employee Ranking By Box Sales
- Employee MRC Matrix Report
- KPI Report By Employee
- Box Report By Employee
- Employee APH+MRC Report
- Employee Performance Stack Rank
- Employee Ranking By Finance
- Employee MRC Summary

### Sales

- Finance/Lease Report
- Trade-In Custom Report
- Phone Trend By Market
- Phone Trend By Market -> Model

### Inventory

- Inventory Report
- PO Listing Report
- Open PO Report
- Inventory Transfer Listing
- Inventory Transfer Detail
- Inventory Audit Log
- Inventory Tangible Audit Log
- Serial Adjusted Report
- RMA Serial Report
- RMA Shipped Report
- Serial Demo/Display Report
- Serial Aging Report

## Known live validation edge cases

These are now reported explicitly by `rtbdi validate-reports`:

- Profit Loss Report: access denied for the supplied login.
- Buy-Back InStock Report: access denied for the supplied login.
- Serial Number Report: downloads a malformed legacy `.xls` file that `xlrd`
  cannot parse (`downloaded_parse_failed`).
- Bill Payment Listing: page has an `Export to Excel` submit input, but the
  current browser event flow does not emit a Playwright download event.
- Promo Fee Report, ESN Change Report, Inventory Transaction Report: page opens
  and generates, but live export did not emit a download event in validation.
- Tangible Adjusted Report: download event occurred, but the browser canceled
  the file save in validation.
- Not Verified Serial Report: export did not emit a download event in validation.

These are not hidden failures; the validator records them so the next iteration
can add report-specific handlers or confirm account permissions.

## Edge-case investigation notes

- Bill Payment Listing: clicking the visible `Export to Excel` submit input does
  not emit a Playwright download event. A direct authenticated form POST to
  `BillPaymentListing.fwx` also timed out at 120 seconds for the tested
  company-wide date range, so this likely needs either tighter required filters
  or a report-specific server endpoint/parameter check.
- Employee APH+MRC Report: exports through the visible `Export` button rather
  than Raw Excel; the report-specific export mode handles this.
- Finance and Trade-In: use the DevExtreme grid export button rather than Raw
  Excel; the report-specific export mode handles this.
- Serial Number Report: downloads a large legacy `.xls` file, but `xlrd` raises
  `AssertionError`. No local LibreOffice/soffice converter is available in this
  environment, so this remains a custom legacy-BIFF parsing task.

## Live answer validation examples

- `What is Natalie Gonzalez's conversion ratio?` -> 48.28%
- `Total accessory sales at ROCKON NASA.` -> $8,522.18
- `Top 5 employees by accessory sales.` -> Aftab, Sabina, Hajra, hafi, MUHAMMAD
- `Top 5 stores by total accessory sales.` -> ROCKON MAIN, WALLER, ROSENBERG, NASA, TOMBALL
- `Total financed amount.` -> $6,302.32
- `Which employee had the highest financed dollar amount and their gross profit?` -> Ramiro, gross profit $-12,622.97
- `How many trade-ins applied, by carrier?` -> unknown 3, Verizon 2
- `Top 5 fastest-selling phones in the last 30 days.` -> TripleSIM, Samsung A16, Samsung Tab A9+, Samsung A17, TMO REVVL Tab 2
- `How many Samsung phones in stock?` -> 1,834
- `Total open PO amount by vendor.` -> IDOO-AUTO $147,721.44, ALPHACOMM $1,414.20, SUPERIOR $138.25
- `Total transfer cost between stores last month.` -> $192,888.26
- `Top accessory seller - what's their gross profit and store?` -> Aftab, gross profit $-12,712.18, stores ROCKON ROSENBERG and ROCKON WALLER
- `Top seller's plan mix, their store inventory, and gross profit vs #2.` -> generated and merged ranking, MRC matrix, KPI, and inventory exports
