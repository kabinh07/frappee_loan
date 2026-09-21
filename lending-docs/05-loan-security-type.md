# Module 05 — Loan Security Type

## Navigation
URL:         /app/loan-security-type
Awesome bar: "Loan Security Type"

## What is it?
A category of collateral — Fixed Deposit, Gold, Shares, Property, whatever your
institution accepts as security. It doesn't record an actual pledged item; it
records the two percentages that apply to every item of that category: how much
of its market value you discount for risk, and how far a loan against it can go
before you need to worry.

## Why does Frappe need it?
```
Loan Security Type (haircut %, LTV %)
        |
        v
Loan Security (a specific item of that type)  ->  Loan Security Price (its market value over time)
        |
        v
"usable collateral value" for disbursement, or a shortfall trigger, depending on context
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Haircut % | `haircut` | Percent | Discounts the security's market value down to a usable value **at disbursement time**. In `loan_disbursement.py:965-971` (`get_total_pledged_security_value`, `on_shortfall_check=False` branch): `security_value += price * qty * (100 - haircut) / 100`. Also the fallback haircut in `loan_security_assignment.py:120-126` and `loan_security.py:55-62` when the individual Loan Security record doesn't override it. |
| Loan To Value Ratio | `loan_to_value_ratio` | Percent | Used for a *different* calculation: detecting an ongoing shortfall. In the **same function**, `on_shortfall_check=True` branch (`loan_disbursement.py:951-966`): `security_value += price * qty * loan_to_value_ratio / 100`, then compared against the outstanding loan amount in `loan_security_shortfall.py`. `get_ltv_ratio()` (`loan_security_shortfall.py:238-241`) reads it straight off this doctype via the security's `loan_security_type`. |
| Loan Security Type | `loan_security_type` | Data | The name/category itself (e.g. "Fixed Deposit"). Autoname field — this is what other doctypes Link against. |
| Disabled | `disabled` | Check | Standard enable/disable toggle; no special code path found beyond the usual "don't show in Link filters" behavior. |

> **Not in this build:** don't assume `haircut` and `loan_to_value_ratio` are two
> names for the same "safety margin" concept — they are not interchangeable and
> the code never averages or combines them. The same function
> (`get_total_pledged_security_value`) picks **one or the other** by an
> `on_shortfall_check` flag, never both.

## Worked example
Fixed Deposit worth BDT 500,000 market price, `haircut = 10`, `loan_to_value_ratio = 90`.

**At disbursement** (haircut path):
```
security_value = 500,000 * (100 - 10) / 100 = 500,000 * 0.90 = BDT 450,000
```
This is the usable collateral value that gets added toward `maximum_loan_value`
for how much can actually be disbursed against this security.

**On a shortfall check** (LTV path — same numbers, different formula, coincidentally the same result here because haircut and LTV happen to both be complements of 10% in this example):
```
security_value = 500,000 * 90 / 100 = BDT 450,000
```
This value is compared against the loan's current outstanding amount; if the
outstanding amount exceeds it, a Loan Security Shortfall record gets raised
against the loan. Note this is only the same number as the disbursement
calculation because `100 - haircut` and `loan_to_value_ratio` happen to both
equal 90 in this example — set `haircut = 15` and `loan_to_value_ratio = 90`
and the two calculations diverge (BDT 425,000 vs BDT 450,000).

## What to create now
One record:
- `loan_security_type` = "Fixed Deposit"
- `haircut` = 10
- `loan_to_value_ratio` = 90
- `disabled` = unchecked

## Why this matters later
This module -> Loan Security (module 06, a specific Fixed Deposit item, can
override the haircut per-item) -> Loan Security Price (module 07, the item's
market value over time) -> `get_total_pledged_security_value()` turns
(price × qty × haircut-or-LTV) into the number that gates how much a Loan can
disburse against pledged collateral, and later whether that Loan trips a
security shortfall.

## Source
- `apps/lending/lending/loan_management/doctype/loan_security_type/loan_security_type.json`
- `apps/lending/lending/loan_management/doctype/loan_disbursement/loan_disbursement.py:938-971`
- `apps/lending/lending/loan_management/doctype/loan_security_assignment/loan_security_assignment.py:118-129`
- `apps/lending/lending/loan_management/doctype/loan_security/loan_security.py:55-62`
- `apps/lending/lending/loan_management/doctype/loan_security_shortfall/loan_security_shortfall.py:215-241`
