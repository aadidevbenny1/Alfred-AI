"""Alfred AI Package."""
from .persona import ALFRED_SYSTEM_PROMPT, get_varied_greeting, get_varied_acknowledgement
from .gemini_client import GeminiClient

__all__ = [
    "ALFRED_SYSTEM_PROMPT",
    "get_varied_greeting",
    "get_varied_acknowledgement",
    "GeminiClient",
]

