# The Lending Workflow (this build)

One continuous path, in the order you actually build it. This is the condensed
version — click paths and the values used on this stack. For *why* each field
matters, what's confirmed dead in this build, and the source citations, see
the linked module file; this page just sequences them.

```
Loan Category → Classification → Offset Order → Security → Security Price →
Partner → Company settings → Product → Sanctioned Limit →
Application → Approval → Loan → Disbursement → Repayment
```

**Assumed already done, not repeated below:** a Company exists
([00a](00a-company-creation.md)) — on this stack, `Polygon Bank Private
Limited Company`. Lending Settings ([01](01-lending-settings.md)) is skipped
here on purpose — both its fields are confirmed inert in this build, nothing
to configure.

---

## 1. Loan Category
[Full detail →](02-loan-category.md)

Awesome bar → **Loan Category** → **+ New**.
- Loan Category Name / Code — this stack: `CMSME` / `LC-1`

## 2. Classification
[Full detail →](03-loan-classification.md)

Awesome bar → **Loan Classification** → **+ New**, once per bucket:

| Code | Name |
|---|---|
| STD | Standard |
| SMA | Special Mention Account |
| SS | Sub-Standard |
| DF | Doubtful |
| BL | Bad/Loss |

Vocabulary only — no thresholds yet. Confirm codes/thresholds against the live
BRPD circular before treating any of this as regulatory truth.

## 3. Offset Order
[Full detail →](04-loan-demand-offset-order.md)

