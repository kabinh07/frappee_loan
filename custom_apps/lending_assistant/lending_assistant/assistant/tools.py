"""Read-only tools the assistant can call. No tool writes to the database or filesystem.

Every tool runs as the session user and respects Frappe permissions. Inputs are validated
here because tool inputs are streamed eagerly and may arrive incomplete or malformed.
"""

import fnmatch
import json
import os
import re
import time

import frappe

MAX_CHARS = 20000
MAX_RECORDS = 20
MAX_SOURCE_LINES = 400
MAX_SEARCH_HITS = 50
SOURCE_EXTENSIONS = (".py", ".js", ".json")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GUIDE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+\.md$")
SAFE_META_FIELDS = {"name", "creation", "modified", "owner", "docstatus", "modified_by"}
FILTER_OPS = {"=", "!=", ">", "<", ">=", "<=", "like", "not like", "in", "not in", "is", "between"}

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")


class ToolError(Exception):
	"""Raised for bad input or denied access. Message goes back to the model."""


TOOL_DEFS = [
	{
		"name": "list_lending_doctypes",
		"description": (
			"List every DocType that belongs to the installed `lending` app (name, whether it is a "
			"child table, single, or submittable). Use first when unsure which doctype covers a topic."
		),
		"input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
	},
	{
		"name": "get_doctype_schema",
		"description": (
			"Get the real field list of a DocType from the running site (includes custom fields): "
			"fieldname, label, fieldtype, options, reqd, depends_on, mandatory_depends_on, read_only, "
			"default. Call before naming any field to the user."
		),
		"input_schema": {
			"type": "object",
			"properties": {"doctype": {"type": "string", "description": "Exact DocType name, e.g. 'Loan Product'"}},
			"required": ["doctype"],
			"additionalProperties": False,
		},
	},
	{
		"name": "read_guide",
		"description": (
			"Read one curated guide file from the project's lending-docs (source-verified for this "
			"build). Pass a filename such as '10-loan-product.md', 'WORKFLOW.md' or '12-first-loan-walkthrough.md'. "
			"Pass an empty name to list available files."
		),
		"input_schema": {
			"type": "object",
			"properties": {"name": {"type": "string"}},
			"required": ["name"],
			"additionalProperties": False,
		},
	},
	{
		"name": "search_source",
		"description": (
			"Regex search in the installed lending app source (.py/.js/.json). System Manager only. "
			"Returns up to 50 'path:line: text' hits. `glob` optionally filters relative paths, "
			"e.g. 'loan_management/doctype/loan_product/*'."
		),
		"input_schema": {
			"type": "object",
			"properties": {"pattern": {"type": "string"}, "glob": {"type": "string"}},
			"required": ["pattern"],
			"additionalProperties": False,
		},
	},
	{
		"name": "read_source",
		"description": (
			"Read lines from a file inside the installed lending app. System Manager only. `path` is "
			"relative to the app package root (as returned by search_source). Max 400 lines per call."
		),
		"input_schema": {
			"type": "object",
			"properties": {
				"path": {"type": "string"},
				"start": {"type": "integer", "description": "1-based first line, default 1"},
				"end": {"type": "integer", "description": "last line, default start+199"},
			},
			"required": ["path"],
			"additionalProperties": False,
		},
	},
	{
		"name": "list_records",
		"description": (
			"List existing records of a DocType on this site, respecting the user's permissions. "
			"Max 20 rows. Use to check which prerequisites already exist (e.g. does any Loan Product exist). "
			"`filters` is an object like {\"disabled\": 0} or {\"status\": [\"in\", [\"Open\", \"Approved\"]]}."
		),
		"input_schema": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string"},
				"filters": {"type": "object"},
				"fields": {"type": "array", "items": {"type": "string"}},
				"limit": {"type": "integer"},
			},
			"required": ["doctype"],
			"additionalProperties": False,
		},
	},
	{
		"name": "get_record",
		"description": "Read one record (by DocType and name) if the user may read it. Password fields are removed.",
		"input_schema": {
			"type": "object",
			"properties": {"doctype": {"type": "string"}, "name": {"type": "string"}},
			"required": ["doctype", "name"],
			"additionalProperties": False,
		},
	},
]

for _t in TOOL_DEFS:
	_t["eager_input_streaming"] = True


# ---------- helpers ----------


def _require_str(args: dict, key: str, max_len: int = 200, required: bool = True) -> str:
	value = args.get(key)
	if value is None or value == "":
		if required:
			raise ToolError(f"Missing required string '{key}'.")
		return ""
	if not isinstance(value, str):
		raise ToolError(f"'{key}' must be a string.")
	if len(value) > max_len:
		raise ToolError(f"'{key}' too long (max {max_len}).")
	return value


def _cap(obj) -> str:
	text = json.dumps(obj, default=str, indent=1, ensure_ascii=False)
	if len(text) > MAX_CHARS:
		return text[:MAX_CHARS] + f"\n... [truncated at {MAX_CHARS} chars]"
	return text


