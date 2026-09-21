# Module 11 — Sanctioned Loan Amount

## Navigation
URL:         /app/sanctioned-loan-amount
Awesome bar: "Sanctioned Loan Amount"

## What is it?
A single record that caps how much one applicant (an Employee, Member, or
Customer) can owe a given Company across all their loans at once. It has no
workflow and no child tables — it's a flat ceiling, entered once by a credit
officer, that the loan and loan application code checks against.

## Why does Frappe need it?
```
Sanctioned Loan Amount record (applicant + company -> limit, set once)
                |
                v
New Loan / Loan Application for that applicant
                |
     loan_amount + applicant's other outstanding loans  --compared to-->  limit x (1 + tolerance%)
                |
                v
      over limit -> frappe.throw(), save/submit blocked
      within limit -> proceeds
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Applicant Type | `applicant_type` | Select (Employee / Member / Customer) | Sets which doctype the `applicant` field links to. Used as the exact-match filter in both lookup calls below. |
| Applicant | `applicant` | Dynamic Link (target driven by `applicant_type`) | Identifies whose limit this is. `get_sanctioned_amount_limit()` in `loan.py:866` matches on this field exactly (no wildcard/fallback) — one record per applicant per company. |
| Company | `company` | Link -> Company | Second half of the lookup key. A limit is scoped per company: the same applicant could have different limits at two companies. |
| Sanctioned Amount Limit | `sanctioned_amount_limit` | Currency | The ceiling itself. Read (never written) by `get_sanctioned_amount_limit()`, then used in `check_sanctioned_amount_limit()` in both `loan.py:557` and `loan_application.py:182` to hard-stop the document if exceeded — see Worked example. |

All four fields are `reqd: 1` — Frappe won't let you save a record with any of
them blank.

## Worked example

Set up: `applicant_type = "Customer"`, `applicant = "Test Customer"`,
`company = "Polygon Bank Private Limited Company"` (this build's actual default
company — confirmed via `bench --site lending.localhost execute
frappe.db.get_value`), `sanctioned_amount_limit = BDT 500,000`.

Now someone creates a **Loan Application** for that same customer/company for
BDT 480,000, and the applicant already has an existing submitted, non-closed
Loan with BDT 60,000 still outstanding (`total_payment` net of what's already
paid/written off — see `get_total_loan_amount()` in `loan.py:795`).

The Loan Product used has `sanctioned_amount_tolerance_percentage = 5`.

This is exactly what `check_sanctioned_amount_limit()` computes, line for line
(`loan.py:557-572`, identical logic duplicated in
`loan_application.py:182-197`):

```
allowed_limit = sanctioned_amount_limit * (1 + tolerance% / 100)
              = 500,000 * 1.05
              = 525,000

requested_total = loan_amount + total_loan_amount (existing outstanding)
                 = 480,000 + 60,000
                 = 540,000

540,000 > 525,000  ->  frappe.throw("Sanctioned Amount limit crossed for Customer Test Customer")
```

The Loan Application fails validation and cannot be saved. Drop the new request
to BDT 440,000 instead: `440,000 + 60,000 = 500,000`, which is `<= 525,000` —
validation passes.

If no "Sanctioned Loan Amount" record exists for that applicant/company pair at
all, `get_sanctioned_amount_limit()` returns `None`, the `if sanctioned_amount_limit:`
check is falsy, and the whole limit check is skipped — an applicant with no
record has no ceiling.

## What to create now

Create one record:
- Applicant Type: `Customer`
- Applicant: your test customer (create one in Customer if you don't have one yet — this doctype doesn't create it for you)
- Company: `Polygon Bank Private Limited Company` (or whatever `bench --site lending.localhost execute frappe.db.get_value --args '["Company", {}, "name"]'` returns on your site)
- Sanctioned Amount Limit: `500000`

## Why this matters later

This module -> every **Loan Application** and every **Loan** created for that
applicant/company (both deferred, transactional modules) -> `validate()` on
each calls `check_sanctioned_amount_limit()` unconditionally, which also reads
`sanctioned_amount_tolerance_percentage` off whatever **Loan Product** (module
10) is selected on the application/loan — so the effective ceiling isn't just
this record's number, it's this number stretched by that product's tolerance.

> **Not in this build:** there's no bulk/mass "set sanctioned limits" tool and
> no report showing whose limit is closest to being breached — you'd need to
> query the doctype directly for that.

## Source
- `apps/lending/lending/loan_management/doctype/sanctioned_loan_amount/sanctioned_loan_amount.json` (fields, autoname `LM-SLA-.####`)
- `apps/lending/lending/loan_management/doctype/loan/loan.py:130-150` (`validate()` calling `check_sanctioned_amount_limit()`), `:557-572` (`check_sanctioned_amount_limit()`), `:795-814` (`get_total_loan_amount()`), `:866-871` (`get_sanctioned_amount_limit()`)
- `apps/lending/lending/loan_management/doctype/loan_application/loan_application.py:76-88` (`validate()`), `:182-197` (`check_sanctioned_amount_limit()`)
- Live check: `bench --site lending.localhost execute frappe.db.get_value --args '["Company", {}, ["name", "default_currency"]]'` -> `["Polygon Bank Private Limited Company", "BDT"]`
