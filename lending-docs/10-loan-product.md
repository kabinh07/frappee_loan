# Module 10 — Loan Product

## Navigation
URL:         /app/loan-product
Awesome bar: "Loan Product"

## What is it?
Loan Product is the template a loan is created from. It fixes the interest
rate, the repayment schedule style, the grace period, which offset sequence
collections follow, and every GL account the loan will post to, before a
single Loan Application exists. Every Loan carries a `loan_product` link back
to one of these records for its whole life.

## Why does Frappe need it?
```
Loan Product (this module)
     │  rate_of_interest, repayment_schedule_type, grace_period_in_days,
     │  loan_charges, collection_offset_sequence_for_*, GL accounts
     ▼
Loan Application  (deferred, transactional)
     │  copies rate_of_interest down if the applicant doesn't override it
     ▼
Loan  (deferred, transactional)
     │  reads grace_period_in_days, bpi_recovery_method, days_past_due_threshold_for_npa
     ▼
Loan Disbursement / Loan Repayment Schedule / Loan Interest Accrual
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Product Code | `product_code` | Data | The record's name (`autoname: "field:product_code"`) — this is what other doctypes link to, not Product Name. |
| Product Name | `product_name` | Data | Display label only. |
| Rate of Interest (%) Yearly | `rate_of_interest` | Percent | If a Loan is created with this product and the Loan itself has no rate set, `loan.py:552-553` copies this value onto the Loan via `frappe.get_cached_value`. |
| Loan Category | `loan_category` | Link → Loan Category | Links to module 02. Purely classificatory on this doctype — no `.py` file branches on it directly; it's used for grouping/reporting. |
| Is Term Loan | `is_term_loan` | Check | Gates whether `repayment_schedule_type` is shown/required at all (`depends_on: is_term_loan`). |
| Repayment Schedule Type | `repayment_schedule_type` | Select | Options: *(blank)*, Monthly as per repayment start date, Pro-rated calendar months, Monthly as per cycle date, Line of Credit, Flat Interest Rate. Read back off the Loan by `loan_disbursement.py:112,281` and `loan_outstanding_report.py:218` — "Line of Credit" specifically skips fixed-schedule disbursement logic. |
| Cyclic Day Of the Month | `cyclic_day_of_the_month` | Int | Only mandatory/shown when `repayment_schedule_type == "Monthly as per cycle date"` (`depends_on` / `mandatory_depends_on` in the JSON). |
| Repayment Date On | `repayment_date_on` | Select | Options: *(blank)*, Start of the next month, End of the current month. Only shown when `repayment_schedule_type == "Pro-rated calendar months"`. |
| No Interest Accrual Till Month End | `no_interest_till_month_end` | Check | Only shown when `repayment_schedule_type == "Line of Credit"`. Per its own description: delays interest accrual from the disbursement date to the 1st of the following month. |
| Grace Period in Days | `grace_period_in_days` | Int | Read by `loan_interest_accrual.py:620` via `frappe.get_value(..., cache=True)` — the number of days after due date before penalty starts accruing. |
| Penalty Interest Rate (%) | `penalty_interest_rate` | Percent | Per its own JSON description: charged daily on the pending amount once a repayment is delayed. |
| How to Handle Advance Payments | `advance_payment_handling` | Select | Options: Reduce Tenure (default), Reduce EMI. Read by `loan_restructure.py:966-969` (`get_advance_payment_handling`) — decides whether an advance payment shortens the loan or lowers the EMI. |
| Days Past Due Threshold for NPA | `days_past_due_threshold_for_npa` | Int | Bulk-read across all products by `loan.py:1778` (`frappe.get_all("Loan Product", fields=[..., "days_past_due_threshold_for_npa"])`) — this is the per-product DPD cutoff that flags a loan Non-Performing. |
| Validate Normal Repayment | `validate_normal_repayment` | Check | Default 0. |
| BPI Recovery Method | `bpi_recovery_method` | Select | Options: *(blank)*, Upfront Deduction (default), Amortized Over Tenure, Add to First EMI, Add to Last EMI. Read by `loan_disbursement.py:810-814` and `loan_repayment_schedule.py:430-431` — controls how Broken Period Interest is recovered from the borrower. |
| BPI Treatment | `bpi_treatment` | Select | Options: On top of first EMI, Adjust within the EMI amount. Only shown when `bpi_recovery_method == "Add to First EMI"`. |
| Auto Write Off Amount | `write_off_amount` | Currency | Per its own JSON description: a Loan Write Off is auto-created on closure request if the pending amount is below this. |
| Excess Amount Acceptance Limit | `excess_amount_acceptance_limit` | Float | Per its own JSON description: excess repayment limit accepted during loan closure. |
| Sanctioned Amount Tolerance (%) | `sanctioned_amount_tolerance_percentage` | Percent | Per its own JSON description: how far a new loan may exceed the applicant's `Sanctioned Loan Amount` limit (module 11) before being blocked. |
| Min days between Disbursement and first Repayment | `min_days_bw_disbursement_first_repayment` | Int | Only mandatory when `is_term_loan` is checked **and** `repayment_schedule_type == "Monthly as per cycle date"`. |
| Loan Charges | `loan_charges` | Table → Loan Charges | Each row: `charge_type` (Link → Item), `charge_based_on` (Select: Percentage / Fixed Amount), `amount`, `percentage`, plus a set of Account links for where each charge posts. These become the default charge set applied at disbursement. |
| Loan Partners | `loan_partners` | Table MultiSelect → Loan Product Loan Partner | Each row is just `loan_partner` (Link → Loan Partner, module 08) — the set of co-lending partners this product is allowed to be booked under. |
| Collection Offset Sequence for Standard/Sub Standard/Written Off Asset, and for Settlement Collection | `collection_offset_sequence_for_standard_asset` etc. (4 fields) | Link → Loan Demand Offset Order | Links to module 04. These override, per-product, the company-wide defaults of the same name set in module 09 (Company Lending tab) — same fieldnames, different doctype. |
| *(GL wiring, ~24 fields)* | `payment_account`, `loan_account`, `interest_income_account`, `penalty_income_account`, `disbursement_account`, `interest_waiver_account`, `penalty_waiver_account`, `suspense_interest_income`, `suspense_collection_account`, `interest_receivable_account`, `penalty_receivable_account`, `security_deposit_account`, `interest_accrued_account`, `broken_period_interest_recovery_account`, `additional_interest_*` (5 fields), `penalty_accrued_account`, `penalty_suspense_account`, `write_off_account`, `write_off_recovery_account`, `subsidy_adjustment_account`, `customer_refund_account` | Link → Account | All out of scope for this guide — standard chart-of-accounts wiring, one field per GL posting point. Set these up with your accountant against your Company's chart of accounts. |

> **Not in this build:** `maximum_loan_amount` exists on the JSON but nothing
> in `loan_management/**/*.py` reads it outside of the doctype's own generated
> type stub — no validation currently enforces it against the Loan Application
> amount in this build. Don't rely on it as a hard cap.

## Worked example
Product "Personal Loan - Standard EMI": `rate_of_interest = 15` (yearly),
`is_term_loan` checked, `repayment_schedule_type = "Monthly as per repayment
start date"`, `grace_period_in_days = 3`.

