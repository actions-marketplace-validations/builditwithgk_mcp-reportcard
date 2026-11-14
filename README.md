# MCP Doctor

**A health check for MCP servers.** It lints your tools' names, descriptions, schemas and safety annotations, estimates how many tokens they cost on every turn, fuzzes error handling, and gives you a graded report card with a concrete fix for every issue.

<!-- TODO: demo GIF (bad server → report → fixes → grade D to A) -->

```text
┌──────── MCP Doctor · acme-orders (bad example) ─────────┐
│ Grade D  ·  score 67/100                                 │
│ 7 tools  ·  1 errors  ·  16 warnings  ·  5 info          │
│ ~351 tokens per turn (tiktoken o200k_base (approximate)) │
└──────────────────────────────────────────────────────────┘
  F002 lookup_invoice Error output exposes internals: `Traceback (most recent call last)`
       fix: Log stack traces server-side; return a short, safe message to the client.
  X001 server `find_items` and `search_items` are described almost the same way (88% word overlap)
       fix: Say in each description when to use it instead of the other, or merge them.
  ...
```

## Why

When an agent picks the wrong tool, sends malformed arguments, or burns context on bloated definitions, the cause is usually in the server: vague descriptions, untyped or undocumented parameters, near-duplicate tools, missing safety hints, and errors that leak stack traces. The model only sees what your `tools/list` says. MCP Doctor checks that in seconds and tells you exactly what to change.

It complements the official [MCP Inspector](https://github.com/modelcontextprotocol/inspector), which is for manual, interactive testing. MCP Doctor is automated, scored, and runs in CI.

## Install

```bash
pip install "mcp-doctor[tokens] @ git+https://github.com/builditwithgk/mcp-doctor"
```

Requires Python 3.10+. A PyPI release (`pip install mcp-doctor`) is coming soon. The `[tokens]` extra adds tiktoken for more accurate token counts.

## Usage

```bash
# A stdio server (any language): pass the command that starts it
mcp-doctor check "python server.py"
mcp-doctor check "npx -y @modelcontextprotocol/server-everything"

# A Streamable HTTP server
mcp-doctor check http://localhost:8000/mcp

# A saved tools/list JSON (offline, no server needed)
mcp-doctor check tools.json

# Also test error handling with bad inputs (read-only tools only, see "Fuzzing safety")
mcp-doctor check "python server.py" --fuzz

# Reports for PRs and CI
mcp-doctor check "python server.py" -f markdown -o report.md
mcp-doctor check "python server.py" -f json --fail-under 80

# Save a server's tool list (for offline checks or the web demo)
mcp-doctor dump "python server.py" -o tools.json

# List every check
mcp-doctor rules
```

Try it on the bundled examples: `examples/bad_server.py` scores a **D**, and `examples/good_server.py` (the same service, written properly) scores an **A**.

## What it checks

| ID | Severity | Check |
|---|---|---|
| N001–N005 | error / warning / info | Missing, duplicate, invalid or over-long names; mixed naming styles |
| D001–D005 | error / warning / info | Missing, too short, too long, or name-restating descriptions; no "when to use" guidance when a similar tool exists |
| S001–S008 | error / warning / info | Missing object schema, untyped or undocumented parameters, broken `required`, free-form objects, deep nesting, missing `enum`, too many parameters |
| A001–A002 | warning | Missing or contradictory `readOnlyHint` / `destructiveHint` |
| T001, X002 | info / warning | Heavy tool definitions; total token cost per turn |
| X001, X003, X004 | warning / error | Tools with overlapping descriptions; too many tools; no tools |
| F001–F003 | warning / error | (fuzz) Accepts schema-violating input; leaks stack traces or file paths; crashes or hangs |

Run `mcp-doctor rules` for the full list.

**Scoring:** each tool starts at 100 and loses 25 per error, 10 per warning and 3 per info. The server score is the average tool score minus server-level penalties (capped at 40). Grades: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F below.

## Fuzzing safety

`--fuzz` calls your tools with missing arguments, wrong types, out-of-enum values, 10,000-character strings and tricky Unicode, then checks for clean `isError` responses.

- By default it **only calls tools annotated `readOnlyHint: true`** (and not `destructiveHint: true`). Everything else is skipped and listed in the report.
- `--allow-unsafe` fuzzes every tool. **Only use it against a test instance**, never production data.
- A stdio server's own stderr is hidden to keep the report readable; add `--server-logs` to see it.

## Use in CI

```yaml
# .github/workflows/mcp-doctor.yml
- run: pip install "mcp-doctor @ git+https://github.com/builditwithgk/mcp-doctor"
- run: mcp-doctor check "python server.py" --fuzz -f markdown -o mcp-doctor.md --fail-under 80
```

## Hosted demo

`web/` is a small Flask app: paste a `tools/list` JSON and get the report card in the browser. It runs only the static checks. It never connects to servers, calls tools or contacts an LLM, and it needs nothing but Flask, so it runs on ordinary shared hosting.

```bash
pip install flask
python web/app.py     # http://localhost:5000
```

On cPanel shared hosting, create a Python app with `web/` as the application root and `passenger_wsgi.py` as the startup file, then install `web/requirements.txt`. The app imports the package straight from `src/`, so upload the `src/` and `examples/` folders alongside it.

## Limitations

- Token counts are **estimates**. Each provider wraps tool definitions in its own format; use the numbers to compare tools and track changes, not as a bill.
- Description checks are heuristics. A D005 ("no usage guidance") is a nudge, not a hard rule.
- Leak detection (F002) looks for stack traces only. File paths in error messages are not flagged, because file and git tools legitimately name paths.
- Fuzzing can't prove a tool is correct; it shows how it fails on bad input.
- v1 checks tools only, not resources or prompts.

## Roadmap

- Tool-selection eval (bring your own API key): generate realistic tasks per tool and measure how often a model picks the right one.
- README badge (`MCP Doctor: A`).
- Resource and prompt checks.

## Development

```bash
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT. Built by [Scaleup Solutions](https://scaleup-solutions.in/): we help teams ship production AI, from agents and MCP servers to RAG and LLM guardrails.
