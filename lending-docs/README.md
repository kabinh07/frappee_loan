# Frappe Lending — Learning Guide (version-16, this build)

Written against the actual installed source in this stack, not the public docs.
See `00-inventory.md` for the full doctype inventory, classification method, and
how the dependency order below was derived (Link-field graph, no cycles found).

Want the whole path as one page instead of clicking through each module?
See **[WORKFLOW.md](WORKFLOW.md)** — the condensed, in-order build: Loan
Category → Classification → Offset Order → Security → Security Price →
Partner → Company settings → Product → Sanctioned Limit → Application →
Approval → Loan → Disbursement → Repayment, with click paths and this
stack's actual values, linking back here for the full rationale on each step.

Configuration modules 01–11 are in dependency order. Full documentation of the
individual transactional doctypes (Loan Application, Loan, Loan Disbursement,
Loan Repayment, etc.) and background processes (`process_*`) is still deferred
per `00-inventory.md` — module 12 is the exception: a click-by-click runbook
that uses just enough of the transactional flow to get one real loan
disbursed and repaid, so you can see the configuration modules actually working.

| # | Module | Summary | Done |
|---|--------|---------|:---:|
| 00a | [Company Creation](00a-company-creation.md) | The actual prerequisite before any of this: how a Company record gets created, what ERPNext auto-bootstraps on its first save (chart of accounts, warehouses, cost center), and the one (creation-agnostic) hook the lending app has on it. | [ ] |
| 01 | [Lending Settings](01-lending-settings.md) | A settings singleton with two fields — both confirmed inert in this build; nothing reads them. | [ ] |
| 02 | [Loan Category](02-loan-category.md) | A tagging master (name + code) for grouping Loan Products; confirmed no filtering/validation logic reads it yet. | [ ] |
| 03 | [Loan Classification](03-loan-classification.md) | Defines the code/name vocabulary for risk buckets (e.g. BRPD Standard/SMA/Sub-Standard/Doubtful/Bad-Loss) — thresholds live in module 09. | [ ] |
| 04 | [Loan Demand Offset Order](04-loan-demand-offset-order.md) | Sets the row-order priority (Charges/Penalty/Principal/EMI...) a repayment is allocated against; confirmed the "Interest" option alone is a no-op in this build's allocation code. | [ ] |
| 05 | [Loan Security Type](05-loan-security-type.md) | Haircut % and Loan-to-Value % per collateral type; confirmed these feed two different formulas (usable value vs. shortfall check), not one. | [ ] |
| 06 | [Loan Security](06-loan-security.md) | A specific pledgeable asset record; original/available/utilized value fields are system-computed, not user-entered. | [ ] |
| 07 | [Loan Security Price](07-loan-security-price.md) | Time-stamped valuations for a Loan Security; updating a price recalculates dependent Sanctioned Loan Amount records. | [ ] |
| 08 | [Loan Partner](08-loan-partner.md) | Co-lending partner setup (share %, interest split, FLDG fields) — confirmed the FLDG trigger/guarantee fields are validated but never actually consumed by disbursement or repayment code in this build. | [ ] |
| 09 | [Company — Lending Tab](09-company-lending-settings.md) | Company-wide lending defaults added via custom fields (not a standalone doctype): interest day-count convention, accrual frequency, collection-offset defaults, and the two child tables that attach DPD ranges + provisioning rates to each Loan Classification code. Includes the BRPD worked example. | [ ] |
| 10 | [Loan Product](10-loan-product.md) | The template a Loan Application/Loan is created from — interest rate, repayment schedule type, charges, partner shares, per-product offset overrides. Confirmed `maximum_loan_amount` has no enforcement anywhere in this build. | [ ] |
| 11 | [Sanctioned Loan Amount](11-sanctioned-loan-amount.md) | Per-applicant credit limit — confirmed genuinely user-created (unlike its log-shaped siblings) and actively enforced with a hard `frappe.throw` from both Loan and Loan Application `validate()`. | [ ] |
| 12 | [First Loan Walkthrough](12-first-loan-walkthrough.md) | Click-by-click runbook: Loan Application → Approve → Loan → Disbursement → Repayment, using the exact records created in modules 01–11. Confirms the real button locations, status transitions, and which fields are pre-filled vs. must be typed by hand. | [ ] |

## Notable findings across modules

Things that would have misled you if this guide had gone off the public docs
instead of this installed source:

- **Dead/unwired fields exist in this build.** Lending Settings' two fields,
  Loan Category's link, Loan Partner's five FLDG fields, Loan Product's
  `maximum_loan_amount`, and two Company-tab fields (`collection_offset_logic_based_on`,
  `days_past_due_threshold`) are all present on the form but not read by any
  controller. Each is called out with a `> **Not in this build:**` note rather
  than described as if it worked.
- **`haircut` and `loan_to_value_ratio` are not the same safety margin measured
  two ways** — they feed two different formulas depending on whether the code
  is computing usable disbursement value or checking for a security shortfall
  (module 05).
- **The demand-offset "Interest" option is a no-op** — only `Principal` and
  `EMI (Principal + Interest)` rows are actually read by the repayment
  allocation code (module 04).
- **Company's Lending tab is not a doctype** — it's custom fields grafted onto
  the core Company doctype by `install.py`. If you go looking for a dedicated
  settings doctype, you won't find one (module 09).

## Regulatory note

Module 03 and module 09 use Bangladesh Bank BRPD classification buckets as a
worked example. Both carry an explicit callout: confirm current codes,
DPD thresholds, and provisioning rates against the live BRPD circular before
using them on a real Company record. Nothing in this guide is a substitute for
that check.
