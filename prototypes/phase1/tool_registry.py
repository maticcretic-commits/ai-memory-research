"""Tool registry prototype (Nate Herk N3, MCP tool-server pattern).

Tools are registered with a schema, a permission (read, write, outward),
and a callable. invoke() validates arguments before calling anything,
audits every attempt including rejected ones, and never executes an
outward tool without the explicit approval value "approved". The front
end stays thin: list_tools() exposes schemas only, never functions.
Stdlib only. Synthetic tools only. No network, no sending without
explicit approval, and no approval is ever assumed.
"""

from __future__ import annotations

import copy

_TYPES = {"str": str, "dict": dict, "list": list, "int": int, "bool": bool}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}
        self._audit_log: list[dict] = []

    def register(self, name: str, schema: dict, permission: str, fn) -> None:
        self._tools[name] = {"schema": schema, "permission": permission, "fn": fn}

    def _record(self, name: str, outcome: str) -> None:
        self._audit_log.append({"seq": len(self._audit_log) + 1, "tool": name, "outcome": outcome})

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "schema": copy.deepcopy(t["schema"]), "permission": t["permission"]}
            for name, t in self._tools.items()
        ]

    def audit_log(self) -> list[dict]:
        return copy.deepcopy(self._audit_log)

    def invoke(self, name: str, args: dict, approval: str | None = None) -> dict:
        if name not in self._tools:
            self._record(name, "rejected")
            return {"outcome": "rejected", "reason": "unknown_tool"}
        tool = self._tools[name]
        schema = tool["schema"]
        for required in schema.get("required", []):
            if required not in args:
                self._record(name, "rejected")
                return {"outcome": "rejected", "reason": "missing_required_param"}
            expected = _TYPES.get(schema.get("params", {}).get(required))
            if expected is not None and not isinstance(args[required], expected):
                self._record(name, "rejected")
                return {"outcome": "rejected", "reason": "wrong_param_type"}
        if tool["permission"] == "outward" and approval != "approved":
            self._record(name, "needs_approval")
            return {"outcome": "needs_approval", "reason": "explicit_approval_required"}
        value = tool["fn"](**args)
        self._record(name, "executed")
        return {"outcome": "executed", "value": value}
