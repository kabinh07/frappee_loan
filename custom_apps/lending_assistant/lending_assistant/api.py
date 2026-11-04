import json

import frappe
from frappe import _

from lending_assistant.lending_assistant.doctype.lending_assistant_settings.lending_assistant_settings import (
	get_api_key,
)

MAX_MESSAGE_CHARS = 4000
MAX_CONTEXT_CHARS = 6000
CONVERSATION = "Lending Assistant Conversation"


def _require_desk_user():
	if frappe.session.user == "Guest" or frappe.db.get_value("User", frappe.session.user, "user_type") != "System User":
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _own(name: str):
	"""Load a conversation owned by the session user. Raises otherwise."""
	if not name or not frappe.db.exists(CONVERSATION, name):
		frappe.throw(_("Conversation not found"), frappe.DoesNotExistError)
	doc = frappe.get_doc(CONVERSATION, name)
	if doc.user != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


@frappe.whitelist()
def status():
	_require_desk_user()
	settings = frappe.get_single("Lending Assistant Settings")
	return {
		"enabled": bool(settings.enabled),
		"has_key": bool(get_api_key()),
		"is_system_manager": "System Manager" in frappe.get_roles(),
	}


@frappe.whitelist()
def get_conversations():
	_require_desk_user()
	return frappe.get_all(
		CONVERSATION,
		filters={"user": frappe.session.user},
		fields=["name", "title", "status", "modified"],
		order_by="modified desc",
		limit_page_length=30,
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_conversation(name: str):
	_require_desk_user()
	doc = _own(name)
	return {
		"name": doc.name,
		"title": doc.title,
		"status": doc.status,
		"messages": json.loads(doc.display_json) if doc.display_json else [],
	}


@frappe.whitelist(methods=["POST"])
def send_message(message: str, conversation: str | None = None, context: str | None = None):
	_require_desk_user()
	settings = frappe.get_single("Lending Assistant Settings")
	if not settings.enabled:
		frappe.throw(_("Lending Assistant is disabled."))
	if not get_api_key():
		frappe.throw(_("No Anthropic API key set. Add it in Lending Assistant Settings."))

	message = (message or "").strip()
	if not message:
		frappe.throw(_("Message is empty."))
	if len(message) > MAX_MESSAGE_CHARS:
		frappe.throw(_("Message too long (max {0} characters).").format(MAX_MESSAGE_CHARS))

	page_context = ""
	if context:
		try:
			ctx = json.loads(context)
			page_context = json.dumps(ctx, default=str)[:MAX_CONTEXT_CHARS]
		except (TypeError, ValueError):
			page_context = ""

	if conversation:
		doc = _own(conversation)
		if doc.status == "running":
			frappe.throw(_("The assistant is still answering. Wait for it to finish."))
	else:
		doc = frappe.new_doc(CONVERSATION)
		doc.user = frappe.session.user
		doc.title = message[:60]
		doc.insert(ignore_permissions=True)

	user_text = f"<page_context>{page_context}</page_context>\n\n{message}" if page_context else message
	messages = json.loads(doc.messages_json) if doc.messages_json else []
	messages.append({"role": "user", "content": user_text})
	display = json.loads(doc.display_json) if doc.display_json else []
	display.append({"role": "user", "text": message})

	frappe.db.set_value(
		CONVERSATION,
		doc.name,
		{"messages_json": json.dumps(messages), "display_json": json.dumps(display), "status": "running"},
	)
	frappe.db.commit()

	frappe.enqueue(
		"lending_assistant.assistant.runner.run",
		queue="long",
		timeout=600,
		conversation=doc.name,
		user=frappe.session.user,
		enqueue_after_commit=True,
	)
	return {"conversation": doc.name}
