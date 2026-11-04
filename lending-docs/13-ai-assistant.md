# 13 — AI Assistant (Desk side panel)

A chat panel on every Desk page (`/app/...`) that guides a user step by step through Frappe Lending. It is read-only: it never creates, edits, submits or deletes records. It tells the user what to click and type.

Code: `custom_apps/lending_assistant/` (a separate Frappe app, installed on top of `lending`).

## Using it

1. Click the round ✦ button at the bottom-right of any Desk page.
2. Ask a goal, for example "create a loan product" or "what do I do next on this Loan Application?".
3. On a form, the panel sends the current page context (doctype, docname, filled values, empty required fields) along with the question so the answer is specific. Password fields are never sent.

Each user sees only their own conversations. Only users of type System User get the button.

## Setting the API key

Open `/app/lending-assistant-settings` (System Manager) and fill:

| Field | Meaning |
|---|---|
| Enabled | Turns the panel on or off. |
| Anthropic API Key | Stored encrypted (Password field). |
| Model | Default `claude-opus-5-5`. |
| Effort | `low`, `medium` (default) or `high`. Higher is slower and costs more. |
| Max Tool Rounds | Model/tool round trips per question. Default 10, capped at 25. |

If the Settings field is empty, the key is read from `site_config.json` (`anthropic_api_key`), then from the environment variable `ANTHROPIC_API_KEY`. Without any key the panel shows a notice instead of the chat box.

## What the assistant can look at

All tools are read-only and run as the logged-in user, so Frappe permissions apply.

| Tool | Purpose | Who |
|---|---|---|
| `list_lending_doctypes` | DocTypes in the `lending` app | everyone |
| `get_doctype_schema` | Real fields of a DocType on this site (incl. custom fields) | needs read permission on that DocType |
| `read_guide` | Files in this `lending-docs/` folder | everyone |
| `list_records` | Up to 20 existing records, to find missing prerequisites | needs read permission |
| `get_record` | One record, Password fields removed | needs read permission |
| `search_source`, `read_source` | Search/read the installed `lending` app code | System Manager only |

The assistant's system prompt embeds `README.md` and `WORKFLOW.md` from this folder. The other module guides are loaded on demand with `read_guide`. When you change a guide here, rebuild the image (below) so the assistant sees it.

## How it works

1. Browser calls `lending_assistant.api.send_message`. The server stores the user turn and enqueues `lending_assistant.assistant.runner.run` on the `long` queue (so the 120 s gunicorn timeout does not apply).
2. The job calls the Anthropic Messages API (streaming, adaptive thinking, refusal fallback on) in a tool loop, up to Max Tool Rounds.
3. Text deltas and tool status lines are pushed to the browser over Frappe realtime (socket.io, the `websocket` service).
4. The full API history is saved in `Lending Assistant Conversation.messages_json`, append-only. The text shown in the panel is in `display_json`.

## Build and install

The assistant ships as an extra image layer, `lending-local:v16-ai`, built `FROM lending-local:v16` (see `images/lending-assistant/Containerfile`). `lending-compose.yaml` uses the `-ai` image.

- `./run.sh`: builds the base image if missing, builds the assistant layer, starts the stack, waits for the site, prints the URL (`http://<machine-ip>:8080`). Keeps existing data.
- `./run.sh --rebuild`: also rebuilds the base image with no cache.
- `./run.sh --reset`: runs `docker compose down -v` first, which destroys all site data. It asks you to type `yes`.
- `./build-assistant.sh`: older helper that does the same build and `up -d` without the wait and URL output.

`lending-compose.yaml` is one simple file. Its `init` service (a `bash -c` entrypoint) writes the bench config, creates the site on first run, and on later runs installs `lending_assistant` if missing and runs `bench migrate`. All other services wait for `init`. Services use `pull_policy: never` because the image is local-only. To pass the API key through the environment, set `ANTHROPIC_API_KEY` in the shell or a `.env` file next to the compose file (used by `backend` and `queue-long`).

## Tests

```
docker compose -f lending-compose.yaml --project-name lending exec backend bash -lc \
  'bench --site lending.localhost run-tests --app lending_assistant'
```

The tests use a fake Anthropic client, so no API key or network is needed.

## Known limits

- The assistant is only as good as the guides and live schema it reads. It is told to say "not sure" when it cannot verify a field.
- No write actions by design. Adding "create this record for me" would be a separate change with a confirm step.
- Conversations are never auto-deleted. Delete them from the `Lending Assistant Conversation` list.
