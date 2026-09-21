# Lending App — Doctype Inventory & Dependency Order

Generated against the installed build. Every doctype below was read from:

```
docker compose -f lending-compose.yaml --project-name lending exec backend \
  bash -lc 'ls /home/frappe/frappe-bench/apps/lending/lending/loan_management/doctype/'
```

Total doctype folders: 65 (excluding `__init__.py`, `__pycache__`).

Classification flags (`is_submittable`, `istable`) were read from each doctype's own
`<name>.json` via `jq`, not assumed from the name.

## Dependency graph (setup masters only)

Only doctypes with a `Link` field pointing at another *setup master* create an
ordering constraint. Links to core Frappe/ERPNext doctypes (Account, Company,
Address, Branch, Customer) are out of scope for this graph — this app doesn't
control their setup order.

One exception noted explicitly: **Company itself is the true root of the
whole graph** — every module below has a `company` field, and module 09 is
custom fields grafted onto Company directly. It's out of scope for *this*
graph only because Company isn't part of the `lending` app; its own creation
flow (mandatory fields, ERPNext's automatic chart-of-accounts/warehouse/cost-center
bootstrap, and the lending app's one hook on it) is covered separately in
`00a-company-creation.md`, which comes before module 01 in reading order.

```
Loan Security Type ──┬──> Loan Security ──> Loan Security Price
                      └───────────────────────────^
Loan Classification ────────┐
Loan Demand Offset Order ───┼──> Company (Lending tab, custom fields)
                             │
Loan Category ───────────┐  │
Loan Demand Offset Order ┼──┴──> Loan Product
Loan Partner ─────────────┘

Lending Settings, Sanctioned Loan Amount — no edges (roots, ordered last by convenience)
```

No cycles were found.

Resulting order used for `lending-docs/NN-*.md`:

| # | Module | Depends on |
|---|--------|------------|
| 01 | Lending Settings | — |
| 02 | Loan Category | — |
| 03 | Loan Classification | — |
| 04 | Loan Demand Offset Order | — |
| 05 | Loan Security Type | — |
| 06 | Loan Security | Loan Security Type |
| 07 | Loan Security Price | Loan Security, Loan Security Type |
| 08 | Loan Partner | — |
| 09 | Company — Lending Settings (custom fields) | Loan Classification, Loan Demand Offset Order |
| 10 | Loan Product | Loan Category, Loan Demand Offset Order, Loan Partner |
| 11 | Sanctioned Loan Amount | — (root; placed last because it's operationally set right before disbursement) |

> **Not in this build:** module 09 is not a folder under `loan_management/doctype/`
> at all. It is a set of custom fields grafted onto the existing **Company**
> doctype by `apps/lending/lending/install.py` (dict key `"Company"`). If you go
> looking for a "Lending Settings" doctype in the Company sense, you won't find
> one — you'll find it as a "Lending" tab on the Company form. Source:
> `apps/lending/lending/install.py:9-177`.

## Masters / configuration (`is_submittable=0`, `istable=0`, no `process_` prefix)

### True setup masters — get a full module file (listed above)
Lending Settings, Loan Category, Loan Classification, Loan Demand Offset Order,
Loan Security Type, Loan Security, Loan Security Price, Loan Partner, Loan Product,
Sanctioned Loan Amount, and Company's Lending tab.

### System-maintained records — same flags, but not user-configured
These match the `is_submittable=0, istable=0` filter mechanically, but grepping
`apps/lending/lending/**/*.py` shows every one is written by the app's own code
(`loan.py`, a `process_*` job, or a dashboard), never created by a user through
the form. Confirmed via:

```
grep -rln '"<Doctype Name>"' --include=*.py apps/lending/lending | grep -v /doctype/<slug>/
```

All five below also appear verbatim in `hooks.py`'s `ignore_links_on_delete` list
(`apps/lending/lending/hooks.py:253-259`), which only makes sense for pure audit
trails. No module file is written for these — there is nothing to configure.

| Doctype | Written by |
|---|---|
| Days Past Due Log | `loan.py`, `process_loan_classification.py` |
| Loan Freeze Log | `loan.py` |
| Loan Limit Change Log | `loan.py` |
| Loan NPA Log | `loan.py` |
| Loan Restructure Limit Log | `process_loan_restructure_limit.py` |
| Loan Security Shortfall | `process_loan_security_shortfall.py`, `loan_disbursement.py`, `loan_repayment.py` |

`Sanctioned Loan Amount` looked like it belonged in this list (it has a
Pending/Completed-style shape at a glance) but checking `loan.py:865-870` shows
`get_sanctioned_amount_limit()` only ever **reads** it
(`frappe.db.get_value("Sanctioned Loan Amount", ...)`) — nothing in the app ever
creates one. That means it really is a master you set up by hand, so it keeps
its module file (11).

## Transactional documents (`is_submittable=1`, excluding `process_*`)

Deferred — per instruction, not documented until every configuration module above
is done.

Bulk Repayment Log, Loan, Loan Accrual Repost, Loan Adjustment, Loan Application,
Loan Balance Adjustment, Loan Demand, Loan Disbursement, Loan Interest Accrual,
Loan Refund, Loan Repayment, Loan Repayment Repost, Loan Repayment Schedule,
Loan Restructure, Loan Security Assignment, Loan Security Deposit,
Loan Security Release, Loan Transfer, Loan Write Off.

## Child tables (`istable=1`)

Deferred as standalone files. The ones that attach to a configuration master are
documented inline inside that master's module:

| Child table | Embedded in |
|---|---|
| Loan Demand Offset Detail | Module 04 — Loan Demand Offset Order |
| Loan Classification Range | Module 09 — Company Lending tab (`loan_classification_ranges`) |
| Loan IRAC Provisioning Configuration | Module 09 — Company Lending tab (`irac_provisioning_configuration`) |
| Loan Charges | Module 10 — Loan Product |
| Loan Product Loan Partner | Module 10 — Loan Product |
| Loan Partner Shareable | Module 08 — Loan Partner |
| Loan Partner Address | Module 08 — Loan Partner |
| Loan Partner Adhoc Charges Shared | Module 08 — Loan Partner |

Everything else in this bucket (Co-Lender Schedule, Loan Accrual Repost Detail,
Loan Adjustment Detail, Loan Charge Reference, Loan Demand Offset Detail dupes,
Loan Disbursement Charge, Loan Import Details, Loan Repayment Charges,
Loan Repayment Detail, Loan Repayment Repost Cancel Detail,
Loan Repayment Repost Detail, Loan Restructure Charges, Loan Transfer Detail,
Pledge, Prepayment Charges, Proposed Pledge, Repayment Schedule, Unpledge)
belongs to a deferred transactional doctype and will be documented alongside it.

## Background processes (name starts with `process_`)

Deferred — these are Frappe's "submit to run a background job" pattern
(most have `is_submittable=1` themselves), not setup masters.

Process Loan Classification, Process Loan Demand, Process Loan Interest Accrual,
Process Loan Restructure Limit, Process Loan Security Shortfall,
Process Loan Statement of Accounts, Process Loan Statement of Accounts Applicant
(child table of the previous one, `istable=1`).

## Source
- `apps/lending/lending/loan_management/doctype/*/,*.json` (list, flags, fields)
- `apps/lending/lending/install.py` (Company custom fields)
- `apps/lending/lending/hooks.py` (`ignore_links_on_delete`)
- `apps/lending/lending/loan_management/doctype/loan/loan.py`
