# Module 02 — Loan Category

## Navigation
URL:         /app/loan-category
Awesome bar: "Loan Category"

## What is it?
Loan Category is a small tagging master: a name and a code, nothing else. You
create one record per category you want to classify loan products under (for
example, "Personal Loan" or "Business Loan"), and each Loan Product picks one.

## Why does Frappe need it?
```
Loan Category record (e.g. "Personal Loan" / code "PL")
        |
        v
Loan Product.loan_category  (you pick it on the product)
        |
        v
Loan.loan_category  (auto-copied from the product, read-only)
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Loan Category Name | `loan_category_name` | Data | Required, unique. This is the value shown wherever the category is displayed. |
| Loan Category Code | `loan_category_code` | Data | Required, unique, and is the **autoname** field (`"autoname": "field:loan_category_code"` in `loan_category.json`) — the code becomes the document's `name`/ID, not the display name. |

`disabled` exists in the JSON but is a pure display/list-filter checkbox with no
logic reading it anywhere in the app — skipped per the "pure display fields"
rule.

> **Not in this build:** I expected a category field to drive at least one
> validation, filter, or report, since that's the normal reason a classification
> master like this exists. It doesn't. `grep -rln "loan_category" apps/lending/lending`
> turns up exactly two consumers, and both are passive:
> - `loan_product.json:443` — the `loan_category` Link field lives on Loan Product.
> - `loan.json:587-588` — Loan's own `loan_category` field is `"fetch_from": "loan_product.loan_category"`, i.e. it's copied over automatically and is read-only.
>
> Neither `loan.py` nor `loan_product.py` contains any `if`/validation/filter
> logic that branches on `loan_category` — the only hits in those two `.py`
> files are the auto-generated type-hint comments (`loan_category: DF.Link | None`),
> not real code. So today, in this build, Loan Category is pure classification
> metadata with no enforced behavior. It's still worth setting up correctly
> (it's cheap, and it's the kind of field that print formats/reports get built
> against later), but don't expect it to gate or calculate anything yet.

## Worked example
There's no arithmetic here — this is a grouping mechanism, not a calculation.
Concretely: if you create two categories,

| Code | Name |
|---|---|
| PL | Personal Loan |
| BL | Business Loan |

...then a "Personal Loan" product and a "Business Loan" product will each carry
their category through to every Loan created against them (via the `fetch_from`
on Loan). The only difference this makes today is that you can filter/group the
Loan and Loan Product list views by category — there's no rate, limit, or
workflow difference tied to the category itself. Any rate/limit differences
have to be configured separately in the Loan Product record (module 10).

## What to create now
Create one Loan Category record:
- `loan_category_name` = `Personal Loan`
- `loan_category_code` = `PL`
- `disabled` = unchecked

You'll link this from the Loan Product you create in module 10.

## Why this matters later
This module → Loan Product (`loan_category` Link, module 10) → every Loan
created from that product inherits the category automatically → available as a
filter/grouping dimension in list views and any reports you build later. It does
not, in this build, change any calculation or validation along that chain.

## Source
- `apps/lending/lending/loan_management/doctype/loan_category/loan_category.json`
- `apps/lending/lending/loan_management/doctype/loan_category/loan_category.py`
- `apps/lending/lending/loan_management/doctype/loan_product/loan_product.json:14,443`
- `apps/lending/lending/loan_management/doctype/loan_product/loan_product.py` (grep, no behavioral hits)
- `apps/lending/lending/loan_management/doctype/loan/loan.json:27,587-588`
- `apps/lending/lending/loan_management/doctype/loan/loan.py` (grep, no behavioral hits)
