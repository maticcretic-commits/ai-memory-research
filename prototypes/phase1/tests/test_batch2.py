"""Batch 2 tests. Run: python3 -m unittest discover -s tests -v

Written before the implementations. Synthetic tools and data only.
No network, no accounts, no sending, no real records. A passing suite
proves only that the prototypes behave as specified on these fixtures.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _synthetic_tools():
    calls = []

    def fetch_record(record_id):
        calls.append(("fetch_record", record_id))
        return {"id": record_id, "text": "synthetic record"}

    def summarise(record):
        calls.append(("summarise", record["id"]))
        return f"Summary of {record['id']}"

    def draft_reply(summary):
        calls.append(("draft_reply", summary))
        return {"draft": f"Draft about: {summary}", "sent": False}

    def send_message(draft):
        calls.append(("send_message", draft["draft"]))
        return {"sent": True}

    def failing_tool(_x):
        raise ValueError("synthetic failure")

    return calls, {
        "fetch_record": fetch_record,
        "summarise": summarise,
        "draft_reply": draft_reply,
        "send_message": send_message,
        "failing_tool": failing_tool,
    }


class TestWorkflowGraph(unittest.TestCase):
    def test_linear_workflow_runs_in_order(self):
        import workflow_graph

        calls, tools = _synthetic_tools()
        wf = workflow_graph.Workflow(
            steps=[
                {"id": "fetch", "tool": "fetch_record", "args": ["SYN-1"], "depends_on": []},
                {"id": "summarise", "tool": "summarise", "args": ["$fetch"], "depends_on": ["fetch"]},
                {"id": "draft", "tool": "draft_reply", "args": ["$summarise"], "depends_on": ["summarise"]},
            ]
        )
        result = wf.run(tools)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([c[0] for c in calls], ["fetch_record", "summarise", "draft_reply"])
        self.assertFalse(result["outputs"]["draft"]["sent"])

    def test_cycle_is_rejected_before_running(self):
        import workflow_graph

        calls, tools = _synthetic_tools()
        wf = workflow_graph.Workflow(
            steps=[
                {"id": "a", "tool": "fetch_record", "args": ["SYN-1"], "depends_on": ["b"]},
                {"id": "b", "tool": "summarise", "args": ["$a"], "depends_on": ["a"]},
            ]
        )
        with self.assertRaises(workflow_graph.WorkflowError):
            wf.run(tools)
        self.assertEqual(calls, [])

    def test_unknown_tool_fails_closed_with_log(self):
        import workflow_graph

        calls, tools = _synthetic_tools()
        wf = workflow_graph.Workflow(
            steps=[{"id": "x", "tool": "no_such_tool", "args": [], "depends_on": []}]
        )
        result = wf.run(tools)
        self.assertEqual(result["status"], "failed")
        self.assertIn("no_such_tool", result["log"][0]["error"])
        self.assertEqual(calls, [])

    def test_step_error_stops_and_preserves_log(self):
        import workflow_graph

        calls, tools = _synthetic_tools()
        wf = workflow_graph.Workflow(
            steps=[
                {"id": "fetch", "tool": "fetch_record", "args": ["SYN-1"], "depends_on": []},
                {"id": "boom", "tool": "failing_tool", "args": ["$fetch"], "depends_on": ["fetch"]},
                {"id": "draft", "tool": "draft_reply", "args": ["$boom"], "depends_on": ["boom"]},
            ]
        )
        result = wf.run(tools)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["log"]), 2)
        self.assertEqual([c[0] for c in calls], ["fetch_record"])
        self.assertNotIn("draft", result["outputs"])

    def test_missing_dependency_is_rejected(self):
        import workflow_graph

        calls, tools = _synthetic_tools()
        wf = workflow_graph.Workflow(
            steps=[{"id": "x", "tool": "fetch_record", "args": ["SYN-1"], "depends_on": ["ghost"]}]
        )
        with self.assertRaises(workflow_graph.WorkflowError):
            wf.run(tools)


class TestSubAgents(unittest.TestCase):
    def test_allowed_tool_executes_and_is_logged(self):
        import subagents

        calls, tools = _synthetic_tools()
        runner = subagents.SubAgentRunner(
            agents={"researcher": {"allowed_tools": ["fetch_record", "summarise"], "max_steps": 5}},
            tools={"fetch_record": tools["fetch_record"], "summarise": tools["summarise"]},
        )
        result = runner.run("researcher", [("fetch_record", ["SYN-9"])])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["log"][0]["agent"], "researcher")
        self.assertEqual(result["log"][0]["tool"], "fetch_record")

    def test_disallowed_tool_is_blocked_and_logged(self):
        import subagents

        calls, tools = _synthetic_tools()
        runner = subagents.SubAgentRunner(
            agents={"researcher": {"allowed_tools": ["fetch_record"], "max_steps": 5}},
            tools={"fetch_record": tools["fetch_record"], "summarise": tools["summarise"]},
        )
        result = runner.run("researcher", [("summarise", [{"id": "SYN-9"}])])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(calls, [])
        self.assertEqual(result["log"][0]["outcome"], "blocked_disallowed_tool")

    def test_step_limit_is_enforced(self):
        import subagents

        calls, tools = _synthetic_tools()
        runner = subagents.SubAgentRunner(
            agents={"worker": {"allowed_tools": ["fetch_record"], "max_steps": 2}},
            tools={"fetch_record": tools["fetch_record"]},
        )
        result = runner.run(
            "worker",
            [("fetch_record", ["SYN-1"]), ("fetch_record", ["SYN-2"]), ("fetch_record", ["SYN-3"])],
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(calls), 2)

    def test_outward_tool_is_proposed_never_executed(self):
        import subagents

        calls, tools = _synthetic_tools()
        runner = subagents.SubAgentRunner(
            agents={"sender": {"allowed_tools": ["draft_reply", "send_message"], "max_steps": 5}},
            tools={"draft_reply": tools["draft_reply"], "send_message": tools["send_message"]},
            outward_tools={"send_message"},
        )
        result = runner.run(
            "sender",
            [("draft_reply", ["synthetic summary"]), ("send_message", [{"draft": "x", "sent": False}])],
        )
        self.assertEqual(result["status"], "needs_approval")
        self.assertEqual([c[0] for c in calls], ["draft_reply"])
        self.assertEqual(result["log"][-1]["outcome"], "proposed_not_executed")

    def test_unknown_agent_is_rejected(self):
        import subagents

        _calls, tools = _synthetic_tools()
        runner = subagents.SubAgentRunner(agents={}, tools=tools)
        with self.assertRaises(subagents.SubAgentError):
            runner.run("ghost", [])


class TestToolRegistry(unittest.TestCase):
    def _registry(self):
        import tool_registry

        calls, tools = _synthetic_tools()
        reg = tool_registry.ToolRegistry()
        reg.register(
            "fetch_record",
            {"params": {"record_id": "str"}, "required": ["record_id"]},
            "read",
            tools["fetch_record"],
        )
        reg.register(
            "send_message",
            {"params": {"draft": "dict"}, "required": ["draft"]},
            "outward",
            tools["send_message"],
        )
        return calls, reg

    def test_read_tool_invokes_and_audits(self):
        _calls, reg = self._registry()
        result = reg.invoke("fetch_record", {"record_id": "SYN-1"})
        self.assertEqual(result["outcome"], "executed")
        self.assertEqual(result["value"]["id"], "SYN-1")
        self.assertEqual(len(reg.audit_log()), 1)

    def test_missing_required_param_rejected_without_call(self):
        calls, reg = self._registry()
        result = reg.invoke("fetch_record", {})
        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(calls, [])

    def test_unknown_tool_rejected_and_audited(self):
        calls, reg = self._registry()
        result = reg.invoke("no_such_tool", {})
        self.assertEqual(result["outcome"], "rejected")
        self.assertEqual(calls, [])
        self.assertEqual(reg.audit_log()[-1]["outcome"], "rejected")

    def test_outward_tool_needs_approval_and_does_not_execute(self):
        calls, reg = self._registry()
        result = reg.invoke("send_message", {"draft": {"draft": "x", "sent": False}})
        self.assertEqual(result["outcome"], "needs_approval")
        self.assertEqual(calls, [])

    def test_outward_tool_executes_only_with_explicit_approval(self):
        calls, reg = self._registry()
        result = reg.invoke(
            "send_message", {"draft": {"draft": "x", "sent": False}}, approval="approved"
        )
        self.assertEqual(result["outcome"], "executed")
        self.assertTrue(result["value"]["sent"])
        self.assertEqual(len(calls), 1)

    def test_list_tools_hides_functions(self):
        _calls, reg = self._registry()
        listed = reg.list_tools()
        self.assertEqual({t["name"] for t in listed}, {"fetch_record", "send_message"})
        for tool in listed:
            self.assertNotIn("fn", tool)


if __name__ == "__main__":
    unittest.main()
