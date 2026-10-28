"""Sub-agents as tools prototype (Nate Herk N2).

A sub-agent may call only the tools on its allowed list, and only up to
its step limit. A tool marked outward (send, publish, call) is never
executed by a sub-agent: it is recorded as proposed, the run stops with
status "needs_approval", and a human decision is required before anything
goes out. Every attempted call is logged, including blocked ones.
Stdlib only. Synthetic tools only. No network, no sending.
"""

from __future__ import annotations


class SubAgentError(Exception):
    """Raised for an unknown agent, before any tool runs."""


class SubAgentRunner:
    def __init__(self, agents: dict, tools: dict, outward_tools: set | None = None) -> None:
        self.agents = agents
        self.tools = tools
        self.outward_tools = set(outward_tools or set())

    def run(self, agent_name: str, plan: list[tuple[str, list]]) -> dict:
        """Run a scripted plan for one agent.

        The plan is a list of (tool_name, args) pairs supplied by the
        caller. This prototype has no language model: it proves the
        permission, limit, and approval rules, not any agent reasoning.
        """
        if agent_name not in self.agents:
            raise SubAgentError(f"unknown agent: {agent_name}")
        agent = self.agents[agent_name]
        allowed = set(agent.get("allowed_tools", []))
        max_steps = agent.get("max_steps", 0)
        log: list[dict] = []
        results: list = []
        for index, (tool_name, args) in enumerate(plan):
            if index >= max_steps:
                log.append(
                    {"agent": agent_name, "tool": tool_name,
                     "outcome": "blocked_step_limit", "step": index}
                )
                return {"status": "blocked", "log": log, "results": results}
            if tool_name not in allowed:
                log.append(
                    {"agent": agent_name, "tool": tool_name,
                     "outcome": "blocked_disallowed_tool", "step": index}
                )
                return {"status": "blocked", "log": log, "results": results}
            if tool_name not in self.tools:
                log.append(
                    {"agent": agent_name, "tool": tool_name,
                     "outcome": "blocked_unknown_tool", "step": index}
                )
                return {"status": "blocked", "log": log, "results": results}
            if tool_name in self.outward_tools:
                log.append(
                    {"agent": agent_name, "tool": tool_name,
                     "outcome": "proposed_not_executed", "step": index}
                )
                return {"status": "needs_approval", "log": log, "results": results}
            results.append(self.tools[tool_name](*args))
            log.append(
                {"agent": agent_name, "tool": tool_name, "outcome": "executed", "step": index}
            )
        return {"status": "completed", "log": log, "results": results}
