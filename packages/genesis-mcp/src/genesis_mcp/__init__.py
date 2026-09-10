"""genesis-mcp: the companion's own vault, reachable over MCP."""

__version__ = "0.0.1"

from genesis_mcp.server import GenesisBridge, GenesisRootError, handle, serve  # noqa: F401
