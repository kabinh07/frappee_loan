# LMS Scope Document — Frappe Lending

> Standalone scope document (not part of the full BRD → SRS → … → Epics
> pipeline — the user opted for a lightweight scope doc instead, via
> `/agentic-harness:plan`). Describes what the **Loan Management (LMS)**
> side of the installed `lending` app provides — loan servicing from
> sanction/booking through closure — based on the **installed** code
> running in the `lending` Docker stack, not on docs.frappe.io, per this
> project's `CLAUDE.md` rule 1 (the public docs track a newer build and
> have already caused one wrong setup here).
>
> **Explicitly excluded by user request:** Loan Origination (LOS) — lead
> capture, application intake/KYC workflow, co-applicants, document
> collection, **and Disbursement, which is treated as LOS's final step**
> (loan goes from Sanctioned to funded, then hands off to LMS for
> servicing). See §2 and `planning/LOS_LMS_CBS_FLOW.md`.

| Field | Value |
|---|---|
| Status | Draft |
| Version | 0.5.0 (0.1.0 → LOS/Disbursement removed; 0.3.0 → renamed "Loan Account Management" to "Loan Book & Product Management"; 0.4.0 → bulk interest-rate change promoted to Planned feature, all 11 reports enumerated; 0.5.0 → full Bulk Interest Rate Repricing spec added as §3a, with open data-model questions) |
| Date | 2026-09-16 |
| Source | Installed code, `apps/lending/lending/` inside the `lending-backend-1` container, app version `16.4.4` |
| Scope | LMS (loan servicing, post-disbursement onward) only, backend/data-model only — no UI/portal screens documented (`planning.has_ui: false`) |

## 1. Purpose

This document scopes the **Loan Management (servicing)** capability of
Frappe Lending — everything that happens to a loan **after it has been
disbursed**, through repayment, collateral management, interest accrual,
restructuring, risk classification, co-lending, and closure. The
origination-to-funding journey (lead → application → underwriting →
sanction → disbursement) is treated as LOS end-to-end, including
disbursement itself — LMS begins at schedule generation, once funds are
already out the door. See §2 and `planning/LOS_LMS_CBS_FLOW.md` for the
full LOS→LMS→CBS handoff diagram.

Both Loan Origination and Disbursement are implemented as part of this
same installed `lending` app (Loan Origination is its own Frappe module;
Disbursement lives inside the Loan Management Frappe module directory
alongside everything below) — the LOS/LMS split here is a scope/ownership
decision this document applies on top of that code layout, not a
reflection of how the code itself is organized.

## 2. Out of scope for this document

- **Loan Origination (LOS)**, end-to-end through funding — Loan Lead
  capture/qualification, OTP verification fields, Loan Application intake
  and its KYC workflow, co-applicants, document collection, loan-purpose
  master, origination settings, **and Disbursement** (disbursement-tranche
  processing, LTV-based disbursal limit checks, disbursement charges).
  (`loan_origination/` module, plus the `Loan Application` and `Loan
  Disbursement`/`Loan Disbursement Charge` doctypes.)
- UI/portal screens (a "Borrower Portal" is referenced by a settings field
  but its page code was not located in this survey pass — flagged in §12).
- The 11 built-in reports under `loan_management/report/` are known to
  exist (from test-coverage evidence) but were not individually enumerated
  in this pass — see §12.
- ERPNext/Frappe core features (accounting, bank reconciliation UI, email
  delivery) that Lending merely hooks into rather than implements.

## 3. Module: Loan Book & Product Management

