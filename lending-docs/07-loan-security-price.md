# Module 07 — Loan Security Price

## Navigation
URL:         /app/loan-security-price
Awesome bar: "Loan Security Price"

## What is it?
A dated valuation record for one specific pledged security (a `Loan Security`
record, e.g. a fixed deposit). Instead of storing "the value" as one number on
the security itself, the app keeps a history of price records, each valid for
a bounded time window. Whenever code needs "what is this security worth right
now", it looks up the price record whose window covers the current moment.

## Why does Frappe need it?
```
Loan Security "FD-2026-0001"  --(has many, over time)-->  Loan Security Price rows
                                                            [valid_from, valid_upto] -> price

lookup(security, as_of_time) -> the one row whose window contains as_of_time
                              -> feeds: LTV checks, sanctioned-limit recalculation,
                                 loan security shortfall checks
```
A single static price field wouldn't let the system answer "what was this FD
worth on 15 March" after it's since been revalued — the time-boxed rows do.

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Loan Security | `loan_security` | Link → Loan Security | Which security this price row belongs to. Entered by you. |
| Loan Security Price | `loan_security_price` | Currency | The value for this window. Read via `get_loan_security_price()` (`loan_security_price.py:81-93`) by disbursement, security assignment, and loan application code. |
| Valid From | `valid_from` | Datetime | Start of the window. **Mandatory**, not optional — `validate_dates()` (`loan_security_price.py:63`) throws if `valid_from > valid_upto`, and separately rejects any new row whose `[valid_from, valid_upto]` overlaps an existing row for the same security (`loan_security_price.py:66-79`). |
| Valid Upto | `valid_upto` | Datetime | End of the window. **Also mandatory** — there is no "open-ended, still current" state in this build; every row must have both ends set, and the next revaluation is a brand new row with its own bounded window. |
| Loan Security Type | `loan_security_type` | Link → Loan Security Type (read-only) | Auto-filled: `fetch_from = "loan_security.loan_security_type"`. You never enter this. |
| Loan Security Name | `loan_security_name` | Data (read-only) | Auto-filled: `fetch_from = "loan_security.loan_security_name"`. You never enter this. |

> **Not in this build:** there's no "no end date" convenience — I initially expected an
> open row you just update in place. Instead `valid_upto` is required and enforced
> non-overlapping, confirmed by reading the field metadata (`read_only`/`fetch_from`
> are both `null` for `valid_from`/`valid_upto`, i.e. genuinely free-entry, mandatory
> fields) and the overlap-rejection SQL in `validate_dates()`.

One side effect worth knowing before you create these: `on_update` and `on_trash`
both call `update_sanctioned_limits_for_security_holders()`
(`loan_security_price.py:33-52`), which finds every applicant with this exact
security currently pledged (via `Loan Security Assignment` + `Pledge`, status
`Pledged`, submitted) and recalculates their `Sanctioned Loan Amount` (module 11).
Saving or deleting a price row is not inert — it can change someone's sanctioned
limit immediately.

## Worked example
Security: `FD-2026-0001` (a fixed deposit, from module 06), original face value
BDT 500,000.

- Row 1: `valid_from = 2026-01-01 00:00:00`, `valid_upto = 2026-06-30 23:59:59`,
  `loan_security_price = 500,000`.
- The FD is revalued after accrued interest. Row 2:
  `valid_from = 2026-07-01 00:00:00`, `valid_upto = 2026-12-31 23:59:59`,
  `loan_security_price = 512,500`.

Calling `get_loan_security_price("FD-2026-0001", "2026-08-15")` scans for a row
where `valid_from <= 2026-08-15 <= valid_upto` — that's Row 2, so it returns
`512,500`. Calling it with `2026-03-01` returns Row 1's `500,000`. Trying to
insert a Row 3 with `valid_from = 2026-06-15` (inside Row 1's window) would be
rejected by the overlap check.

## What to create now
One record:
- `loan_security`: `FD-2026-0001`
- `loan_security_price`: `500000`
- `valid_from`: today's date, `00:00:00`
- `valid_upto`: pick a real review-cycle end date (e.g. 6 months out) — leaving
  it far in the future is fine, but it cannot be blank.

`loan_security_type` and `loan_security_name` will fill themselves in from the
`loan_security` link — do not try to type them.

## Why this matters later
This module → `get_loan_security_price()` is called by Loan Disbursement, Loan
Security Assignment, and Loan Application (all deferred, transactional) to
value collateral at the moment of the transaction → the same lookup feeds
Loan Security Shortfall, which compares current security value against
outstanding loan amount to detect under-collateralized loans.

## Source
- `apps/lending/lending/loan_management/doctype/loan_security_price/loan_security_price.json`
- `apps/lending/lending/loan_management/doctype/loan_security_price/loan_security_price.py`
