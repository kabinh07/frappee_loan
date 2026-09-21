# Module 12 — First Loan, Click-by-Click

This is the manual runbook: exact clicks and field values to go from an empty
`lending.localhost` site to one disbursed and partially repaid loan. Part A is
the condensed version of modules 01–11 (full rationale/sourcing is in those
files — this is just the fast path). Part B is new: the transactional flow
(Loan Application → Loan → Disbursement → Repayment) that was deferred until
now, researched fresh from `loan.py`, `loan.js`, `loan_application.py/js`,
`loan_disbursement.py`, and `loan_repayment.py`.

Before you start:
- Log in at **http://lending.localhost:8080** as `Administrator` / `admin`.
- Company: your site's default company (confirmed live as **Polygon Bank
  Private Limited Company** — check yours via the awesome bar: "Company").
- Test applicant: a Customer named **Kavin** already exists in this site
  (confirmed via `bench --site lending.localhost execute frappe.client.get_list`).
  You don't need to create one — use it as the loan applicant.

## Part A — Configuration (modules 01–11, fast path)

For every row: type the doctype name into the awesome bar (top search), click
**+ New**, fill the listed fields, **Save**. No submission needed for any of
these — they're all non-submittable masters except where noted.

| # | Doctype | Fields to set |
|---|---|---|
| 01 | Lending Settings | Nothing required — both fields are inert in this build (see module 01). Skip. |
| 02 | Loan Category | Loan Category Name = `Personal Loan`, Loan Category Code = `PL` |
| 03 | Loan Classification | Create 5 separate records — Classification Code / Classification Name: `STD`/`Standard`, `SMA`/`Special Mention Account`, `SS`/`Sub-Standard`, `DF`/`Doubtful`, `BL`/`Bad/Loss` |
| 04 | Loan Demand Offset Order | Title = `Standard EMI Offset`; in the Components table add rows in this order: `Charges`, `Penalty`, `EMI (Principal + Interest)` (module 04 found the standalone `Interest` option is a dead no-op — use the combined EMI type instead) |
| 05 | Loan Security Type | Loan Security Type = `Fixed Deposit`, Haircut % = `10`, Loan To Value Ratio = `90` |
| 06 | Loan Security | Loan Security Name = `FD-2026-0001`, Loan Security Type = `Fixed Deposit`, Loan Security Code = `FD0001` (original/available/utilized value fields are system-computed — leave blank) |
| 07 | Loan Security Price | Loan Security = `FD-2026-0001`, Loan Security Price = `500000`, Valid From = today's date/time |
| 08 | Loan Partner | Partner Name = `ABC Bank Co-lending`, Partner Code = `ABCBANK`, Organization Type = `Centralized`, Partner Loan Share Percentage = `20`, Partner Base Interest Rate = `9`, Type of FLDG Applicable = `Fixed Deposit Only`, FLDG Trigger DPD = `90`, FLDG Fixed Deposit Percentage = `5`, Effective Date = today |
| 09 | Company (open the existing Company record, go to its **Lending** tab — this is not a separate doctype) | Interest Day-Count Convention = `Actual/365`, Loan Accrual Frequency = `Monthly`, Collection Offset Logic Based On = `Days Past Due`, Days Past Due Threshold = `1`, Collection Offset Sequence for Standard Asset = `Standard EMI Offset`; then fill the two child tables using the 5 classification codes from step 03 with illustrative DPD ranges/provision rates — **confirm these against the live BRPD circular before trusting them** (see module 03/09) |
| 10 | Loan Product | Product Name = `Personal Loan - Standard EMI`, Product Code = `PL-STD`, Loan Category = `Personal Loan`, tick Is Term Loan, Rate of Interest = `15`, Repayment Schedule Type = `Monthly as per repayment start date`, Grace Period in Days = `3`, Loan Partners table → add `ABC Bank Co-lending`, Collection Offset Sequence for Standard Asset = `Standard EMI Offset`, Loan Charges table → one row, Charge Type = any Item, Charge Based On = `Percentage`, Percentage = `1` |
| 11 | Sanctioned Loan Amount | Applicant Type = `Customer`, Applicant = `Kavin`, Company = your default company, Sanctioned Amount Limit = `500000` |

At this point configuration is done — `loan.py`'s `check_sanctioned_amount_limit()`
will actively enforce that BDT 500,000 ceiling on whatever you request next
(confirmed in module 11: it's called unconditionally from both Loan and Loan
Application `validate()`).

## Part B — One real loan, start to finish

### Step 12 — Loan Application
Awesome bar → **Loan Application** → **+ New**.

Mandatory fields (confirmed via `jq '.fields[] | select(.reqd==1)' loan_application.json`):
- Applicant Type = `Customer`
- Applicant = `Kavin`
- Company = your default company
- Loan Product = `Personal Loan - Standard EMI`
- Application Date = today

