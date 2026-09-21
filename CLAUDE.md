# Project: Frappe Lending learning environment

## Stack
- frappe / erpnext / payments / lending, all on `version-16`
- Python 3.14, Node 24 (hard requirements of frappe v16)
- Site: lending.localhost:8080 (Administrator / admin)
- Compose project name: `lending`, file `lending-compose.yaml`

## Running anything inside the stack
docker compose -f lending-compose.yaml --project-name lending exec backend bash -lc '<cmd>'

## Hard rules
1. Source of truth is the installed code under
   apps/lending/lending/loan_management/doctype/, NOT docs.frappe.io.
   The public docs track a newer build and have already caused one wrong setup.
2. Never invent a fieldname, doctype, or bench flag. Grep or admit uncertainty.
3. Before claiming an app is correctly installed, check its git branch, not just
   that its directory exists.
4. `docker compose down -v` destroys data. Always warn before proposing it.
5. Documentation lives in docs/, one module per file, numbered in dependency order.