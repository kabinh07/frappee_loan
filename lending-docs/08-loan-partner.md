# Module 08 — Loan Partner

## Navigation
URL:         /app/loan-partner
Awesome bar: "Loan Partner"

## What is it?
A Loan Partner is a bank or NBFC you co-lend with: they fund and take on risk for
an agreed slice of a loan instead of you carrying all of it alone. The record you
configure here fixes that partner's percentage share, their base interest rate,
and the terms of a loss-guarantee (FLDG) they've agreed to provide if a borrower
defaults.

The doctype's own name field is `partner_code` (`autoname: "field:partner_code"`),
so whatever you type there becomes the record's ID everywhere else it's linked.

## Why does Frappe need it?
```
Loan disbursed (BDT)  --split by partner_loan_share_percentage-->  "our" principal
                                                              \\--> "partner's" principal
                                                                     (posted to partner's
                                                                      receivable/credit account,
                                                                      only if
                                                                      enable_partner_accounting)
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Partner Code | `partner_code` | Data | Becomes the record's `name` (autoname is `field:partner_code`) — this is what every other doctype links to, not Partner Name. |
| Partner Loan Share Percentage | `partner_loan_share_percentage` | Percent | The real split. Read in `loan_disbursement.py:878` to post `(disbursed_amount * partner_loan_share_percentage) / 100` as a GL entry, and in `loan_repayment_schedule.py:356-371` to split principal/interest per instalment, and in `loan_repayment.py:1892-1897` to compute `loan_partner_share_percentage`/`loan_partner_payment_ratio` on repayment. Must be between 1 and 99 — `loan_partner.py:75-77` throws otherwise. |
| Partner Base Interest Rate | `partner_base_interest_rate` | Percent | Same 1–99 validation as above (`loan_partner.py:75-77`). Referenced only in tests and the type stub in this build — no calculation file reads it to, say, net off your own spread from the partner's rate. |
| Organization Type | `organization_type` | Select | `Centralized` / `Decentralized`. No behavioural consumer found outside the doctype's own field — stored, not branched on. |
| Repayment Schedule Type | `repayment_schedule_type` | Select | `EMI (PMT) based` / `Collection at partner's percentage` / `POS reduction plus interest at partner ROI`. This label also exists as its own field on Loan Product (module 10) — the two are read from different places (`loan_disbursement.py`, `loan_demand.py`, `loan_repayment_schedule.py` all reference `repayment_schedule_type`, but keyed off the *Loan*, not directly off this partner field in this build). |
| Servicer Fee | `servicer_fee` | Check | Captured on the form and by `tests/test_utils.py`'s test factory; no `.py` outside tests reads it. |
| Enable Partner Accounting | `enable_partner_accounting` | Check | The on/off switch for all partner GL postings. Checked in `loan_disbursement.py:872-873` before posting the partner's share, in `loan_repayment.py:2360-2365` before splitting repayment GL entries, and in `overrides/sales_invoice.py:93-95` before applying partner accounting to a charge invoice. If unchecked, `partner_loan_share_percentage` still describes the split conceptually but nothing gets posted to the accounts below for the partner's side. |
| Receivable / Credit / Payable / FLDG / Interest-Share accounts | `receivable_account`, `credit_account`, `payable_account`, `fldg_account`, `partner_interest_share` | Link → Account | Pure GL wiring, not loan math — they tell the disbursement/repayment GL-entry code which ledger accounts to debit/credit once `enable_partner_accounting` is on. Only `receivable_account` and `credit_account` are actually read in this build (`loan_disbursement.py:874-877`); `payable_account`, `fldg_account`, and `partner_interest_share` are captured but not read by any `.py` outside the doctype's own file and tests. |
| FLDG Trigger DPD | `fldg_trigger_dpd` | Int | See callout below — not read anywhere outside this doctype's type stub and test fixtures. |
| FLDG Limit Calculation Component | `fldg_limit_calculation_component` | Select | `Disbursement` / `Outstanding Principal` / `Outstanding Principal & Interest Accrued`. Same as above — not read anywhere outside this doctype and tests. |
| FLDG Fixed/Corporate Guarantee % | `fldg_fixed_deposit_percentage`, `fldg_corporate_guarantee_percentage` | Percent | Only consumer is `loan_partner.py:79-89`'s own `validate_percentage_and_interest_fields`, which makes the relevant one mandatory (1–99) depending on `type_of_fldg_applicable`, and nothing more. |
| Type of FLDG Applicable | `type_of_fldg_applicable` | Select | `Fixed Deposit Only` / `Corporate Guarantee Only` / `Both Fixed Deposit and Corporate Guarantee`. Drives which of the two percentage fields above become mandatory (`loan_partner.py:81-87`). |

