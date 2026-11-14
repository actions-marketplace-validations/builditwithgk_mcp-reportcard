"""Hosted mcp-reportcard demo: paste a tools/list JSON, get a report card.

Runs the same lint, token and scoring code as the CLI. It never connects to servers, calls
tools or contacts an LLM, so it is cheap and safe to host on shared hosting. Needs only Flask.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from flask import Flask, render_template, request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))  # use the package source without installing it

from mcp_reportcard.analyze import analyze  # noqa: E402
from mcp_reportcard.loader import LoadError, load_tools_text  # noqa: E402
from mcp_reportcard.report import sorted_issues  # noqa: E402

MAX_BYTES = 512 * 1024
MAX_TOOLS = 500
SAMPLES = {
    "bad": (ROOT.parent / "examples" / "bad_tools.json"),
    "good": (ROOT.parent / "examples" / "good_tools.json"),
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


def _sample(name: str) -> str:
    path = SAMPLES.get(name)
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


@app.route("/", methods=["GET", "POST"])
def index():  # noqa: ANN201
    text, report, error = "", None, None
    if request.method == "POST":
        text = request.form.get("tools", "")
        try:
            tools = load_tools_text(text)
            if len(tools) > MAX_TOOLS:
                raise LoadError(f"Too many tools ({len(tools)}); the demo checks up to {MAX_TOOLS}.")
            report = analyze(tools, server="pasted tools")
        except LoadError as e:
            error = str(e)
    else:
        text = _sample(request.args.get("sample", ""))
    return render_template(
        "index.html", text=text, report=report, error=error,
        sorted_issues=sorted_issues, Counter=Counter,
    )


@app.errorhandler(413)
def too_large(_e):  # noqa: ANN001, ANN201
    return render_template("index.html", text="", report=None, sorted_issues=sorted_issues,
                           Counter=Counter, error="Input is larger than 512 KB."), 413


if __name__ == "__main__":
    app.run(debug=False, port=5000)
