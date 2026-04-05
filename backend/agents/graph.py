import logging

from langgraph.graph import END, StateGraph

from backend.agents.nodes import analyst_node, researcher_node, supervisor_node, validator_node
from backend.agents.state import NexusState

logger = logging.getLogger(__name__)


def build_nexus_graph():
    """
    Compiles the Project Nexus multi-agent graph with specialized nodes and state management.
    """
    workflow = StateGraph(NexusState)

    # 1. Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("validator", validator_node)

    # 2. Routing Logic
    def route_supervisor(state: NexusState):
        agent = state.get("current_agent", "end")
        if agent in ["researcher", "analyst", "validator"]:
            return agent
        return "end"

    def route_validator(state: NexusState):
        agent = state.get("current_agent", "end")
        if agent == "end":
            return END
        return "supervisor"

    # 3. Add Edges
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {"researcher": "researcher", "analyst": "analyst", "validator": "validator", "end": END},
    )

    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("analyst", "validator")  # Direct hand-off for speed

    workflow.add_conditional_edges(
        "validator", route_validator, {"supervisor": "supervisor", END: END}
    )

    # 4. Set Entry Point
    workflow.set_entry_point("supervisor")

    # 5. Compile
    return workflow.compile()


# Global graph instance for API to use
nexus_graph = build_nexus_graph()