*(Not "loan account" — this isn't about opening the customer a bank
account. This is the lender's book of already-sanctioned/disbursed loans:
the product rules each loan is governed by, and the loan record's own
status/lifecycle as it's serviced.)*

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Loan product configuration | Defines rate plans and repayment-schedule types (Monthly / Pro-rated / Cycle-date / Line-of-Credit / Flat Interest), plus the full GL account mapping per product (interest, penalty, disbursement, suspense, write-off, subsidy, refund). | Loan Product |
| Loan record & status lifecycle | The system-of-record for each loan in the book. Status flows Draft → Sanctioned → Partially Disbursed → Disbursed → Active → Loan Closure Requested → Closed / Written Off / Settled. Supports moratorium periods and line-of-credit limit tracking (maximum/utilized/available amount). | Loan |
| Loan categorization | Simple categorization tag applied to a loan. | Loan Category |
| Sanctioned-limit register | Tracks the sanctioned credit limit per applicant type/company. | Sanctioned Loan Amount |
| Branch-to-branch loan transfer | Bulk-transfers a batch of loans in the book from one servicing branch to another. | Loan Transfer, Loan Transfer Detail |
| Opening-balance import | Captures opening principal/interest/penalty/charge outstanding, for migrating an existing loan book into the system. | Loan Import Details |
| Automatic line-of-credit closure | Daily scheduled job auto-closes fully-repaid Line-of-Credit loans. | Loan (`auto_close_loc_loans`) |
| Bulk Interest Rate Repricing — **(Planned / Not Yet Implemented)** | Maker-checker-approved, batch rate change across eligible floating-rate loans, effective a future date, with dry-run preview and versioned schedule regeneration. Full spec in §3a — a materially bigger feature than, and not a fix to, the orphaned code in §12. | *(none yet — new feature; see §3a for why the existing `Process Loan Interest Change` code doesn't cover it)* |

### 3a. Planned feature spec: Bulk Interest Rate Repricing

**Status: Planned, not implemented.** This is scope documentation only —
no code has been written for this. It **supersedes** the orphaned
`Process Loan Interest Change` code discussed in §12: that code covers
essentially none of the requirements below (no eligibility filtering, no
dry-run, no maker-checker, no schedule versioning, bypasses the `Loan`
doctype's own hooks, writes no audit trail) and should not be assumed to
be a usable starting point without a full rewrite.

| Requirement | Detail |
|---|---|
| Eligibility & selection | Authorized user selects loans by product, customer segment, branch, or explicit loan IDs. **Open question:** none of "floating vs. fixed rate," "customer segment," or "branch on Loan" are confirmed to exist as fields today — see §12 for what's actually on `Loan`/`Loan Product` currently. |
| Non-interference with history | Must not modify paid EMIs or historical transactions. |
| Rate transition | Accrue at the old rate up to the effective date; apply the new rate only from the effective date forward. |
| Recalculation scope | Recalculate only outstanding principal and unpaid installments — not the full loan history. |
| Two repricing modes | (a) increase the EMI, holding the maturity date fixed, or (b) extend the tenure, holding the EMI fixed. Caller chooses per batch. |
| Schedule versioning | Produce a new version of the repayment schedule while preserving all previous versions (not overwriting history). The nearest confirmed precedent in this codebase is `Loan Restructure`, which already creates an updated `Loan Repayment Schedule` and moves the prior one to a Restructured/Outdated status rather than deleting it. |
| Preview / dry-run | Before committing, show affected loans with old vs. new EMI, tenor, and total interest. |
| Maker-checker approval | Requires a second-approver sign-off before execution — no batch financial-rate change goes live on a single user's action. |
| Processing guarantees | Idempotent, transactional, resumable, and auditable. The nearest confirmed precedent in this codebase is `Loan Repayment Repost`, whose batch has its own Draft/Queued/In Process/Completed/Cancelled status — a similar resumable-batch shape, not a ready-made implementation. |
| Audit trail | Record rate-change reason, effective date, approver(s), the full set of affected loans, and before/after values for each. |
| Borrower notification | Notify affected borrowers once the change is approved. |
| Exclusions | Fixed-rate loans, and loans already Closed / Written Off / otherwise ineligible, must be excluded from selection. |

## 4. Module: Collateral & Security Management

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Security master & valuation | Defines collateral types with default haircut/LTV ratios, individual security instances, and a price history used to compute shortfall. | Loan Security Type, Loan Security, Loan Security Price |
| Pledge lifecycle | Full pledge workflow: Pledge Requested → Pledged → Release Requested → Released / Repossessed / Cancelled. | Loan Security Assignment, Pledge, Proposed Pledge |
| Security release / unpledge | Handles requesting and approving release of pledged security. | Loan Security Release, Unpledge |
| Shortfall monitoring | Scheduled job scans all secured loans and auto-creates a shortfall record when pledged security value falls below outstanding exposure; also triggered on manual price updates via the API. | Loan Security Shortfall, Process Loan Security Shortfall |

## 5. Module: Repayment, Billing & Charges

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Amortization schedule generation | Generates the repayment schedule per loan, including per-co-lender share splits for co-lent loans. | Loan Repayment Schedule, Repayment Schedule, Co-Lender Schedule |
| Demand generation | Scheduled job generating billable demand lines (EMI, principal, interest, penalty, charges, BPI), with separate logic paths for term loans vs. demand/overdraft-style loans. | Loan Demand, Process Loan Demand |
| Repayment processing | The richest workflow in the system — over 15 repayment types including normal payment, interest/penalty waiver, principal adjustment, pre-payment, advance payment, capitalization variants, write-off recovery, subsidy adjustment, and full/partial settlement. | Loan Repayment |
| Bulk repayment processing | Mass repayment upload and posting, with its own success/failure status tracking. | Bulk Repayment Log |
| Demand offset rules | Configurable priority order defining how an incoming payment is allocated across EMI, principal, interest, additional interest, penalty and charges. | Loan Demand Offset Order, Loan Demand Offset Detail |
| Charges engine | Configurable charge types (each with its own income/receivable/waiver/write-off GL mapping) attachable to a product, a repayment, a prepayment, or a restructure. | Loan Charges, Loan Repayment Charges, Prepayment Charges, Loan Restructure Charges, Loan Charge Reference |
| Due-amount & schedule preview API | Whitelisted endpoints return a simulated repayment schedule for a proposed loan, or a due-amount breakdown (overdue penalty/interest/principal, unbooked interest, available security deposit, written-off amount, excess paid) for an existing one — without requiring a saved record. | `api.get_repayment_schedule`, `api.get_due_details` |

## 6. Module: Interest & Accrual Management

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Interest accrual engine | Scheduled, frequency-aware periodic interest booking per loan (frequency is configurable per product, not fixed). | Loan Interest Accrual, Process Loan Interest Accrual |
| Penal interest calculation | Dedicated calculation path for penal interest on overdue amounts, kept separate from normal interest accrual. | Loan Interest Accrual (`calculate_penal_interest_for_loans`) |
| Accrual reversal & repost | Reverses/cancels and reposts accrual entries, e.g. after a correction, for a batch of loans over a date range. | Loan Accrual Repost, Loan Accrual Repost Detail |
| Repayment repost | Reposts previously-posted repayment entries in bulk, with its own Draft/Queued/In Process/Completed/Cancelled status. | Loan Repayment Repost, Loan Repayment Repost Detail, Loan Repayment Repost Cancel Detail |

## 7. Module: Restructuring, Write-Off & Adjustments

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Loan restructuring | Supports Normal / Pre-Payment / Advance-Payment restructure types, each producing an updated repayment schedule (and, where relevant, a settlement repayment). Branch/company-level monthly restructure-limit is tracked and enforced. | Loan Restructure, Loan Restructure Charges, Loan Restructure Limit Log, Process Loan Restructure Limit |
| Write-off & recovery | Records a write-off against a loan; also supports recovering amounts previously written off (not a one-way operation). | Loan Write Off |
| Manual adjustments | Manual/internal foreclosure and balance corrections covering waivers, capitalization, and carry-forward adjustment types. | Loan Adjustment, Loan Adjustment Detail |
| Balance adjustments | Credit/debit adjustment tied to a specific repayment or restructure. | Loan Balance Adjustment |
| Refunds | Refund of excess payment on a loan. | Loan Refund |
| Security deposits | Tracks deposits held as loan security and their allocation/availability/refund. | Loan Security Deposit |

## 8. Module: Risk & Compliance (Asset Classification)

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Asset classification engine | DPD-range-driven classification (e.g. Standard / Sub-standard / NPA), run as a daily scheduled batch job. | Loan Classification, Loan Classification Range, Process Loan Classification |
| Provisioning | Provisioning-percentage matrix keyed by classification and security type (Secured/Unsecured/Semi-Secured) — RBI IRAC-style provisioning. | Loan IRAC Provisioning Configuration |
| DPD & NPA audit trail | Per-loan, per-posting-date log of days-past-due and of NPA status transitions. | Days Past Due Log, Loan NPA Log |
| Income suspense handling | On classification as non-performing, automatically moves unpaid interest and receivable charges to a suspense ledger. A separate, higher DPD threshold governs when a loan becomes eligible for write-off vs. standard NPA classification. | Loan (`move_unpaid_interest_to_suspense_ledger`, `get_dpd_threshold_write_off_map`) |
| Loan freeze tracking | Records freeze/unfreeze periods on a loan (e.g. moratorium or legal hold). | Loan Freeze Log |
| Line-of-credit limit audit | Logs every change to a loan's maximum/utilized/available limit amounts. | Loan Limit Change Log |

## 9. Module: Co-Lending & Partner Management

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Co-lending partner master | Defines a co-lending partner, including First-Loss Default Guarantee (FLDG) type: Fixed Deposit, Corporate Guarantee, or Both. | Loan Partner, Loan Partner Address |
| Product–partner mapping | Links a co-lending partner to the products they participate in. | Loan Product Loan Partner |
| Collection/loan-amount share | Defines a partner's share percentage of collections or of the loan amount itself. | Loan Partner Shareable |
| Ad-hoc charge sharing | Defines the sharing ratio for ad-hoc charges with a co-lending partner. | Loan Partner Adhoc Charges Shared |
| Credit note reconciliation | Hourly scheduled job reconciling pending credit notes arising from partner-shared collections. | Loan Repayment (`process_pending_credit_notes`) |

## 10. Module: Reporting, Statements & Platform Administration

| Feature | Description | Backing doctype(s) |
|---|---|---|
| Statement of accounts | Configures and triggers generation/emailing of a borrower's statement of account, scheduled to run daily, with letterhead/terms and CC recipients. | Process Loan Statement of Accounts, Process Loan Statement of Accounts Applicant, Process Statement Of Accounts CC |
| Report: ALM Audit Report | Ageing-bucketed principal/interest outstanding per loan — asset-liability management view. | Loan |
| Report: Applicant Wise Loan Security Exposure | Pledged-security exposure grouped by applicant. | Loan Security |
| Report: Disbursement Analysis Report | Disbursement volume/trend analysis. | Loan Disbursement |
| Report: Future Cashflow Report | Projected future payment dates/amounts per disbursement, going forward. | Loan |
| Report: Loan Outstanding Report | Current outstanding balance per loan. | Loan |
| Report: Loan Repayment and Closure | Repayment and closure activity per loan. | Loan Repayment |
| Report: Loan Security Exposure | Total pledged-security exposure. | Loan Security |
| Report: Loan Security Ledger | Ledger-style history of security pledge/release/value events. | Loan Security |
| Report: Loan Security Status | Current status of each pledged security. | Loan Security |
| Report: Loan Statement of Account | Per-loan statement view (ad hoc, distinct from the scheduled/emailed Process Loan Statement of Accounts above). | Loan |
| Report: Past Cashflow Report | Historical principal/interest/additional-interest actually collected. | Loan |
| Platform settings | App-wide toggles: auto-create-customer on loan creation, Borrower Portal branding. | Lending Settings |
| Dual accounting modes | Company-level toggle switches the whole app between full GL-posting (via Sales Invoice/Journal Entry) and a simplified Loan-Demand-only accounting mode. | `api.apply_charge`, `enable_loan_accounting` company flag |
| Roles & workflow gating | Loan Manager, Loan Officer, Loan Processor, Loan Appraiser, Loan Underwriter roles apply across the servicing lifecycle (the sixth role, Loan LOS User, is origination-specific and out of scope here). | Fixtures: `role.json` |
| Bank reconciliation integration | Hooks into ERPNext's own bank reconciliation feature for Loan Repayment records (Loan Disbursement reconciliation is out of scope — see §2). | `hooks.py` (`bank_reconciliation_doctypes`) |

## 11. Actors (roles)

Loan Manager · Loan Officer · Loan Processor · Loan Appraiser · Loan
Underwriter — plus an implied self-service Borrower actor (via the
referenced Borrower Portal, not documented in detail here per §2/§12).
`Loan LOS User` exists as a role in the app but is origination-specific
and out of scope for this document.

## 12. Known gaps / open items

These are observations from reading the installed code, not confirmed
product decisions — flagged for follow-up rather than silently omitted.
Origination-specific gaps (OTP stub fields, lossy lead→application
conversion) are intentionally omitted here since LOS is out of scope —
see the prior full-scope draft if those are needed later.

- **`Process Loan Interest Change` is orphaned and insufficient.**
  `process_loan_interest_change.py` has no `.json` schema (unreachable —
  see original finding above this list), and even if registered, it only
  flips `Loan.rate_of_interest` via a raw `frappe.qb.update` — bypassing
  the `Loan` doctype's own `validate`/`on_update` hooks, writing no audit
  trail, and not regenerating the repayment schedule. It does not meet
  the requirements gathered for Bulk Interest Rate Repricing (§3a) and
  should not be extended in place — treat §3a as a from-scratch feature.
  (Re-confirmed directly this session: the directory contains only the
  `.py` file, still no `.json`.)
- **Bulk Interest Rate Repricing (§3a) has three unresolved data-model
  questions** before it can move from spec to design:
  - No "fixed vs. floating rate" field was found anywhere in `Loan` or
    `Loan Product` in the original survey — eligibility filtering needs
    this concept to exist first.
  - No "customer segment" field was identified on `Loan`, `Loan
    Application`, or the ERPNext `Customer` doctype in the original
    survey — needs to be defined (an existing field repurposed, e.g.
    Customer Group, or a new one) before "select by segment" is buildable.
  - `branch` is confirmed only on a few doctypes (e.g. `Loan Transfer`) in
    the original survey — whether `Loan` itself carries a branch to filter
    by needs re-confirming before "select by branch" is buildable.
- **App git branch unverified.** The running container has no `.git`
  directory for `apps/lending` (or `erpnext`/`frappe`/`payments`), so the
  branch could not be confirmed live, per `CLAUDE.md` rule 3. The only
  evidence is `__version__ = "16.4.4"` in the app's `__init__.py` and this
  host repo's `apps.json`, which declares `version-16` as a **build-time**
  input — not proof of what's actually baked into the current image.
- **Borrower Portal referenced but not located.** `Lending Settings` has a
  "Borrower Portal" section (logo field), implying a self-service borrower
  UI exists, but no portal page/template code was found in this pass
  (`templates/`, `public/` weren't scoped in). Undocumented here per the
  backend-only scoping decision (§2) — revisit if `has_ui` changes.
- **No external integrations found** — no payment gateway or credit
  bureau API code exists in this app.
