"""Workflow graph prototype (Nate Herk N1).

A workflow is a list of steps with explicit dependencies. Steps run in
topological order. Arguments may reference an earlier step's output as
"$step_id". Validation happens before any step runs: duplicate ids,
missing dependencies, and cycles are rejected with no tool called.
A step error or an unknown tool stops the run fail-closed; the log up
to the failure is preserved and later steps do not run.
Stdlib only. Synthetic tools only. No network, no sending.
"""

from __future__ import annotations


class WorkflowError(Exception):
    """Raised when a workflow spec is invalid, before any step runs."""


class Workflow:
    def __init__(self, steps: list[dict]) -> None:
        self.steps = steps

    def _validate(self) -> None:
        ids = [s["id"] for s in self.steps]
        if len(ids) != len(set(ids)):
            raise WorkflowError("duplicate step id")
        known = set(ids)
        for step in self.steps:
            for dep in step.get("depends_on", []):
                if dep not in known:
                    raise WorkflowError(f"missing dependency: {dep}")
        # Cycle detection: Kahn's algorithm, without executing anything.
        remaining = {s["id"]: set(s.get("depends_on", [])) for s in self.steps}
        while remaining:
            ready = [sid for sid, deps in remaining.items() if not deps]
            if not ready:
                raise WorkflowError("cycle detected")
            for sid in ready:
                del remaining[sid]
            for deps in remaining.values():
                deps.difference_update(ready)

    def _order(self) -> list[dict]:
        by_id = {s["id"]: s for s in self.steps}
        ordered: list[dict] = []
        done: set[str] = set()
        while len(ordered) < len(self.steps):
            for step in self.steps:
                if step["id"] in done:
                    continue
                if all(dep in done for dep in step.get("depends_on", [])):
                    ordered.append(step)
                    done.add(step["id"])
        return ordered

    def run(self, tools: dict) -> dict:
        """Run the workflow against a dict of synthetic tool callables."""
        self._validate()
        outputs: dict = {}
        log: list[dict] = []
        for step in self._order():
            tool_name = step["tool"]
            if tool_name not in tools:
                log.append(
                    {"step": step["id"], "tool": tool_name, "outcome": "failed",
                     "error": f"unknown tool: {tool_name}"}
                )
                return {"status": "failed", "log": log, "outputs": outputs}
            args = [
                outputs[arg[1:]] if isinstance(arg, str) and arg.startswith("$") else arg
                for arg in step.get("args", [])
            ]
            try:
                outputs[step["id"]] = tools[tool_name](*args)
            except Exception as exc:  # noqa: BLE001 - log and stop, fail-closed
                log.append(
                    {"step": step["id"], "tool": tool_name, "outcome": "failed",
                     "error": str(exc)}
                )
                return {"status": "failed", "log": log, "outputs": outputs}
            log.append({"step": step["id"], "tool": tool_name, "outcome": "ok"})
        return {"status": "completed", "log": log, "outputs": outputs}