> **Not in this build:** the FLDG (First Loss Default Guarantee) fields —
> `fldg_trigger_dpd`, `fldg_limit_calculation_component`,
> `fldg_fixed_deposit_percentage`, `fldg_corporate_guarantee_percentage`, and
> `fldg_account` — are captured and validated on this form, but grepping
> `apps/lending/lending` end to end finds no code in `loan.py`,
> `loan_disbursement.py`, `loan_repayment.py`, or the `process_*` jobs that
> reads `fldg_trigger_dpd` to check a borrower's days-past-due against it, or
> that turns `fldg_fixed_deposit_percentage` into an actual guarantee-limit
> amount or GL claim. In this installed build, FLDG is data entry only — there
> is no automatic trigger or payout. If you're relying on FLDG protection
> operationally, it has to be tracked and actioned manually until/unless a
> later patch wires it up.

## Worked example
A BDT 1,000,000 loan is disbursed with `partner_loan_share_percentage = 20` and
`enable_partner_accounting` checked.

`loan_disbursement.py:878`: `(1,000,000 × 20) / 100 = 200,000`

So on disbursement, GL posts BDT 200,000 as a debit to the partner's
`receivable_account` and credit to `credit_account` — that's the partner's
funded share. The remaining BDT 800,000 is yours, tracked through the loan's own
disbursement accounting (module 10, deferred to the transactional pass).

If you also set `fldg_fixed_deposit_percentage = 5`, you might read that as "the
partner backs 5% of the loan with a fixed deposit," i.e. BDT 50,000 of guarantee
cover on this loan — but per the callout above, this build never actually computes
or enforces that number anywhere. Treat it as a note-to-self field until you've
confirmed otherwise in your own copy of the code.

## What to create now
Create one Loan Partner record:
- Partner Code: `ABCBANK`
- Partner Name: `ABC Bank Co-lending`
- Organization Type: `Centralized`
- Partner Loan Share Percentage: `20`
- Partner Base Interest Rate: `9`
- Repayment Schedule Type: `EMI (PMT) based`
- Effective Date: today
- Type of FLDG Applicable: `Fixed Deposit Only`
- FLDG Fixed Deposit Percentage: `5` (recorded, not enforced — see callout)
- FLDG Trigger DPD: `90` (recorded, not enforced — see callout)
- Enable Partner Accounting: leave unchecked until your Company's chart of
  accounts has partner-specific receivable/credit accounts ready (module 09
  covers the Company side; the accounts themselves are outside this app).

## Why this matters later
This module → Loan Product's `loan_partners` table (module 10, via the
Loan Product Loan Partner child doctype) → which partners are even selectable
on a given product → a Loan's disbursement GL split and (once you reach the
deferred transactional pass) its repayment GL split, both keyed off
`partner_loan_share_percentage` and `enable_partner_accounting` from this record.

## Source
- `apps/lending/lending/loan_management/doctype/loan_partner/loan_partner.json`
- `apps/lending/lending/loan_management/doctype/loan_partner/loan_partner.py`
- `apps/lending/lending/loan_management/doctype/loan_disbursement/loan_disbursement.py:860-885`
- `apps/lending/lending/loan_management/doctype/loan_repayment/loan_repayment.py:1875-1897,2355-2365`
- `apps/lending/lending/loan_management/doctype/loan_repayment_schedule/loan_repayment_schedule.py:356-371`
- `apps/lending/lending/overrides/sales_invoice.py:90-96`
