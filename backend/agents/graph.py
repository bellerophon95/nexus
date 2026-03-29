from typing import Dict, Any, List, Union
from langgraph.graph import StateGraph, END
from backend.agents.state import NexusState
from backend.agents.nodes import supervisor_node, researcher_node, analyst_node, validator_node
import logging

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

    # 2. Add Edges based on Supervisor choice
    def route_supervisor(state: NexusState):
        """
        Conditional logic for routing from the supervisor.
        """
        agent = state.get("current_agent", "end")
        
        if agent == "researcher":
            return "researcher"
        if agent == "analyst":
            return "analyst"
        if agent == "validator":
            return "validator"
        
        return "end"

    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "researcher": "researcher",
            "analyst": "analyst",
            "validator": "validator",
            "end": END
        }
    )

    # All nodes except validator loop back to supervisor to check next step
    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("analyst", "supervisor")
    workflow.add_edge("validator", "supervisor")

    # 3. Set Entry Point
    workflow.set_entry_point("supervisor")

    # 4. Compile
    return workflow.compile()

# Global graph instance for API to use
nexus_graph = build_nexus_graph()
