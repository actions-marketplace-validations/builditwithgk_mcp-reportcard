import json
import sys
from pathlib import Path

from typer.testing import CliRunner

from mcp_doctor.cli import app

ROOT = Path(__file__).resolve().parents[1]
BAD = str(ROOT / "examples" / "bad_tools.json")
GOOD = str(ROOT / "examples" / "good_tools.json")
runner = CliRunner()


def test_check_json_output():
    result = runner.invoke(app, ["check", BAD, "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["grade"] in "ABCDF" and len(data["tools"]) == 7


def test_fail_under_gate():
    assert runner.invoke(app, ["check", BAD, "--fail-under", "90", "-f", "json"]).exit_code == 1
    assert runner.invoke(app, ["check", GOOD, "--fail-under", "90", "-f", "json"]).exit_code == 0


def test_markdown_to_file(tmp_path):
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["check", BAD, "-f", "markdown", "-o", str(out)])
    assert result.exit_code == 0
    assert "MCP Doctor report" in out.read_text(encoding="utf-8")


def test_bad_input_exit_code(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{nope", encoding="utf-8")
    assert runner.invoke(app, ["check", str(broken)]).exit_code == 2


def test_rules_command():
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0 and "F002" in result.stdout


def test_web_demo():
    sys.path.insert(0, str(ROOT / "web"))
    from app import app as flask_app

    client = flask_app.test_client()
    assert client.get("/?sample=good").status_code == 200
    page = client.post("/", data={"tools": Path(GOOD).read_text(encoding="utf-8")})
    assert page.status_code == 200 and b'class="grade g-A"' in page.data
    page = client.post("/", data={"tools": "[1]"})
    assert b"is not a JSON object" in page.data
