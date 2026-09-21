# Module 06 — Loan Security

## Navigation
URL:         /app/loan-security
Awesome bar: "Loan Security"

## What is it?
A single register of one physical or financial item a borrower can pledge as
collateral — one Fixed Deposit certificate, one property, one lot of shares.
It is not the pledge itself; it just says "this asset exists, it is worth this
much, and this much of it is currently tied up." The actual act of pledging it
against a loan happens later, in Loan Security Assignment (deferred,
transactional).

## Why does Frappe need it?
```
Loan Security Type (haircut %, LTV %)      Original Security Value (you enter)
              │  fetch_from                            │
              ▼                                        ▼
      Loan Security record  ──validate()──>  Available = Original - Utilized
                                                        │
                              Loan Security Assignment submitted
                                                        │
                                                        ▼
                              Utilized ↑, Available ↓ (on this same record)
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Loan Security Name | `loan_security_name` | Data | User-entered. The identifying name/description of this specific asset. |
| Loan Security Type | `loan_security_type` | Link → Loan Security Type | User-entered. Which category (module 05) this asset belongs to — this is what drives the two fetched fields below. |
| Loan Security Code | `loan_security_code` | Data | User-entered. Free-text internal code. |
| Haircut % | `haircut` | Percent | `fetch_from: loan_security_type.haircut` — auto-filled from the linked Loan Security Type when you pick it, not typed from scratch. Editable afterward since it isn't marked read-only. |
| Loan To Value Ratio | `loan_to_value_ratio` | Percent | `fetch_from: loan_security_type.loan_to_value_ratio` — same as above, auto-filled from the type. |
| Original Security Value | `original_security_value` | Currency | User-entered. The declared value of the asset when you register it. This is the only one of the three value fields you actually type. |
| Available Security Value | `available_security_value` | Currency | System-computed, `read_only: 1`. Recalculated every time the document is validated: `available = original - utilized` (`loan_security.py:37-39`). Also directly overwritten by `update_loan_securities_values()` in `loan_security_assignment.py:181-251` whenever a Loan Security Assignment against this asset is submitted or reversed. |
| Utilized Security Value | `utilized_security_value` | Currency | System-computed, `read_only: 1`. Only ever written by that same `update_loan_securities_values()` function — it never comes from a form. |
| Disabled | `disabled` | Check | User-entered, default `0`. Standard "stop offering this for new pledges" switch. |

## Worked example
You register a Fixed Deposit worth ৳500,000 as a Loan Security.

At creation (nothing pledged against it yet):
- `original_security_value` = 500,000 (typed)
- `utilized_security_value` = 0 (system default)
- `available_security_value` = 500,000 - 0 = 500,000 (computed by `validate()`)

Later, a Loan Security Assignment pledges ৳180,000 worth of this FD against a
loan and gets submitted. `update_loan_securities_values()` runs the "utilized
increased" branch (`loan_security_assignment.py:224-234`): since
180,000 + 0 ≤ 500,000, it sets

- `new_utilized_security_value` = 0 + 180,000 = 180,000
- `new_available_security_value` = 500,000 - 180,000 = 320,000

and writes both directly onto this Loan Security record with
`frappe.db.set_value(...)` (`loan_security_assignment.py:247-252`) — it does not
go through this doctype's own `validate()` a second time.

If a later assignment tried to pledge more than the remaining 320,000, the code
caps `new_utilized_security_value` at `original_security_value` and the leftover
amount is returned to the caller rather than silently overflowing
(`loan_security_assignment.py:228-231`).

## What to create now
One record, values you actually type:
- Loan Security Name: `FD-2026-0001`
- Loan Security Type: `Fixed Deposit` (must already exist — module 05)
- Loan Security Code: `FD0001`
- Original Security Value: `500000`

Leave Haircut % and Loan To Value Ratio alone — they'll fill in from the Loan
Security Type the moment you select it. Leave Available/Utilized Security Value
blank; they are read-only and will show 500,000 / 0 after save.

## Why this matters later
This module → Loan Security Price (module 07, needed if the security is a
market-priced instrument rather than a fixed value like an FD) → Loan Security
Assignment (deferred, transactional — this is what actually moves the
Utilized/Available numbers) → collateral coverage check on a Loan.

## Source
- `apps/lending/lending/loan_management/doctype/loan_security/loan_security.json`
- `apps/lending/lending/loan_management/doctype/loan_security/loan_security.py`
- `apps/lending/lending/loan_management/doctype/loan_security_assignment/loan_security_assignment.py` (lines 162-254)
