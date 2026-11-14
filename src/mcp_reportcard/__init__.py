"""mcp-reportcard: a health check for MCP servers.

The core (loading, lint rules, token estimates, scoring, Markdown/JSON reports) uses only the
standard library, so it can run anywhere, including the hosted demo. Live connections and
fuzzing (``connect``, ``fuzz``) need the ``mcp`` SDK and are imported lazily.
"""

from mcp_reportcard.analyze import analyze
from mcp_reportcard.loader import load_tools
from mcp_reportcard.models import Issue, Report, Severity

__all__ = ["Issue", "Report", "Severity", "analyze", "load_tools"]
__version__ = "0.1.0"
