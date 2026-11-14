"""MCP Doctor: a health check for MCP servers.

The core (loading, lint rules, token estimates, scoring, Markdown/JSON reports) uses only the
standard library, so it can run anywhere, including the hosted demo. Live connections and
fuzzing (``connect``, ``fuzz``) need the ``mcp`` SDK and are imported lazily.
"""

from mcp_doctor.analyze import analyze
from mcp_doctor.loader import load_tools
from mcp_doctor.models import Issue, Report, Severity

__all__ = ["Issue", "Report", "Severity", "analyze", "load_tools"]
__version__ = "0.1.0"
