"""Genesis engine seam.

The whole of invariant 5 (engine-agnostic) lives behind one Protocol. Nothing
above this package imports a provider SDK or names a vendor. Swap the engine, the
agent is unchanged. For the beta the seam is a single-turn `complete`; the
tool-using `turn()` and heavy-lift `run()` from the design land with genesis-core.
"""

__version__ = "0.0.1"

from .seam import (
    Backend,
    BackendCaps,
    BackendError,
    Completion,
    Message,
    ToolCall,
    ToolSpec,
    TurnResult,
)
from .anthropic_backend import AnthropicBackend
from .openai_backend import OpenAIBackend
from .gemini_backend import GeminiBackend
from .claude_cli_backend import ClaudeCLIBackend

__all__ = [
    "Backend",
    "BackendCaps",
    "BackendError",
    "Completion",
    "Message",
    "ToolCall",
    "ToolSpec",
    "TurnResult",
    "AnthropicBackend",
    "OpenAIBackend",
    "GeminiBackend",
    "ClaudeCLIBackend",
    "__version__",
]
