"""Genesis core: the layer that ties memory + engine together.

For now it owns config resolution and the unified `genesis` CLI (status, doctor).
Next it gains the agentic turn-loop that is both the agent and its own
installer. Depends on genesis-memory and genesis-backend; nothing below depends
back up.
"""

__version__ = "0.0.1"

from . import config

__all__ = ["config", "__version__"]
