import os

import frappe
from frappe.model.document import Document


class LendingAssistantSettings(Document):
	pass


def get_api_key() -> str | None:
	"""Settings field, then site_config `anthropic_api_key`, then env ANTHROPIC_API_KEY."""
	key = None
	try:
		key = frappe.get_single("Lending Assistant Settings").get_password("api_key", raise_exception=False)
	except Exception:
		key = None
	return key or frappe.conf.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or None