This module doesn't compute a schedule — that's Loan Repayment Schedule's job
(deferred, transactional). What these settings *imply*, for a principal of
BDT 300,000:

- Yearly rate 15% → monthly rate = 15 / 12 = **1.25% per month**.
- One month's simple interest on the full principal, before any principal is
  repaid: 300,000 × 1.25% = **BDT 3,750**.
- `grace_period_in_days = 3` means if the EMI due date is the 5th and the
  borrower pays on the 7th, no penalty interest accrues yet — `penalty_interest_rate`
  only starts counting from day 4 past due.

The actual EMI amount (principal + interest, amortized over N months) is
computed by Loan Repayment Schedule at Loan creation time, not here.

## What to create now
Create one Loan Product record:
- `product_code`: `PL-STD`
- `product_name`: `Personal Loan - Standard EMI`
- `loan_category`: `Personal Loan` (module 02)
- `is_term_loan`: checked
- `rate_of_interest`: `15`
- `repayment_schedule_type`: `Monthly as per repayment start date`
- `grace_period_in_days`: `3`
- `loan_partners`: add a row for `ABC Bank Co-lending` (module 08)
- `collection_offset_sequence_for_standard_asset`: `Standard EMI Offset` (module 04)
- `loan_charges`: one row, `charge_based_on = Percentage`, `percentage = 1` (a 1% processing fee)

Leave every `*_account` field for your accounting setup pass with the Company's
chart of accounts — they're not needed to exercise the lending workflow itself.

## Why this matters later
Loan Product → Loan Application (deferred) copies the rate and schedule type
down → Loan (deferred) inherits `grace_period_in_days`, `bpi_recovery_method`,
and `days_past_due_threshold_for_npa` for the rest of its life → those three
values directly drive Loan Interest Accrual, Loan Disbursement's BPI handling,
and eventual NPA/classification flags on Days Past Due Log.

## Source
- `apps/lending/lending/loan_management/doctype/loan_product/loan_product.json`
- `apps/lending/lending/loan_management/doctype/loan_product/loan_product.py`
- `apps/lending/lending/loan_management/doctype/loan/loan.py` (lines 198, 552-553, 1778)
- `apps/lending/lending/loan_management/doctype/loan_disbursement/loan_disbursement.py` (lines 93, 112, 281, 810-814)
- `apps/lending/lending/loan_management/doctype/loan_repayment_schedule/loan_repayment_schedule.py` (lines 430-431)
- `apps/lending/lending/loan_management/doctype/loan_restructure/loan_restructure.py` (lines 955, 966-969)
- `apps/lending/lending/loan_management/doctype/loan_interest_accrual/loan_interest_accrual.py` (line 620)
- `apps/lending/lending/loan_management/report/loan_outstanding_report/loan_outstanding_report.py` (lines 164-165, 203, 218-222)
