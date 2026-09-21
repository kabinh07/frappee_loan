# Module 03 — Loan Classification

## Navigation
URL:         /app/loan-classification
Awesome bar: "Loan Classification"

## What is it?
Loan Classification is a two-field lookup doctype that does nothing but define a
vocabulary: a short code and a name for a risk bucket (for example, "Standard" or
"Doubtful"). It holds no thresholds and no logic itself — it exists purely so that
other places in the system have a fixed, valid list of classification codes to
point at.

## Why does Frappe need it?
```
Loan Classification records (code + name)
        |
        v
Company > Loan Classification Ranges (module 09) picks a DPD range per code
        |
        v
process_loan_classification job reads a loan's days-past-due, matches it
against those ranges, and stamps the loan with a classification_code
        |
        v
Loan.classification_code  --used by-->  NPA status, provisioning reports
```

## Fields that matter
| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Classification Code | `classification_code` | Data | Required, unique, and is the document's actual name (`"autoname": "field:classification_code"` in `loan_classification.json`) — this is the join key every `Loan Classification Range` row and every `Loan.classification_code` value links back to. |
| Classification Name | `classification_name` | Data | Required, display label only; carried alongside the code wherever it's looked up (e.g. `loan.py`'s `get_classification_code_and_name` returns both together) but never itself matched against. |

## Worked example
Bangladesh Bank's BRPD circulars define five standard classification buckets.
Used as an illustrative example only:

| classification_code | classification_name |
|---|---|
| STD | Standard |
| SMA | Special Mention Account |
| SS | Sub-Standard |
| DF | Doubtful |
| BL | Bad/Loss |

> **Confirm before use:** these codes and any DPD thresholds you attach to them via the Company "Loan Classification Ranges" table (module 09) must be checked against the current BRPD circular in force at Bangladesh Bank before go-live. Do not treat the numbers in this guide as regulatory truth — they are illustrative only.

How a loan actually gets one of these codes, read from `loan.py`'s
`get_classification_code_and_name(days_past_due, company, is_written_off)`
(`loan_management/doctype/loan/loan.py:1749-1770`): it fetches all
`Loan Classification Range` rows for that `company`, sorted by `min_dpd_range`,
and returns the first row where `min_dpd_range <= days_past_due <= max_dpd_range`
and the row's `is_written_off` flag matches the loan's own write-off state — no
match means the loan gets an empty classification, not an error.

## What to create now
Create these 5 records (classification_code / classification_name):
1. `STD` / `Standard`
2. `SMA` / `Special Mention Account`
3. `SS` / `Sub-Standard`
4. `DF` / `Doubtful`
5. `BL` / `Bad/Loss`

Nothing else goes on this form. The DPD ranges and provisioning percentages for
these codes are set later, on the Company doctype's Lending tab (module 09) —
this module only creates the vocabulary those settings will point at.

## Why this matters later
This module's codes → Company's `loan_classification_ranges` and
`irac_provisioning_configuration` child tables (module 09) attach DPD ranges and
provisioning rates to each code → the `process_loan_classification` background
job reads those ranges against each loan's days-past-due and stamps
`Loan.classification_code` → that value drives NPA status and provisioning
reporting.

## Source
- `apps/lending/lending/loan_management/doctype/loan_classification/loan_classification.json`
- `apps/lending/lending/loan_management/doctype/process_loan_classification/process_loan_classification.py`
- `apps/lending/lending/loan_management/doctype/loan/loan.py:1749-1770` (`get_classification_code_and_name`)
