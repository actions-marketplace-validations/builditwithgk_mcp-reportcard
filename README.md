# mcp-reportcard

> **A health check for MCP servers.** Lint your tools, measure their token cost, fuzz their error handling — and get a graded report card with a concrete fix for every issue.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) [![PyPI](https://img.shields.io/pypi/v/mcp-reportcard)](https://pypi.org/project/mcp-reportcard/) ![MCP](https://img.shields.io/badge/MCP-any%20server%2C%20any%20language-brightgreen) [![GitHub Marketplace](https://img.shields.io/badge/Marketplace-mcp--reportcard-blue?logo=github)](https://github.com/marketplace/actions/mcp-reportcard) [![CI](https://github.com/builditwithgk/mcp-reportcard/actions/workflows/ci.yml/badge.svg)](https://github.com/builditwithgk/mcp-reportcard/actions/workflows/ci.yml) [![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Space-live%20demo-yellow)](https://huggingface.co/spaces/builditwithgk/mcp-reportcard)

When an agent picks the wrong tool, sends malformed arguments, or burns context on bloated definitions, the cause is usually in the server — and the model only ever sees what your `tools/list` says. `mcp-reportcard` checks exactly that, in seconds, for any MCP server in any language.

![mcp-reportcard grading a sloppy MCP server (D) and the same service written properly (A)](https://raw.githubusercontent.com/builditwithgk/mcp-reportcard/main/docs/demo.gif)

**Try it in the browser:** [huggingface.co/spaces/builditwithgk/mcp-reportcard](https://huggingface.co/spaces/builditwithgk/mcp-reportcard) — paste a `tools/list` JSON, get the report card.

## Why it's different

**It grades what the model sees, not what your code does.**

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is for poking at a server by hand. `mcp-reportcard` is automated and opinionated: it scores tool names, descriptions, schemas and safety annotations against the things that actually make models misbehave — vague descriptions, undocumented parameters, near-duplicate tools, missing `readOnlyHint`s, stack traces in error replies — and it runs in CI.

Every finding comes with a rule ID, a severity and a specific fix. No LLM is involved in the checks, so results are deterministic and safe to gate a merge on.

## Example output

Running against the deliberately sloppy server in [`examples/bad_server.py`](https://github.com/builditwithgk/mcp-reportcard/blob/main/examples/bad_server.py):

```text
┌──────── mcp-reportcard · acme-orders (bad example) ─────────┐
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

The same service written properly, [`examples/good_server.py`](https://github.com/builditwithgk/mcp-reportcard/blob/main/examples/good_server.py), scores **A (100)**.

**Field-tested:** run against six official MCP reference servers (Node and Python, stdio and HTTP) — 159 fuzz cases, zero crashes, and two over-eager rules fixed as a result. Numbers and details in [`FINDINGS.md`](https://github.com/builditwithgk/mcp-reportcard/blob/main/FINDINGS.md).

## Install & run

Requires Python 3.10+.

```bash
pip install "mcp-reportcard[tokens]"

# …or run it without installing (uv)
uvx --from "mcp-reportcard[tokens]" mcp-reportcard check "python server.py"

# …or from source
git clone https://github.com/builditwithgk/mcp-reportcard
cd mcp-reportcard
pip install -e ".[dev]"
```

The `[tokens]` extra adds tiktoken for more accurate token counts; without it (`pip install mcp-reportcard`), a characters/4 estimate is used.

## Command line

```bash
# A stdio server (any language): pass the command that starts it
mcp-reportcard check "python server.py"
mcp-reportcard check "npx -y @modelcontextprotocol/server-everything"

# A Streamable HTTP server
mcp-reportcard check http://localhost:8000/mcp

# A saved tools/list JSON (offline, no server needed)
mcp-reportcard check tools.json

# Also test error handling with bad inputs (read-only tools only — see below)
mcp-reportcard check "python server.py" --fuzz

# Reports for PRs and CI
mcp-reportcard check "python server.py" -f markdown -o report.md
mcp-reportcard check "python server.py" -f json --fail-under 80

# Save a server's tool list (for offline checks or the web demo)
mcp-reportcard dump "python server.py" -o tools.json

# List every check
mcp-reportcard rules
```

## GitHub Action

Grade your server on every pull request ([GitHub Marketplace listing](https://github.com/marketplace/actions/mcp-reportcard)). The action writes the report card to the job summary, keeps one sticky PR comment up to date, and fails the check when the score drops below your bar:

```yaml
# .github/workflows/mcp-reportcard.yml
on: pull_request
permissions:
  contents: read
  pull-requests: write   # for the PR comment
jobs:
  mcp-reportcard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5          # or setup-node, etc. — whatever your server needs
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt   # your server's own dependencies
      - uses: builditwithgk/mcp-reportcard@v1
        with:
          server: python server.py             # a command, an http(s) URL, or a saved tools/list JSON
          fuzz: "true"
          fail-under: "80"
```

| Input | Default | |
| --- | --- | --- |
| `server` | — | **Required.** Command that starts a stdio server, an http(s) URL, or a `tools/list` JSON file. |
| `fuzz` | `false` | Also call read-only tools with bad input. Needs a live server. |
| `fail-under` | — | Fail the step below this score (0-100). |
| `args` | — | Extra `mcp-reportcard check` arguments, e.g. `--timeout 20 --server-logs`. |
| `version` | this ref | Pin a PyPI version instead, e.g. `0.1.1`. |
| `comment` | `true` | Post/update the sticky PR comment. |

Outputs: `grade`, `score`, `report` (Markdown path) and `json` (JSON path). mcp-reportcard installs into its own virtualenv, so the Python your server runs on is left untouched.

### pre-commit

Run it before every commit with [pre-commit](https://pre-commit.com):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/builditwithgk/mcp-reportcard
    rev: v0.1.2
    hooks:
      - id: mcp-reportcard
        args: ["python server.py", "--fail-under", "80"]   # or a tools/list JSON file
        files: ^server\.py$                               # optional: only when these files change
```

Prefer the plain CLI? `pip install mcp-reportcard` and `mcp-reportcard check "python server.py" --fail-under 80` (exits 1 below the bar; `--json-out` writes JSON alongside a Markdown report).

This repo dogfoods both: CI runs the CLI and the action against [`examples/good_server.py`](https://github.com/builditwithgk/mcp-reportcard/blob/main/examples/good_server.py) with `--fail-under 90` on Linux, macOS and Windows.

## What it checks

| ID | Severity | Check |
| --- | --- | --- |
| N001–N005 | error / warning / info | Missing, duplicate, invalid or over-long names; mixed naming styles |
| D001–D005 | error / warning / info | Missing, too short, too long, or name-restating descriptions; no "when to use" guidance when a similar tool exists |
| S001–S008 | error / warning / info | Missing object schema, untyped or undocumented parameters, broken `required`, free-form objects, deep nesting, missing `enum`, too many parameters |
| A001–A002 | warning | Missing or contradictory `readOnlyHint` / `destructiveHint` |
| T001, X002 | info / warning | Heavy tool definitions; total token cost per turn |
| X001, X003, X004 | warning / error | Tools with overlapping descriptions; too many tools; no tools |
| F001–F003 | warning / error | (fuzz) Accepts schema-violating input; leaks stack traces; crashes or hangs |

**Scoring:** each tool starts at 100 and loses 25 per error, 10 per warning and 3 per info. The server score is the average tool score minus server-level penalties (capped at 40). Grades: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F below.

## Fuzzing safety

`--fuzz` calls your tools with missing arguments, wrong types, out-of-enum values, 10,000-character strings and tricky Unicode, then checks for clean `isError` responses.

- By default it **only calls tools annotated `readOnlyHint: true`** (and not `destructiveHint: true`). Everything else is skipped — and listed in the report, never silently.
- `--allow-unsafe` fuzzes every tool. **Only use it against a test instance**, never production data.
- A stdio server's own stderr is hidden to keep the report readable; add `--server-logs` to see it.

## Web demo

### Test your own server in the browser

The [browser demo](https://huggingface.co/spaces/builditwithgk/mcp-reportcard) can't launch your server, so save its tool list with the CLI and paste it in:

1. Save the tool list (use whatever command starts your server, or an `http(s)://…/mcp` URL):
   ```bash
   mcp-reportcard dump "python server.py" -o tools.json
   ```
2. Open `tools.json`, copy everything, and paste it into the text box on the [demo page](https://huggingface.co/spaces/builditwithgk/mcp-reportcard).
3. Click **Check tools**.

You get the same lint findings as the CLI. Two differences: token counts are a characters ÷ 4 estimate (the CLI with `[tokens]` uses tiktoken), and there's no fuzzing, because the browser never calls your server. To try it without a server of your own, click **Load a bad example** first.

### How the demo is built

The demo runs the static checks only — it never connects to servers, calls tools or contacts an LLM, and nothing pasted is stored. Because the core is pure standard-library Python, it ships two ways from the same code:

- **In the browser** — [`space/`](https://github.com/builditwithgk/mcp-reportcard/tree/main/space) is a static page that runs `src/mcp_reportcard` client-side with [Pyodide](https://pyodide.org). That's the [Hugging Face Space](https://huggingface.co/spaces/builditwithgk/mcp-reportcard): no server, free tier. `bash space/build.sh` assembles it into `space/_site/`; `bash space/deploy.sh` publishes it. The same folder works on GitHub Pages or any static host.
- **As a Flask app** — [`web/`](https://github.com/builditwithgk/mcp-reportcard/tree/main/web), for Python hosting such as cPanel: create a Python app with `web/` as the root and `passenger_wsgi.py` as the startup file, install `web/requirements.txt`, and upload `src/` and `examples/` alongside.

```bash
pip install flask
python web/app.py     # http://localhost:5000
```

## Limitations

- Token counts are **estimates**. Each provider wraps tool definitions in its own format; use the numbers to compare tools and track changes, not as a bill.
- Description checks are heuristics. A D005 ("no usage guidance") is a nudge, not a hard rule.
- Leak detection (F002) looks for stack traces only. File paths in error messages are not flagged — file and git tools legitimately name paths.
- Fuzzing can't prove a tool is correct; it shows how it fails on bad input.
- v1 checks tools only, not resources or prompts.

## Roadmap

- Tool-selection eval (bring your own API key): generate realistic tasks per tool and measure how often a model picks the right one.
- README badge (`mcp-reportcard: A`).
- Resource and prompt checks.

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Tests cover every lint rule, scoring, leak detection, fuzz-case generation, the CLI and the web demo — plus end-to-end runs against both example servers, in-process and as real stdio subprocesses.

## Author

Built by **Gopi K Aitham** ([builditwithgk](https://github.com/builditwithgk)) — see [scaleup-solutions.in](https://scaleup-solutions.in/). Available for freelance and contract work on AI, agent, and MCP tooling.

## License

MIT
