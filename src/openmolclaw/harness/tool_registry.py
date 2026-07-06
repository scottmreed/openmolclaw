"""Generic tool registry (OpenMolClaw harness).

Provider-neutral registry that maps tool names to Python handlers and their
provider-facing JSON schemas. The router asks the registry for the tool specs
to offer a model; the executor asks it to dispatch a chosen tool by name.

Standard-library only.

Maintained by the ChemIllusion team as part of the OpenMolClaw project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


def normalize_tool_name_for_registry(name: str) -> str:
    """Normalize a provider-emitted tool name to a bare registry key.

    Some providers return names like ``'functions.external_search'`` instead of
    ``'external_search'``. Registry keys use bare names.
    """
    n = (name or "").strip()
    if n.startswith("functions."):
        return n[len("functions.") :]
    return n


@dataclass
class RegisteredTool:
    """A tool handler plus the provider-facing schema that advertises it."""

    name: str
    handler: Callable[..., Any]
    schema: Dict[str, Any]


class ToolRegistry:
    """Registry of callable chemistry/workspace tools.

    Handlers are plain callables invoked with keyword arguments taken from the
    model's tool-call payload. Schemas are provider-neutral function-calling
    specs (``{"type": "function", "function": {...}}``).
    """

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        schema: Optional[Dict[str, Any]] = None,
        *,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a tool.

        Either pass a full provider ``schema`` or let the registry build one
        from ``description`` + JSON-schema ``parameters``.
        """
        key = normalize_tool_name_for_registry(name)
        if schema is None:
            schema = {
                "type": "function",
                "function": {
                    "name": key,
                    "description": description,
                    "parameters": parameters
                    or {"type": "object", "properties": {}},
                },
            }
        self._tools[key] = RegisteredTool(name=key, handler=handler, schema=schema)

    def has(self, name: str) -> bool:
        return normalize_tool_name_for_registry(name) in self._tools

    def get(self, name: str) -> RegisteredTool:
        key = normalize_tool_name_for_registry(name)
        if key not in self._tools:
            raise KeyError(f"unknown tool: {key!r}")
        return self._tools[key]

    def names(self) -> List[str]:
        return sorted(self._tools)

    def specs(self) -> List[Dict[str, Any]]:
        """Provider-facing tool schemas, in stable name order."""
        return [self._tools[n].schema for n in self.names()]


__all__ = [
    "normalize_tool_name_for_registry",
    "RegisteredTool",
    "ToolRegistry",
]
