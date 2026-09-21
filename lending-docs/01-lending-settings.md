# Module 01 — Lending Settings

## Navigation
URL:         /app/lending-settings
Awesome bar: "Lending Settings"

## What is it?
Lending Settings is a single (there is only ever one record, no list view) that
was meant to hold app-wide toggles for the lending app. In this build it holds
exactly two fields: a checkbox about auto-creating customers, and a place to
attach a logo for a borrower-facing portal.

## Why does Frappe need it?
```
[Lending Settings record]  --(read by app code, if any)-->  [behaviour change elsewhere]
```
In this build, nothing on the right-hand side actually happens — see the callout
below.

## Fields that matter

| Label | Fieldname | Type | What it actually controls |
|---|---|---|---|
| Auto create customer | `auto_create_customer` | Check | Nothing, in this build. Its own field description says "Will do a deduplication check and auto create a customer when a lead is converted to application", but `grep -rn "auto_create_customer" apps/lending/lending` only turns up the field's own auto-generated type stub in `lending_settings.py`. No lead-to-application conversion code anywhere in the app reads this field. |
| Portal Logo | `portal_logo` | Attach Image | Nothing, in this build. Same check: `grep -rn "portal_logo" apps/lending/lending` only finds the type stub. No borrower-portal template references it. |

> **Not in this build:** the "Auto create customer" description promises
> deduplication-and-auto-create behaviour on lead conversion. `lending_settings.py`
> is a bare `Document` subclass with `pass` as its entire body — no `validate`,
> no `on_update`, nothing. And no other file in `apps/lending/lending` reads
> either field (`grep -rln "Lending Settings" apps/lending/lending --include=*.py`
> outside the doctype's own folder returns nothing). Whatever consumed this field
> in an older or newer version of the app, it isn't wired up here. Don't rely on
> this checkbox to do anything in version-16.

## Worked example
There's no arithmetic here — both fields are inert switches with no reader. The
practical "worked example" is: ticking `auto_create_customer` on or off, saving,
and then converting a lead to a Loan Application. As of this build, you will see
no difference in behaviour either way, because nothing checks the field.

## What to create now
This is a single, so there's nothing to create — only values to set on the one
existing record:
- Leave `auto_create_customer` unticked (default `0`). It has no effect either way, so there's no reason to change it from default.
- Leave `portal_logo` empty unless you already have a borrower-portal deployment that reads it from somewhere outside this app — nothing inside `lending` does.

## Why this matters later
Nothing downstream in this build depends on Lending Settings — no other doctype
has a Link field pointing at it, and no controller reads it. It's documented
here only because it exists in the doctype list and Step 1 of the inventory
requires classifying every doctype; you can skip configuring it entirely and
move straight to Module 02.

## Source
- `apps/lending/lending/loan_management/doctype/lending_settings/lending_settings.json`
- `apps/lending/lending/loan_management/doctype/lending_settings/lending_settings.py`
- `grep -rn "auto_create_customer" apps/lending/lending` (container path: `/home/frappe/frappe-bench/apps/lending/lending`)
- `grep -rn "portal_logo" apps/lending/lending`
- `grep -rln "Lending Settings" apps/lending/lending --include=*.py`
