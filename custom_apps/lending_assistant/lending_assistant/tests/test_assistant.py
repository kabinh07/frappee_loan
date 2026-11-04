import json
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from lending_assistant.assistant import runner, tools


class FakeBlock:
	def __init__(self, data):
		self._d = data

	def model_dump(self, **kwargs):
		return dict(self._d)


class FakeStream:
	def __init__(self, blocks, stop_reason):
		self._blocks, self._stop = blocks, stop_reason

	def __enter__(self):
		return self

	def __exit__(self, *a):
		return False

	@property
	def text_stream(self):
		for b in self._blocks:
			if b.get("type") == "text":
				yield b["text"]

	def get_final_message(self):
		return SimpleNamespace(content=[FakeBlock(b) for b in self._blocks], stop_reason=self._stop)


class FakeClient:
	def __init__(self, turns):
		self._turns = list(turns)
		self.calls = []
		self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

	def _stream(self, **kwargs):
		self.calls.append(json.loads(json.dumps(kwargs["messages"], default=str)))
		blocks, stop = self._turns.pop(0)
		return FakeStream(blocks, stop)


def _new_conversation(user="Administrator", text="hi"):
	doc = frappe.new_doc("Lending Assistant Conversation")
	doc.user = user
	doc.title = text
	doc.messages_json = json.dumps([{"role": "user", "content": text}])
	doc.display_json = json.dumps([{"role": "user", "text": text}])
	doc.insert(ignore_permissions=True)
	return doc.name


class TestTools(IntegrationTestCase):
	def test_read_source_blocks_traversal(self):
		text, is_err = tools.execute("read_source", {"path": "../../../etc/passwd"})
		self.assertTrue(is_err)
		text, is_err = tools.execute("read_source", {"path": "../../sites/common_site_config.json"})
		self.assertTrue(is_err)

	def test_read_source_system_manager_only(self):
		frappe.set_user("Guest")
		_, is_err = tools.execute("read_source", {"path": "hooks.py"})
		frappe.set_user("Administrator")
		self.assertTrue(is_err)

	def test_read_source_reads_lending_file(self):
		text, is_err = tools.execute("read_source", {"path": "hooks.py", "start": 1, "end": 5})
		self.assertFalse(is_err, text)
		self.assertTrue(text.startswith("1: "))

	def test_schema_returns_real_fields(self):
		text, is_err = tools.execute("get_doctype_schema", {"doctype": "Loan Product"})
		self.assertFalse(is_err, text)
		fieldnames = {f["fieldname"] for f in json.loads(text)["fields"]}
		self.assertIn("product_code", fieldnames)

	def test_schema_unknown_doctype(self):
		_, is_err = tools.execute("get_doctype_schema", {"doctype": "No Such Doctype"})
		self.assertTrue(is_err)

	def test_list_records_rejects_bad_field_and_filter(self):
		_, e1 = tools.execute("list_records", {"doctype": "Loan Product", "fields": ["name; drop table x"]})
		_, e2 = tools.execute("list_records", {"doctype": "Loan Product", "filters": {"nope": 1}})
		self.assertTrue(e1 and e2)

	def test_list_records_limit_capped(self):
		text, is_err = tools.execute("list_records", {"doctype": "User", "limit": 1000})
		self.assertFalse(is_err, text)
		self.assertLessEqual(json.loads(text)["count"], tools.MAX_RECORDS)

	def test_bad_input_type(self):
		_, is_err = tools.execute("get_doctype_schema", {"doctype": 5})
		self.assertTrue(is_err)
		_, is_err = tools.execute("get_doctype_schema", "not a dict")
		self.assertTrue(is_err)

	def test_no_write_calls_in_tools_source(self):
		with open(tools.__file__) as fh:
			src = fh.read()
		for bad in (".insert(", ".save(", ".submit(", ".delete(", "db_set", "db.set_value", "delete_doc", "frappe.db.sql"):
			self.assertNotIn(bad, src)


class TestRunner(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_tool_round_then_end_turn_is_append_only(self):
		name = _new_conversation()
		client = FakeClient(
			[
				([{"type": "tool_use", "id": "tu_1", "name": "list_lending_doctypes", "input": {}}], "tool_use"),
				([{"type": "text", "text": "Create a Loan Product first."}], "end_turn"),
			]
		)
		with patch.object(runner, "_publish"):
			runner.run(name, "Administrator", client=client)
		doc = frappe.get_doc("Lending Assistant Conversation", name)
		msgs = json.loads(doc.messages_json)
		self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user", "assistant"])
		self.assertEqual(msgs[2]["content"][0]["tool_use_id"], "tu_1")
		self.assertEqual(doc.status, "idle")
		self.assertEqual(json.loads(doc.display_json)[-1]["text"], "Create a Loan Product first.")
		# round 2 saw round 1 history unchanged (append-only prefix)
		self.assertEqual(client.calls[1][: len(client.calls[0])], client.calls[0])

	def test_refusal_does_not_run_tools_and_keeps_history_valid(self):
		name = _new_conversation()
		client = FakeClient([([{"type": "tool_use", "id": "tu_9", "name": "read_source", "input": {}}], "refusal")])
		with patch.object(runner, "_publish"), patch.object(tools, "execute") as ex:
			runner.run(name, "Administrator", client=client)
		ex.assert_not_called()
		msgs = json.loads(frappe.get_doc("Lending Assistant Conversation", name).messages_json)
		self.assertTrue(msgs[-1]["content"][0]["is_error"])

	def test_max_tokens_does_not_run_tools(self):
		name = _new_conversation()
		client = FakeClient([([{"type": "tool_use", "id": "tu_8", "name": "read_source", "input": {}}], "max_tokens")])
		with patch.object(runner, "_publish"), patch.object(tools, "execute") as ex:
			runner.run(name, "Administrator", client=client)
		ex.assert_not_called()

	def test_other_users_conversation_is_ignored(self):
		name = _new_conversation(user="Administrator")
		client = FakeClient([])
		with patch.object(runner, "_publish"):
			runner.run(name, "Guest", client=client)
		frappe.set_user("Administrator")
		self.assertEqual(client.calls, [])