Also set (not framework-mandatory, but needed for a real request):
- Loan Amount = `300000` — stays under the 500,000 sanctioned limit from module 11
- Is Term Loan shows a read-only tick (fetched from the product) — you'll then
  see **Repayment Method**, defaulted to `Repay Over Number of Periods`; set
  **Repayment Period in Months** = `12`

**Save**, then **Submit** (this doctype is submittable — `is_submittable: 1`
confirmed in `loan_application.json`).

### Step 13 — Approve it
After submit, Status shows `Open` (confirmed default in `loan_application.json`:
options are `Open`/`Approved`/`Rejected`). Change **Status** to `Approved` and
save. (This field is `permlevel: 1` — if you can't edit it, you're not logged
in with a role that has permission; Administrator always can.)

### Step 14 — Create the Loan
Once Status = `Approved` and the document is submitted, a **Create → Loan**
button appears (confirmed in `loan_application.js`'s `add_toolbar_buttons`,
which only shows it when `frm.doc.status == "Approved" && frm.doc.docstatus == 1`
and no Loan already links to this Application).

Click **Create → Loan**. It opens a new Loan form pre-filled from the
Application (`create_loan()` in `loan_application.py:277`, a standard
mapped-document copy). Review the pre-filled fields, then **Save** and
**Submit**.

On submit, `loan.py:471` runs `self.db_set("status", "Sanctioned")` —
confirmed directly in the controller. You'll see Status flip to `Sanctioned`
automatically; you don't set it yourself (the field is `read_only: 1`).

### Step 15 — Disburse it
With the Loan open and Status = `Sanctioned`, a **Create → Loan Disbursement**
button appears (`loan.js` shows it whenever status is `Sanctioned`,
`Partially Disbursed`, or `Active`).

Click it. It calls `lending.loan_management.doctype.loan.loan.make_loan_disbursement`
with `disbursement_amount` computed as `loan_amount - disbursed_amount`
(i.e. the full remaining sanctioned amount) — the new Loan Disbursement form
opens with that as the starting **Disbursed Amount**, editable if you want a
partial disbursement.

Mandatory fields (confirmed via `jq` on `loan_disbursement.json`): Against Loan,
Disbursement Date, Disbursed Amount, Company, Applicant, Applicant Type — all
pre-filled. Just confirm the Disbursement Date and **Save**, then **Submit**.

`loan_disbursement.py:182`'s `on_submit()` sets the Loan's status to `Disbursed`
if the full sanctioned amount was disbursed, or `Partially Disbursed` otherwise
(confirmed at lines 643/645 and 699/701).

### Step 16 — Take a repayment
Open the Loan again. With Status = `Disbursed` or `Partially Disbursed`, a
**Create → Loan Repayment** button appears, and (separately) a
**Status → Request Loan Closure** button.

Click **Create → Loan Repayment**. It calls
`lending.loan_management.doctype.loan.loan.make_repayment_entry`
(`loan.py:1006`), which pre-fills Against Loan, Applicant, Company, Loan
Product, Posting Date, and Value Date (both defaulted to today) — but **not**
Amount Paid. You must type that in yourself; it's the one mandatory field the
mapped-doc helper deliberately leaves blank (confirmed: `amount_paid` has no
`default` in `loan_repayment.json`, unlike the other pre-filled fields).

Set:
- Amount Paid = whatever EMI amount you want to test with, e.g. `27000`
- Repayment Type = `Normal Repayment` (first of the 20 real options in this
  build — the others are for waivers, write-offs, capitalization, etc., not
  relevant to a plain EMI)

**Save**, then **Submit**. This is where the Loan Demand Offset Order from
module 04 actually gets used: your BDT 27,000 gets allocated across
outstanding Charges → Penalty → EMI (Principal + Interest) in that row order.

At this point you have one real, disbursed, partially-repaid loan running
entirely on this build's actual code paths — not the public docs' description
of a different version.

## Source
- `apps/lending/lending/loan_management/doctype/loan_application/loan_application.json`
- `apps/lending/lending/loan_management/doctype/loan_application/loan_application.js` (`add_toolbar_buttons`, `create_loan`)
- `apps/lending/lending/loan_management/doctype/loan_application/loan_application.py:276-320` (`create_loan`)
- `apps/lending/lending/loan_management/doctype/loan/loan.json` (status field options)
- `apps/lending/lending/loan_management/doctype/loan/loan.js` (`refresh`, `make_loan_disbursement`, `make_repayment_entry`)
- `apps/lending/lending/loan_management/doctype/loan/loan.py:471` (status → Sanctioned on submit), `:1006-1025` (`make_repayment_entry`)
- `apps/lending/lending/loan_management/doctype/loan_disbursement/loan_disbursement.json`
- `apps/lending/lending/loan_management/doctype/loan_disbursement/loan_disbursement.py:182,643,645,699,701` (`on_submit`, status transitions)
- `apps/lending/lending/loan_management/doctype/loan_repayment/loan_repayment.json`
- `bench --site lending.localhost execute frappe.client.get_list` (confirmed existing Customer "Kavin")