def _is_system_manager() -> bool:
	return "System Manager" in frappe.get_roles()


def _lending_modules() -> list[str]:
	return list(frappe.get_module_list("lending"))


def _check_doctype(doctype: str, ptype: str = "read"):
	if not frappe.db.exists("DocType", doctype):
		raise ToolError(f"DocType '{doctype}' does not exist on this site.")
	if not frappe.has_permission(doctype, ptype):
		raise ToolError(f"You do not have {ptype} permission on '{doctype}'.")
	return frappe.get_meta(doctype)


def _app_root() -> str:
	return os.path.realpath(frappe.get_app_path("lending"))


def _safe_source_path(rel: str) -> str:
	root = _app_root()
	full = os.path.realpath(os.path.join(root, rel))
	if os.path.commonpath([root, full]) != root:
		raise ToolError("Path is outside the lending app.")
	if not full.endswith(SOURCE_EXTENSIONS):
		raise ToolError(f"Only {', '.join(SOURCE_EXTENSIONS)} files can be read.")
	if not os.path.isfile(full):
		raise ToolError("File not found.")
	return full


def _require_system_manager():
	if not _is_system_manager():
		raise ToolError("Reading source requires the System Manager role. Use get_doctype_schema or read_guide instead.")


def _walk_source():
	root = _app_root()
	for dirpath, dirnames, filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if d not in ("node_modules", "__pycache__", ".git", "public")]
		for fn in filenames:
			if fn.endswith(SOURCE_EXTENSIONS):
				full = os.path.join(dirpath, fn)
				yield full, os.path.relpath(full, root)


# ---------- tools ----------


def list_lending_doctypes(args: dict) -> str:
	modules = _lending_modules()
	rows = frappe.get_all(
		"DocType",
		filters={"module": ["in", modules]},
		fields=["name", "module", "istable", "issingle", "is_submittable", "custom"],
		order_by="name asc",
		limit_page_length=500,
	)
	return _cap({"modules": modules, "doctypes": rows})


def get_doctype_schema(args: dict) -> str:
	doctype = _require_str(args, "doctype")
	meta = _check_doctype(doctype)
	fields = []
	for df in meta.fields:
		fields.append(
			{
				k: v
				for k, v in {
					"fieldname": df.fieldname,
					"label": df.label,
					"fieldtype": df.fieldtype,
					"options": df.options,
					"reqd": df.reqd or None,
					"depends_on": df.depends_on,
					"mandatory_depends_on": df.mandatory_depends_on,
					"read_only": df.read_only or None,
					"hidden": df.hidden or None,
					"default": df.default,
				}.items()
				if v not in (None, "", 0)
			}
		)
	return _cap(
		{
			"doctype": doctype,
			"module": meta.module,
			"is_submittable": bool(meta.is_submittable),
			"is_child_table": bool(meta.istable),
			"is_single": bool(meta.issingle),
			"autoname": meta.autoname,
			"title_field": meta.title_field,
			"child_tables": [df.options for df in meta.fields if df.fieldtype in ("Table", "Table MultiSelect")],
			"fields": fields,
		}
	)


def read_guide(args: dict) -> str:
	name = _require_str(args, "name", required=False)
	available = sorted(f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".md")) if os.path.isdir(KNOWLEDGE_DIR) else []
	if not name:
		return _cap({"available": available})
	if not GUIDE_NAME.match(name) or name not in available:
		raise ToolError(f"Unknown guide '{name}'. Available: {', '.join(available) or 'none'}")
	with open(os.path.join(KNOWLEDGE_DIR, name), encoding="utf-8") as fh:
		text = fh.read()
	if len(text) > MAX_CHARS * 2:
		text = text[: MAX_CHARS * 2] + "\n... [truncated]"
	return text


def search_source(args: dict) -> str:
	_require_system_manager()
	pattern = _require_str(args, "pattern", max_len=200)
	glob = _require_str(args, "glob", max_len=200, required=False)
	try:
		rx = re.compile(pattern)
	except re.error as e:
		raise ToolError(f"Invalid regex: {e}") from e
	hits: list[str] = []
	deadline = time.monotonic() + 10
	for full, rel in _walk_source():
		if glob and not fnmatch.fnmatch(rel, glob):
			continue
		if time.monotonic() > deadline:
			hits.append("... [search timed out, narrow the pattern or glob]")
			break
		try:
			with open(full, encoding="utf-8", errors="replace") as fh:
				for i, line in enumerate(fh, 1):
					if rx.search(line):
						hits.append(f"{rel}:{i}: {line.strip()[:200]}")
						if len(hits) >= MAX_SEARCH_HITS:
							break
		except OSError:
			continue
		if len(hits) >= MAX_SEARCH_HITS:
			hits.append(f"... [stopped at {MAX_SEARCH_HITS} hits]")
			break
	return "\n".join(hits) if hits else "No matches."