Awesome bar → **Loan Demand Offset Order** → **+ New**.
- Title: `Standard EMI Offset`
- Components, in this order: `Charges` → `Penalty` → `EMI (Principal + Interest)`
  (the standalone `Interest` option is a confirmed no-op in this build's
  allocation code — don't use it)

## 4. Security
[Full detail: Type →](05-loan-security-type.md) · [Item →](06-loan-security.md)

Two doctypes back to back — Security *Type* has to exist before a specific
Security can link to it.

**4a. Loan Security Type** → **+ New**
- Loan Security Type: `Fixed Deposit`, Haircut %: `10`, Loan To Value Ratio: `90`

**4b. Loan Security** → **+ New**
- Loan Security Name: `FD-2026-0001`, Loan Security Type: `Fixed Deposit`,
  Loan Security Code: `FD0001`
- Leave haircut/LTV and the three value fields alone — fetched/system-computed

## 5. Security Price
[Full detail →](07-loan-security-price.md)

Awesome bar → **Loan Security Price** → **+ New**.
- Loan Security: `FD-2026-0001`, Price: `500000`
- Valid From / Valid Upto: **both mandatory** — no open-ended row exists in
  this build. Pick a real window (e.g. 6 months).

⚠️ Saving/deleting this recalculates every affected applicant's Sanctioned
Loan Amount — not inert.

## 6. Partner
[Full detail →](08-loan-partner.md)

Awesome bar → **Loan Partner** → **+ New**.
- Partner Code: `ABCBANK`, Partner Name: `ABC Bank Co-lending`
- Partner Loan Share Percentage: `20` ← the field that actually splits GL
  postings. Partner Base Interest Rate is captured but not read anywhere
  outside tests — record it, don't rely on it.
- FLDG fields: fill in if you want (Type of FLDG Applicable, Trigger DPD,
  Fixed Deposit %) — confirmed data-entry only in this build, nothing
  enforces them automatically.
- Leave `shareables` empty (optional) and GL account Links blank for now.

## 7. Company settings
[Full detail →](09-company-lending-settings.md)

Not a separate doctype — open **Company**, the **Lending** tab.
- Interest Day-Count Convention: `Actual/365`, Loan Accrual Frequency: `Monthly`
- Collection Offset Sequence for Standard Asset: `Standard EMI Offset`
- **Loan Classification Ranges** (child table) — Min/Max DPD per code, no gaps:

  | Code | Min | Max |
  |---|---|---|
  | STD | 0 | 30 |
  | SMA | 31 | 60 |
  | SS | 61 | 90 |
  | DF | 91 | 120 |
  | BL | 121 | 99999999 |

- **IRAC Provisioning Configuration** (child table) — Code / Security Type / Provision Rate:
  `STD`/`Secured`/`1`, `SMA`/`Secured`/`5`, `SS`/`Secured`/`20`,
  `DF`/`Secured`/`50`, `BL`/`Secured`/`100`

⚠️ Confirm DPD ranges and provision rates against the live BRPD circular.
Also confirmed: `Collection Offset Logic Based On`, `Days Past Due Threshold`,
and the whole IRAC table are stored but **not read by any code in this
build** — useful as policy documentation, not as something the system acts on
yet.

## 8. Product
[Full detail →](10-loan-product.md)

Awesome bar → **Loan Product** → **+ New**.
- Product Name / Code: `Personal Loan - Standard EMI` / `PL-STD`
- Loan Category: `CMSME`, tick **Is Term Loan**
- Rate of Interest: `15`, Repayment Schedule Type: `Monthly as per repayment start date`
- Grace Period in Days: `3`
- Loan Partners table → add `ABCBANK`
- Collection Offset Sequence for Standard Asset: `Standard EMI Offset`
- Loan Charges table → one row (any Item, `Percentage`, `1`)

## 9. Sanctioned Limit
[Full detail →](11-sanctioned-loan-amount.md)

Awesome bar → **Sanctioned Loan Amount** → **+ New**.
- Applicant Type: `Customer`, Applicant: your test customer
- Company: your default company, Sanctioned Amount Limit: `500000`

This is the one doctype in this shape that's genuinely user-created and
actively enforced (`frappe.throw` from both Loan and Loan Application
`validate()`) — not a system log like its similarly-shaped siblings.

---

## 10. Application
[Full detail →](12-first-loan-walkthrough.md#step-12--loan-application)

Awesome bar → **Loan Application** → **+ New**.
- Applicant Type/Applicant, Company, Loan Product: `PL-STD`
- Loan Amount (stay under your sanctioned limit), Repayment Period in Months
- **Save**, then **Submit**

## 11. Approval
[Full detail →](12-first-loan-walkthrough.md#step-13--approve-it)

⚠️ **No Approve button exists in this build.** Status has no
`allow_on_submit`, and the only workflow that could drive it
(`Loan Application Workflow`) is disabled and targets a different field
entirely. In this environment we set `status = Approved` directly via
`bench execute frappe.db.set_value`. On a real deployment, this needs either
the disabled workflow properly configured, or a custom fix — not something
a normal user can currently do through the Desk form.

## 12. Loan
[Full detail →](12-first-loan-walkthrough.md#step-14--create-the-loan)

Once Approved + submitted: **Create → Loan** button appears → opens a
pre-filled Loan → **Save**, then **Submit**.

On submit, `loan.py:471` sets status to `Sanctioned` automatically — you
don't set this field yourself.

## 13. Disbursement
[Full detail →](12-first-loan-walkthrough.md#step-15--disburse-it)

With status `Sanctioned`/`Partially Disbursed`/`Active`: **Create → Loan
Disbursement** → pre-filled with the remaining sanctioned amount, editable →
**Save**, then **Submit**.

Full amount disbursed → status `Disbursed`. Less than full → `Partially
Disbursed`.

## 14. Repayment
[Full detail →](12-first-loan-walkthrough.md#step-16--take-a-repayment)

With status `Disbursed`/`Partially Disbursed`: **Create → Loan Repayment** →
pre-fills everything **except Amount Paid** — check the Loan's connected
**Loan Repayment Schedule** for the real EMI figure before typing it in,
since nothing pre-fills it for you.
- Repayment Type: `Normal Repayment` → **Save**, then **Submit**

---

## Source
Every field, value, and behavioral claim above is sourced in its linked
module file. This page only sequences them — see `README.md` for the full
module index and the cross-module "Not in this build" findings.
