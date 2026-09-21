# Module 09 — Company (Lending Tab)

## Navigation
URL:         /app/company (open your existing Company record, then the "Lending" tab)
Awesome bar: "Company"

> **Not in this build (as a separate doctype):** there is no "Lending Settings"
> master covering these fields. They are custom fields added to the core
> Company doctype by `apps/lending/lending/install.py`. If the public docs
> describe a dedicated settings doctype for this, that does not match this
> installed build.

## What is it?
This is where company-wide lending defaults live: how interest is day-counted,
how often it accrues, which DPD threshold triggers an automatic write-off, and
— most importantly — the DPD-to-classification lookup table and the
provisioning-rate table every loan's risk bucket gets checked against.

## Why does Frappe need it?
```
days_past_due (per Loan) --lookup in--> loan_classification_ranges (this module)
                                         |
                                         v
                              classification_code / classification_name
                                         |
                                         v
                    irac_provisioning_configuration (this module, keyed by
                    classification_code + security_type) --> provision_rate
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Restructure Limit % (Overall) | `loan_restructure_limit` | Percent | Fallback % of outstanding principal a Branch may restructure, used only when the Branch record itself has no limit set. Read in `process_loan_restructure_limit.py:38-44`. |
| Watch Period Post Loan Restructure (In Days) | `watch_period_post_loan_restructure_in_days` | Int | How many days a loan stays in a post-restructure watch period. Read in `loan.py:1244` and `loan_restructure.py:591`. |
| Interest Day-Count Convention | `interest_day_count_convention` | Select: `Actual/365`, `Actual/Actual`, `30/365`, `30/360`, `Actual/360` | Picks the interest formula branch. `loan_interest_accrual.py:1051` — `Actual/365`/`30/365` take one branch; `30/360`/`Actual/360` take the other (`:1053`). |
| Minimum days between Disbursement date and first Repayment date | `min_days_bw_disbursement_first_repayment` | Int | Company-level fallback used only when a Loan Product (module 10) leaves its own same-named field blank — `loan_product.py:94-101`. Enforced at disbursement in `loan_disbursement.py:390-401` and `loan.py:2101-2113`. |
| Loan Accrual Frequency | `loan_accrual_frequency` | Select: `Daily`, `Weekly`, `Monthly` | How often interest accrual runs for this company's loans. `loan_interest_accrual.py:1152` (`get_loan_accrual_frequency`), `:404` (`get_accrual_frequency_breaks`), `:477` (`is_posting_date_accrual_day`). |
| Enable Loan Accounting | `enable_loan_accounting` | Check | Gates whether GL entries are posted for this company's loans at all — `loan_management/utils.py:322`. |
| Enable async reversal of GL for future demand and accruals | `enable_async_gl_reversal` | Check | Gates whether GL reversal of future demand/accrual entries is queued asynchronously — `loan_management/utils.py:329-336`. |
| Async GL Reversal Start Date | `async_gl_reversal_start_date` | Date | Cutoff date the async-reversal logic applies from; only read when `enable_async_gl_reversal` is checked — `utils.py:336`. |
| Collection Offset Logic Based On | `collection_offset_logic_based_on` | Select: `NPA Flag`, `Days Past Due` | **Not wired up in this build.** `grep -rn "collection_offset_logic_based_on"` across the whole app finds it only in `install.py` — no other file reads it. Setting it currently has no effect. |
| Days Past Due Threshold | `days_past_due_threshold` | Int | **Not wired up in this build.** Only reference outside `install.py` is a test fixture (`tests/test_utils.py:1057`) — no production code reads it. |
| Days Past Due Threshold For Auto Write Off | `days_past_due_threshold_for_auto_write_off` | Int | DPD value past which a loan becomes eligible for automatic write-off — read in `loan.py:1786`. |
| Collection Offset Sequence for Standard / Sub Standard / Written Off Asset / Settlement Collection | `collection_offset_sequence_for_*` (4 fields) | Link → Loan Demand Offset Order (module 04) | Company-level default offset order per classification bucket. Loan Product (module 10) falls back to these when its own field of the same name is blank (`loan_product.py:37,133`). `loan_repayment.py:2527` picks the matching one by bucket name when posting a repayment. |
| Loan Classification Ranges | `loan_classification_ranges` (Table → Loan Classification Range) | Table | The actual DPD→bucket lookup. `loan.py:1748` `get_classification_code_and_name(days_past_due, company, is_written_off)` reads these rows filtered by `parent=company`, and returns the first row where `min_dpd_range <= days_past_due <= max_dpd_range` and `is_written_off` matches. Row fields: `classification_code` (Link → Loan Classification, module 03), `classification_name`, `min_dpd_range` (Int), `max_dpd_range` (Int), `is_written_off` (Check). Duplicate ranges are rejected at save via `overrides/company.py:6-13`. |
| IRAC Provisioning Configuration | `irac_provisioning_configuration` (Table → Loan IRAC Provisioning Configuration) | Table | Only validated for duplicate `(classification_code, security_type)` pairs at save (`overrides/company.py:15-24`). **No report or scheduled job in this build actually computes a provisioning amount from it** — grepping the whole app for `irac_provisioning_configuration` outside `install.py`/patches/locale files turns up nothing else. Row fields: `provision_rate` (Percent), `classification_code` (Link → Loan Classification), `classification_name`, `security_type` (Select: `Secured`, `Unsecured`, `Semi-Secured`). |

Note: `classification_code` on both child tables is a plain `Link` to Loan
Classification (module 03), which itself is just two free-text fields
(`classification_code`, `classification_name` — see module 03). Nothing in the
schema forces codes like STD/SMA/SS/DF/BL; that's a naming convention you
choose, not an enforced enum.

## Worked example
Suppose you've created five Loan Classification records (module 03) using
codes that mirror Bangladesh Bank's BRPD asset-classification categories —
Standard (STD), Special Mention Account (SMA), Sub-Standard (SS), Doubtful
(DF), Bad/Loss (BL) — and then filled this Company's two tables like this:

**Loan Classification Ranges**

| classification_code | classification_name | min_dpd_range | max_dpd_range | is_written_off |
|---|---|---|---|---|
| STD | Standard | 0 | 30 | 0 |
| SMA | Special Mention Account | 31 | 60 | 0 |
| SS | Sub-Standard | 61 | 90 | 0 |
| DF | Doubtful | 91 | 180 | 0 |
| BL | Bad/Loss | 181 | 99999 | 0 |

**IRAC Provisioning Configuration** (Secured facilities only, for this example)

| classification_code | classification_name | security_type | provision_rate |
|---|---|---|---|
| STD | Standard | Secured | 1% |
| SMA | Special Mention Account | Secured | 5% |
| SS | Sub-Standard | Secured | 20% |
| DF | Doubtful | Secured | 50% |
| BL | Bad/Loss | Secured | 100% |

> **Confirm before use:** the DPD ranges and provisioning rates above are
> illustrative only. Check the BRPD circular currently in force at Bangladesh
> Bank before setting these on a live Company record.

Now take a Loan with `days_past_due = 75`, outstanding principal
**BDT 500,000**, secured.

1. `get_classification_code_and_name(75, company, is_written_off=0)` scans the
   ranges in `min_dpd_range` order and finds `61 <= 75 <= 90` on the SS row →
   returns `classification_code="SS"`, `classification_name="Sub-Standard"`.
2. Looking up `irac_provisioning_configuration` for `classification_code="SS"`,
   `security_type="Secured"` gives `provision_rate = 20%`.
3. Provisioning = `500,000 × 20% = BDT 100,000`.

Step 3 is arithmetic you'd have to do yourself (in a custom report or script)
— as noted above, this build stores and validates the provisioning table but
does not compute a provisioning figure from it anywhere.

## What to create now
On your Company record's Lending tab, set:
- `interest_day_count_convention` = `Actual/365` (a config choice — pick
  whichever your interest agreements are actually written against; nothing in
  the code prefers one over another beyond the two-branch split noted above)
- `loan_accrual_frequency` = `Monthly`
- `days_past_due_threshold_for_auto_write_off` = a DPD value your policy defines
- `collection_offset_sequence_for_standard_asset` and the other three
  offset-sequence fields = the matching Loan Demand Offset Order records from
  module 04
- `loan_classification_ranges` = the 5 BRPD-style rows above (against your
  confirmed current BRPD thresholds, not the illustrative ones)
- `irac_provisioning_configuration` = the matching provisioning rows above
  (again, confirmed rates, not illustrative ones)

Leave `collection_offset_logic_based_on` and `days_past_due_threshold` alone —
setting them currently does nothing in this build.

## Why this matters later
This module → the deferred `process_loan_classification` background job reads
`loan_classification_ranges` through `get_classification_code_and_name()` to
set every Loan's classification/NPA flag → that classification drives which
Loan Demand Offset Order applies to each repayment → and, if you build a
provisioning report against `irac_provisioning_configuration` yourself, drives
your regulatory provisioning numbers.

## Source
- `apps/lending/lending/install.py:9-177` (all Company custom fields)
- `apps/lending/lending/loan_management/doctype/loan/loan.py:1244, 1748-1767, 1786, 2101-2113`
- `apps/lending/lending/loan_management/doctype/loan_restructure/loan_restructure.py:591`
- `apps/lending/lending/loan_management/doctype/loan_interest_accrual/loan_interest_accrual.py:404-424, 477-480, 1041-1079, 1152-1164`
- `apps/lending/lending/loan_management/doctype/loan_product/loan_product.py:37, 94-101, 133`
- `apps/lending/lending/loan_management/doctype/loan_disbursement/loan_disbursement.py:390-401`
- `apps/lending/lending/loan_management/doctype/loan_repayment/loan_repayment.py:2527`
- `apps/lending/lending/loan_management/doctype/process_loan_restructure_limit/process_loan_restructure_limit.py:38-44`
- `apps/lending/lending/loan_management/utils.py:322, 329-336`
- `apps/lending/lending/overrides/company.py:6-24`