def read_source(args: dict) -> str:
	_require_system_manager()
	rel = _require_str(args, "path", max_len=300)
	full = _safe_source_path(rel)
	start = args.get("start", 1)
	if not isinstance(start, int) or start < 1:
		raise ToolError("'start' must be an integer >= 1.")
	end = args.get("end", start + 199)
	if not isinstance(end, int) or end < start:
		raise ToolError("'end' must be an integer >= start.")
	end = min(end, start + MAX_SOURCE_LINES - 1)
	out = []
	with open(full, encoding="utf-8", errors="replace") as fh:
		for i, line in enumerate(fh, 1):
			if i < start:
				continue
			if i > end:
				break
			out.append(f"{i}: {line.rstrip()[:300]}")
	return "\n".join(out) if out else "(no lines in range)"


def _valid_fieldnames(meta) -> set[str]:
	skip = {"Password", "Table", "Table MultiSelect"}
	return {df.fieldname for df in meta.fields if df.fieldname and df.fieldtype not in skip} | SAFE_META_FIELDS


def _validate_filters(filters, valid: set[str]):
	if filters is None:
		return None
	if not isinstance(filters, dict):
		raise ToolError("'filters' must be an object of fieldname -> value or [operator, value].")
	clean = {}
	for key, value in filters.items():
		if key not in valid:
			raise ToolError(f"Unknown or disallowed filter field '{key}'.")
		if isinstance(value, list):
			if len(value) != 2 or not isinstance(value[0], str) or value[0].lower() not in FILTER_OPS:
				raise ToolError(f"Filter for '{key}' must be [operator, value] with operator in {sorted(FILTER_OPS)}.")
			clean[key] = [value[0].lower(), value[1]]
		elif isinstance(value, (str, int, float, bool)) or value is None:
			clean[key] = value
		else:
			raise ToolError(f"Unsupported filter value for '{key}'.")
	return clean


def list_records(args: dict) -> str:
	doctype = _require_str(args, "doctype")
	meta = _check_doctype(doctype)
	valid = _valid_fieldnames(meta)
	fields = args.get("fields")
	if fields is None:
		fields = ["name"] + [f for f in ("title", "status", "disabled", "docstatus") if f in valid]
	if not isinstance(fields, list) or not fields or len(fields) > 20:
		raise ToolError("'fields' must be a list of 1-20 fieldnames.")
	for f in fields:
		if not isinstance(f, str) or not IDENT.match(f) or f not in valid:
			raise ToolError(f"Unknown or disallowed field '{f}'.")
	limit = args.get("limit", 10)
	if not isinstance(limit, int) or limit < 1:
		raise ToolError("'limit' must be a positive integer.")
	limit = min(limit, MAX_RECORDS)
	filters = _validate_filters(args.get("filters"), valid)
	rows = frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=limit, order_by="modified desc")
	return _cap({"doctype": doctype, "count": len(rows), "rows": rows})


def get_record(args: dict) -> str:
	doctype = _require_str(args, "doctype")
	name = _require_str(args, "name")
	meta = _check_doctype(doctype)
	if not frappe.db.exists(doctype, name):
		raise ToolError(f"{doctype} '{name}' not found.")
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	data = doc.as_dict(no_nulls=True)
	password_fields = {df.fieldname for df in meta.fields if df.fieldtype == "Password"}
	for key in list(data):
		if key in password_fields:
			data.pop(key)
	return _cap(data)


TOOLS = {
	"list_lending_doctypes": list_lending_doctypes,
	"get_doctype_schema": get_doctype_schema,
	"read_guide": read_guide,
	"search_source": search_source,
	"read_source": read_source,
	"list_records": list_records,
	"get_record": get_record,
}

STATUS_TEXT = {
	"list_lending_doctypes": "Listing lending doctypes…",
	"get_doctype_schema": "Reading schema of {doctype}…",
	"read_guide": "Reading guide {name}…",
	"search_source": "Searching lending source…",
	"read_source": "Reading source {path}…",
	"list_records": "Checking existing {doctype} records…",
	"get_record": "Reading {doctype} {name}…",
}


def status_text(name: str, args) -> str:
	tpl = STATUS_TEXT.get(name, f"Running {name}…")
	try:
		return tpl.format(**{k: str(v)[:60] for k, v in (args or {}).items()})
	except (KeyError, IndexError, AttributeError):
		return tpl.split("{")[0].rstrip() + "…"


def execute(name: str, args) -> tuple[str, bool]:
	"""Run a tool. Returns (text, is_error). Never raises."""
	fn = TOOLS.get(name)
	if fn is None:
		return f"Unknown tool '{name}'.", True
	if not isinstance(args, dict):
		return "Tool input must be a JSON object.", True
	try:
		return fn(args), False
	except ToolError as e:
		return str(e), True
	except Exception:
		frappe.log_error(title=f"Lending Assistant tool failed: {name}")
		return "Tool failed unexpectedly. See Error Log.", True
