# Module 00a — Company Creation (the real starting point)

This sits before Module 01. Every module in this guide has a `Company` Link
field somewhere, and the Lending tab (module 09) is custom fields grafted onto
this exact doctype — so a Company has to exist, correctly, before anything
else here is even possible. This file exists because module 09 assumed
"open your existing company record" without ever explaining how that record
came to exist or what firing its first save actually does.

Company is a core Frappe/ERPNext doctype, not part of the `lending` app — so
the source of truth here is `apps/erpnext/erpnext/setup/doctype/company/`,
not `apps/lending`.

## Navigation
URL:         /app/company
Awesome bar: "Company"

## What is it?
The root record every other financial document in the system hangs off —
every ledger account, every warehouse, every Loan Product, every Sanctioned
Loan Amount, every Loan is scoped to one Company. Creating one is a heavier
operation than creating any of the lending masters: saving it for the first
time doesn't just store a row, it bootstraps an entire chart of accounts.

## Why does Frappe need it?
```
Company (name, abbr, default_currency, country, valuation_method)
        |
        v  first save (on_update, gated by "does this Company already
        |   have any Account records?")
        v
Chart of Accounts + default Warehouses + default Cost Center
+ country tax fixtures + default Departments
        |
        v
Company now has default accounts set (self.set_default_accounts())
        |
        v
Only now is it safe to fill in the Lending tab (module 09) or point
any lending doctype's `company` field at this record.
```

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Company | `company_name` | Data | Required. The display name everywhere. |
| Abbr | `abbr` | Data | Required. Short code appended to every auto-created account name for this company (e.g. `Cash - PBPLC`) — confirmed via `create_default_accounts`/chart-of-accounts code, which suffixes every account with this abbreviation. |
| Default Currency | `default_currency` | Link → Currency | Required. Drives every `Company:company:default_currency`-linked Currency field across the lending doctypes (Loan Amount, Sanctioned Amount Limit, Loan Security Price, etc. — all of module 06/07/10/11's money fields resolve their currency this way). `on_update` also flips this Currency's `enabled` flag to 1. |
| Country | `country` | Link → Country | Required. Triggers `install_country_fixtures()` and `create_default_tax_template()` on first save if the country is set/changed — installs country-specific tax templates. Not otherwise read by the lending app. |
| Default Stock Valuation Method | `valuation_method` | Select (`FIFO`, `Moving Average`, `LIFO`) | Required by the doctype, but this is inventory/stock accounting — irrelevant to loan math. Pick the default (`FIFO`) unless you're also running ERPNext's stock module for something else. |

> **Not in this build:** there is no lending-specific onboarding step here.
> Grepping `apps/lending/lending/hooks.py` for `"Company"` turns up exactly
> one hook — `validate_loan_tables` on `validate` — and it only checks the two
> Lending-tab child tables (module 09) for duplicate rows. It fires on *every*
> save, not specially at creation. Nothing in the `lending` app runs when a
> Company is first created; the Lending tab fields are just sitting there,
> inert, until you fill them in yourself in module 09.

## Worked example
Your site's default Company is **Polygon Bank Private Limited Company**
(confirmed live via `bench --site lending.localhost execute
frappe.db.get_default --args "['company']"` during this session). Its `abbr`
determines every auto-created account name — e.g. a default cash account
would be named `Cash - <abbr>`, not just `Cash`. If two companies shared an
abbreviation, ERPNext's `validate_abbr()` would reject the second one — that's
the one validation actually worth knowing before you type it in, since `abbr`
can't be sanely changed later without renaming every account under it.

## What to create now
If you're on this stack, this step is already done — `Polygon Bank Private
Limited Company` exists and every module 01–11 record you built points at it.
Only relevant if you're standing up a **second** company on the same site:
- `company_name`, a real `abbr` (short, permanent — see above)
- `default_currency`: `BDT` for a Bangladesh deployment
- `country`: `Bangladesh`
- `valuation_method`: `FIFO` (default, unless you have a reason otherwise)

Save it once, let the chart-of-accounts/warehouse/cost-center bootstrap run,
*then* go fill in its Lending tab (module 09) — trying to set Lending-tab
Account Link fields before the default chart of accounts exists will just
give you an empty Link dropdown.

## Why this matters later
This module → every `company` field across modules 06/07/09/10/11 and the
entire transactional flow (module 12) → the actual GL accounts every
disbursement and repayment posts against. Get the `abbr` wrong here and
you're renaming accounts across the whole company later, not just editing one
field.

## Source
- `apps/erpnext/erpnext/setup/doctype/company/company.json` (mandatory fields)
- `apps/erpnext/erpnext/setup/doctype/company/company.py:339-420` (`on_update`, `create_default_accounts`, `create_default_warehouses`)
- `apps/erpnext/erpnext/setup/doctype/company/company.py:232` (`validate_abbr`)
- `apps/lending/lending/hooks.py:146-149` (the one lending hook on Company)
- `apps/lending/lending/overrides/company.py` (`validate_loan_tables`, full file — already covered in module 09)
- `bench --site lending.localhost execute frappe.db.get_default --args "['company']"` (confirmed live default company name)
