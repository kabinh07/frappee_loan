# Module 04 — Loan Demand Offset Order

## Navigation
URL:         /app/loan-demand-offset-order
Awesome bar: "Loan Demand Offset Order"

## What is it?
A named, ordered list of demand types (Charges, Penalty, Interest-and-Principal,
etc.). It doesn't hold any money or dates itself — it's a priority list that says
"when a repayment comes in and there isn't enough cash to clear everything owed,
settle in this order." You create a handful of these once, then point Company and
Loan Product at whichever one applies.

## Why does Frappe need it?
```
Repayment amount received
        |
        v
apply_allocation_order() walks this record's "components" rows top to bottom
        |
        v
row 1 demand type -> pay down as much of that as the cash allows
        |
        v
row 2 demand type -> pay down whatever cash is left
        |
        v
   ... continues until cash runs out or every row is processed
        |
        v
Leftover, if any, becomes an advance/unallocated amount
```
Source: `apps/lending/lending/loan_management/doctype/loan_repayment/loan_repayment.py:1968` (`apply_allocation_order`).

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Title | `title` | Data | Just a label so you can tell offset orders apart when you pick one on Company or Loan Product — not read anywhere else. |
| Components | `components` | Table (Loan Demand Offset Detail) | Row order **is** the allocation priority. `apply_allocation_order` does `for d in allocation_order_doc.get("components")` and processes each row's `demand_type` in the order the rows sit in the table — first row gets first claim on the repayment cash (`loan_repayment.py:1971-1973`). |
| Demand Type (child row) | `demand_type` | Select | Options actually present in the JSON: `EMI (Principal + Interest)`, `Principal`, `Interest`, `Additional Interest`, `Penalty`, `Charges`. |

Per-option behavior, read directly from `apply_allocation_order` (`loan_repayment.py:1974-2024`):

| `demand_type` row value | What happens when this row is reached |
|---|---|
| `EMI (Principal + Interest)` | Pays BPI (broken-period interest) first, then — only if the loan is a term loan (`self.is_term_loan`) — the combined EMI bucket. Line 1974-1977. |
| `Principal` | Pays the "Normal" (non-EMI) principal bucket, then — only if term loan — the EMI principal bucket. For settlement-type repayments (Partial/Full Settlement, Write Off Recovery/Settlement, Principal Adjustment) it also pushes any remaining cash straight onto outstanding principal, bypassing schedule waiting. Line 1978-2011. |
| `Interest` | **No matching branch exists.** A row with this value is a no-op — nothing in `apply_allocation_order` checks `d.demand_type == "Interest"`. Interest only actually gets paid as a side effect of the `Principal` row above (which internally settles the "Normal"/EMI interest bucket too). See the callout below. |
| `Penalty` | Pays the Penalty demand bucket. Line 2020-2021. |
| `Additional Interest` | Pays the Additional Interest demand bucket. Line 2022-2023. |
| `Charges` | Pays the Charges demand bucket. Line 2024-2025. |

> **Not in this build:** the code also has a branch `if d.demand_type == "Normal"` (`loan_repayment.py:2013`), but `"Normal"` is not one of the six Select options on `Loan Demand Offset Detail` — you cannot enter it from the form. That branch is unreachable through configuration; don't expect adding an "Interest"-labelled row to trigger it. This is a real discrepancy in the installed code, not something the public docs mention — confirmed by reading `loan_management/doctype/loan_demand_offset_detail/loan_demand_offset_detail.json` (six options) against `loan_repayment.py:2013` (checks for a seventh, unreachable value) side by side.

Charges are actually allocated by a separate method, `allocate_charges()` (`loan_repayment.py:1932`), which runs against `self.get("payable_charges")` before `apply_allocation_order` is even called for the rest — so a `Charges` row inside this Offset Order mainly documents intent/ordering relative to Penalty/Principal in the code path shown above, while charge amounts tied to specific charge codes on the repayment are already handled upstream.

## Worked example
A borrower's repayment of **BDT 15,000** arrives against a loan with these outstanding demand balances:

- Charges: BDT 500
- Penalty: BDT 1,200
- Principal + Interest (via the `Principal` row, since `Interest` alone is a no-op): BDT 20,000

Using an Offset Order with rows in this sequence — Charges, Penalty, Principal:

1. **Charges row**: pending BDT 15,000, charges owed BDT 500 → pay BDT 500. Remaining: BDT 14,500.
2. **Penalty row**: pending BDT 14,500, penalty owed BDT 1,200 → pay BDT 1,200. Remaining: BDT 13,300.
3. **Principal row**: pending BDT 13,300, principal+interest owed BDT 20,000 → pay BDT 13,300 (all of it, since it's less than what's owed). Remaining: BDT 0.

Result: BDT 15,000 repayment fully consumed; BDT 6,700 of principal+interest remains outstanding for the next cycle. If the rows had been ordered Principal-first instead, the same BDT 15,000 would have gone straight to principal+interest first, leaving Charges and Penalty completely unpaid this cycle — the row order is the only thing that decides which outcome you get.

## What to create now
Create one record:
- **Title**: `Standard EMI Offset`
- **Components** (in this exact row order):
  1. `Charges`
  2. `Penalty`
  3. `EMI (Principal + Interest)`

Use the combined `EMI (Principal + Interest)` option rather than a separate `Principal` row plus a (non-functional) `Interest` row — since `Interest` alone does nothing (see callout above), and `EMI (Principal + Interest)` is the option that actually engages the BPI/EMI settlement path in one step for term loans. If you later need a distinct pure-principal priority (e.g. for a Line of Credit product with no EMI schedule), use the `Principal` row instead of `EMI (Principal + Interest)` — `Principal` runs the same "Normal" bucket settlement without requiring `is_term_loan`.

## Why this matters later
This module → Company's Lending tab (`collection_offset_sequence_for_standard_asset` etc., Module 09) and/or a specific Loan Product's own override fields (Module 10) → every `Loan Repayment` submitted against a loan using that product/company calls `apply_allocation_order()` with whichever Offset Order is in effect, deciding exactly which of Charges/Penalty/Interest/Principal gets cleared first whenever a repayment doesn't cover everything owed.

## Source
- `apps/lending/lending/loan_management/doctype/loan_demand_offset_order/loan_demand_offset_order.json`
- `apps/lending/lending/loan_management/doctype/loan_demand_offset_detail/loan_demand_offset_detail.json`
- `apps/lending/lending/loan_management/doctype/loan_repayment/loan_repayment.py:1932` (`allocate_charges`)
- `apps/lending/lending/loan_management/doctype/loan_repayment/loan_repayment.py:1968-2027` (`apply_allocation_order`, `adjust_component`)
