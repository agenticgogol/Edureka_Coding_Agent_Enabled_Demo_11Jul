"""Minimal known-working LangGraph example with REAL checkpointing +
human-in-the-loop interrupt/resume — not a UI-only approve button.

Adapt this; verify `pip show langgraph` version matches API used here
(LangGraph's checkpointer API has changed across versions — if
`from langgraph.checkpoint.memory import MemorySaver` fails, check the
installed version's docs before guessing an alternative import path).
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt, Command


class AgentState(TypedDict):
    input: str
    proposed_action: str
    approved: bool
    result: str


def propose_action(state: AgentState) -> AgentState:
    # Replace with a real LLM call via llm_client.complete(...)
    return {**state, "proposed_action": f"do_something_with({state['input']})"}


def human_approval(state: AgentState) -> AgentState:
    # This actually pauses graph execution and persists state via the
    # checkpointer — resuming later (even in a new process) continues here.
    decision = interrupt({"proposed_action": state["proposed_action"]})
    return {**state, "approved": bool(decision.get("approved", False))}


def execute_action(state: AgentState) -> AgentState:
    if not state["approved"]:
        return {**state, "result": "rejected by human reviewer"}
    return {**state, "result": f"executed: {state['proposed_action']}"}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("propose", propose_action)
    graph.add_node("approve", human_approval)
    graph.add_node("execute", execute_action)
    graph.set_entry_point("propose")
    graph.add_edge("propose", "approve")
    graph.add_edge("approve", "execute")
    graph.add_edge("execute", END)

    checkpointer = MemorySaver()  # swap for a persistent checkpointer in production
    return graph.compile(checkpointer=checkpointer)


def run_agent(user_input: str, thread_id: str = "demo-thread") -> dict:
    """Entrypoint the backend calls. First run pauses at human_approval;
    call resume_agent(...) with the same thread_id to continue."""
    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke({"input": user_input, "proposed_action": "", "approved": False, "result": ""}, config)
    return result


def resume_agent(thread_id: str, approved: bool) -> dict:
    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke(Command(resume={"approved": approved}), config)
    return result


if __name__ == "__main__":
    out = run_agent("refund order #123")
    print("Paused for approval:", out)
    resumed = resume_agent("demo-thread", approved=True)
    print("Resumed result:", resumed)
