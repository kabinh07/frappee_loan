"""Claude agentic loop. Runs in a background job (queue `long`), streams to the browser
over Frappe realtime, persists an append-only message history.
"""

import json

import anthropic
import frappe

from lending_assistant.assistant import tools as toolbox
from lending_assistant.assistant.prompt import build_system_prompt
from lending_assistant.lending_assistant.doctype.lending_assistant_settings.lending_assistant_settings import (
	get_api_key,
)

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 64000
EVENT_DELTA = "lending_assistant_delta"
EVENT_STATUS = "lending_assistant_status"
EVENT_DONE = "lending_assistant_done"
EVENT_ERROR = "lending_assistant_error"


class MissingApiKey(Exception):
	pass


def _publish(event: str, conversation: str, user: str, **data):
	frappe.publish_realtime(event, {"conversation": conversation, **data}, user=user)


def _settings():
	s = frappe.get_single("Lending Assistant Settings")
	rounds = s.max_tool_rounds or 10
	return {
		"model": (s.model or DEFAULT_MODEL).strip(),
		"effort": s.effort or "medium",
		"max_rounds": max(1, min(int(rounds), 25)),
	}


def _load(doc, field: str) -> list:
	raw = doc.get(field)
	return json.loads(raw) if raw else []


def _fail_tool_uses(blocks: list[dict], reason: str) -> dict | None:
	"""Pair any tool_use block with an error result so the saved history stays valid."""
	results = [
		{"type": "tool_result", "tool_use_id": b["id"], "content": reason, "is_error": True}
		for b in blocks
		if b.get("type") == "tool_use"
	]
	return {"role": "user", "content": results} if results else None


def run(conversation: str, user: str, client=None):
	"""Entry point for the background job. `client` is injectable for tests."""
	frappe.set_user(user)
	doc = frappe.get_doc("Lending Assistant Conversation", conversation)
	if doc.user != user:
		return

	display = _load(doc, "display_json")
	messages = _load(doc, "messages_json")
	final_text: list[str] = []
	error: str | None = None

	try:
		if client is None:
			api_key = get_api_key()
			if not api_key:
				raise MissingApiKey
			client = anthropic.Anthropic(api_key=api_key)
		cfg = _settings()
		system = build_system_prompt()

		for _round in range(cfg["max_rounds"]):
			with client.beta.messages.stream(
				model=cfg["model"],
				max_tokens=MAX_TOKENS,
				system=system,
				messages=messages,
				tools=toolbox.TOOL_DEFS,
				tool_choice={"type": "auto"},
				thinking={"type": "adaptive"},
				output_config={"effort": cfg["effort"]},
				cache_control={"type": "ephemeral"},
				betas=["server-side-fallback-2026-07-01"],
				fallbacks="default",
			) as stream:
				for text in stream.text_stream:
					_publish(EVENT_DELTA, conversation, user, text=text)
				message = stream.get_final_message()

			blocks = [b.model_dump(mode="json", exclude_none=True) for b in message.content]
			messages.append({"role": "assistant", "content": blocks})
			round_text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
			if round_text:
				final_text.append(round_text)

			stop = message.stop_reason
			if stop == "tool_use":
				results = []
				for b in blocks:
					if b.get("type") != "tool_use":
						continue
					_publish(EVENT_STATUS, conversation, user, text=toolbox.status_text(b["name"], b.get("input")))
					out, is_err = toolbox.execute(b["name"], b.get("input"))
					res = {"type": "tool_result", "tool_use_id": b["id"], "content": out}
					if is_err:
						res["is_error"] = True
					results.append(res)
				messages.append({"role": "user", "content": results})
				continue
			if stop == "pause_turn":
				continue
			if stop == "refusal":
				pending = _fail_tool_uses(blocks, "Not executed: the request was declined.")
				if pending:
					messages.append(pending)
				final_text.append("_The model declined to answer this request. Try rephrasing._")
				break
			if stop == "max_tokens":
				pending = _fail_tool_uses(blocks, "Not executed: the response was cut off.")
				if pending:
					messages.append(pending)
				final_text.append("_The answer was cut off. Ask me to continue._")
				break
			break  # end_turn and anything else
		else:
			final_text.append("_Stopped after the maximum number of tool rounds. Ask me to continue._")

	except anthropic.AuthenticationError:
		error = "API key is invalid. Set it in Lending Assistant Settings."
	except anthropic.RateLimitError:
		error = "Rate limited by the Anthropic API. Try again in a minute."
	except anthropic.APIConnectionError:
		error = "Could not reach the Anthropic API. Check the server's network."
	except anthropic.APIStatusError as e:
		frappe.log_error(title="Lending Assistant API error")
		error = f"Anthropic API error ({e.status_code})."
	except MissingApiKey:
		error = "No API key set. Add it in Lending Assistant Settings."
	except Exception:
		frappe.log_error(title="Lending Assistant failed")
		error = "Unexpected error. See Error Log."

	# Drop a dangling assistant tool_use turn if an exception interrupted a tool round.
	if error and messages and messages[-1].get("role") == "assistant":
		pending = _fail_tool_uses(messages[-1].get("content", []), "Not executed: an error interrupted this turn.")
		if pending:
			messages.append(pending)

	answer = "\n\n".join(final_text).strip()
	if error:
		display.append({"role": "assistant", "text": error, "error": True})
	elif answer:
		display.append({"role": "assistant", "text": answer})

	frappe.db.set_value(
		"Lending Assistant Conversation",
		conversation,
		{
			"messages_json": json.dumps(messages),
			"display_json": json.dumps(display),
			"status": "idle",
		},
		update_modified=True,
	)
	frappe.db.commit()

	if error:
		_publish(EVENT_ERROR, conversation, user, text=error)
	else:
		_publish(EVENT_DONE, conversation, user, text=answer)
