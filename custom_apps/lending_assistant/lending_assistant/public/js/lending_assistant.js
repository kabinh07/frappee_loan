(function () {
	"use strict";

	const API = "lending_assistant.api.";
	const state = { conversation: null, busy: false, stream: null, ready: false };
	let el = {};

	function esc(s) {
		return frappe.utils.escape_html(String(s == null ? "" : s));
	}

	function renderMarkdown(text) {
		try {
			// frappe.markdown already sanitizes its output (strips event-handler attributes).
			return frappe.markdown(text);
		} catch (e) {
			return esc(text).replace(/\n/g, "<br>");
		}
	}

	function getContext() {
		const ctx = { route: frappe.get_route_str ? frappe.get_route_str() : "" };
		const frm = window.cur_frm;
		if (frm && frm.doc) {
			ctx.doctype = frm.doctype;
			ctx.docname = frm.docname;
			ctx.is_new = frm.is_new();
			ctx.docstatus = frm.doc.docstatus;
			const values = {};
			const empty_required = [];
			(frm.meta.fields || []).forEach((df) => {
				if (!df.fieldname || ["Section Break", "Column Break", "Tab Break", "HTML", "Button"].includes(df.fieldtype)) return;
				const v = frm.doc[df.fieldname];
				if (df.fieldtype === "Table") {
					values[df.fieldname] = `${(v || []).length} row(s)`;
					return;
				}
				if (df.fieldtype === "Password") return;
				const blank = v === undefined || v === null || v === "";
				if (!blank) values[df.fieldname] = String(v).slice(0, 120);
				if (blank && df.reqd) empty_required.push(df.fieldname);
			});
			ctx.values = values;
			ctx.empty_required_fields = empty_required;
		}
		return ctx;
	}

	function scroll() {
		el.msgs.scrollTop = el.msgs.scrollHeight;
	}

	function addMsg(role, text, opts = {}) {
		const div = document.createElement("div");
		div.className = "la-msg " + (role === "user" ? "la-user" : "la-bot") + (opts.error ? " la-error" : "");
		if (role === "user") div.textContent = text;
		else div.innerHTML = renderMarkdown(text);
		el.msgs.appendChild(div);
		scroll();
		return div;
	}

	function setStatus(text) {
		el.status.textContent = text || "";
	}

	function setBusy(busy) {
		state.busy = busy;
		el.send.disabled = busy;
		el.input.disabled = busy;
		if (!busy) {
			setStatus("");
			pollStop();
		}
	}

	// Fallback when realtime (socket.io) cannot connect, e.g. browser origin differs from the
	// site name nginx reports (opening the site by IP). Polls until the job leaves "running".
	function pollStop() {
		if (state.poll) clearInterval(state.poll);
		state.poll = null;
	}

	function pollStart() {
		pollStop();
		state.poll = setInterval(() => {
			if (!state.conversation || !state.busy) return pollStop();
			frappe
				.call({ method: API + "get_conversation", args: { name: state.conversation }, silent: true })
				.then((r) => {
					const c = r.message;
					if (!c || c.status === "running" || !state.busy) return;
					const last = (c.messages || []).slice(-1)[0];
					if (state.stream) {
						state.stream.remove();
						state.stream = null;
					}
					if (last && last.role !== "user") addMsg("bot", last.text, { error: last.error });
					setBusy(false);
				});
		}, 2500);
	}

	function showNotice(html) {
		el.msgs.innerHTML = "";
		const n = document.createElement("div");
		n.className = "la-notice";
		n.innerHTML = html;
		el.msgs.appendChild(n);
	}

	function welcome() {
		el.msgs.innerHTML = "";
		addMsg("bot", "Hi. Tell me what you want to do in Lending (for example: *create a loan product*, *process my first loan*). I will guide you one step at a time.");
	}

	function loadConversations() {
		return frappe.call({ method: API + "get_conversations" }).then((r) => {
			el.picker.innerHTML = '<option value="">History…</option>';
			(r.message || []).forEach((c) => {
				const o = document.createElement("option");
				o.value = c.name;
				o.textContent = c.title || c.name;
				el.picker.appendChild(o);
			});
		});
	}

	function openConversation(name) {
		return frappe.call({ method: API + "get_conversation", args: { name } }).then((r) => {
			const c = r.message;
			state.conversation = c.name;
			el.msgs.innerHTML = "";
			(c.messages || []).forEach((m) => addMsg(m.role === "user" ? "user" : "bot", m.text, { error: m.error }));
			if (c.status === "running") {
				setBusy(true);
				setStatus("Working…");
				state.stream = addMsg("bot", "…");
				state.stream._raw = "";
				pollStart();
			}
			scroll();
		});
	}

	function newChat() {
		state.conversation = null;
		state.stream = null;
		setBusy(false);
		el.picker.value = "";
		welcome();
	}

	function send() {
		const text = el.input.value.trim();
		if (!text || state.busy) return;
		el.input.value = "";
		addMsg("user", text);
		setBusy(true);
		setStatus("Thinking…");
		state.stream = addMsg("bot", "…");
		state.stream._raw = "";
		frappe.call({
			method: API + "send_message",
			type: "POST",
			args: { message: text, conversation: state.conversation, context: JSON.stringify(getContext()) },
			callback: (r) => {
				state.conversation = r.message.conversation;
				loadConversations();
				pollStart();
			},
			error: () => {
				setBusy(false);
				if (state.stream) state.stream.remove();
				state.stream = null;
			},
		});
	}

	function bindRealtime() {
		const mine = (d) => d && d.conversation === state.conversation;
		frappe.realtime.on("lending_assistant_delta", (d) => {
			if (!mine(d) || !state.stream) return;
			state.stream._raw += d.text;
			state.stream.innerHTML = renderMarkdown(state.stream._raw);
			setStatus("Writing…");
			scroll();
		});
		frappe.realtime.on("lending_assistant_status", (d) => {
			if (mine(d)) setStatus(d.text);
		});
		frappe.realtime.on("lending_assistant_done", (d) => {
			if (!mine(d)) return;
			if (state.stream) {
				state.stream.innerHTML = renderMarkdown(d.text || state.stream._raw || "(no answer)");
				state.stream = null;
			}
			setBusy(false);
			scroll();
		});
		frappe.realtime.on("lending_assistant_error", (d) => {
			if (!mine(d)) return;
			if (state.stream) {
				state.stream.remove();
				state.stream = null;
			}
			addMsg("bot", d.text, { error: true });
			setBusy(false);
		});
	}

	function toggle(open) {
		const show = open === undefined ? !el.panel.classList.contains("la-open") : open;
		el.panel.classList.toggle("la-open", show);
		if (show && !state.ready) init();
		if (show && el.input) el.input.focus();
	}

	function init() {
		state.ready = true;
		frappe.call({ method: API + "status" }).then((r) => {
			const s = r.message || {};
			if (!s.enabled) {
				showNotice("The Lending Assistant is disabled. A System Manager can enable it in <b>Lending Assistant Settings</b>.");
				el.form.style.display = "none";
				return;
			}
			if (!s.has_key) {
				showNotice(
					"No Anthropic API key yet. " +
						(s.is_system_manager
							? 'Add it in <a href="/app/lending-assistant-settings">Lending Assistant Settings</a>.'
							: "Ask a System Manager to add it in Lending Assistant Settings.")
				);
				el.form.style.display = "none";
				return;
			}
			welcome();
			loadConversations();
			bindRealtime();
		});
	}

	function build() {
		const fab = document.createElement("button");
		fab.className = "la-fab";
		fab.title = "Lending Assistant";
		fab.setAttribute("aria-label", "Open Lending Assistant");
		fab.textContent = "✦";

		const panel = document.createElement("div");
		panel.className = "la-panel";
		panel.innerHTML =
			'<div class="la-head"><span class="la-title">Lending Assistant</span>' +
			'<select class="form-control input-xs la-picker"></select>' +
			'<button class="btn btn-xs btn-default la-new">New</button>' +
			'<button class="btn btn-xs btn-default la-close" aria-label="Close">✕</button></div>' +
			'<div class="la-msgs"></div><div class="la-status"></div>' +
			'<div class="la-form"><textarea class="form-control la-input" placeholder="Ask how to do something…"></textarea>' +
			'<button class="btn btn-primary btn-sm la-send">Send</button></div>';
		document.body.appendChild(fab);
		document.body.appendChild(panel);

		el = {
			fab,
			panel,
			msgs: panel.querySelector(".la-msgs"),
			status: panel.querySelector(".la-status"),
			input: panel.querySelector(".la-input"),
			send: panel.querySelector(".la-send"),
			picker: panel.querySelector(".la-picker"),
			form: panel.querySelector(".la-form"),
		};

		fab.addEventListener("click", () => toggle());
		panel.querySelector(".la-close").addEventListener("click", () => toggle(false));
		panel.querySelector(".la-new").addEventListener("click", newChat);
		el.send.addEventListener("click", send);
		el.picker.addEventListener("change", () => el.picker.value && openConversation(el.picker.value));
		el.input.addEventListener("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				send();
			}
		});
		el.msgs.addEventListener("click", (e) => {
			const a = e.target.closest("a[href^='/app/']");
			if (!a) return;
			e.preventDefault();
			frappe.set_route(a.getAttribute("href").replace(/^\/app\//, "").split("/").map(decodeURIComponent));
		});
	}

	$(document).ready(function () {
		if (!frappe.session || frappe.session.user === "Guest") return;
		if (frappe.boot && frappe.boot.user && frappe.boot.user.user_type !== "System User") return;
		build();
	});
})();
