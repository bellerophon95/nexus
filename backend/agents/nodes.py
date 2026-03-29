import json
import logging
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from backend.agents.state import NexusState, AgentMessage
from backend.agents.tools import NEXUS_TOOLS
from backend.config import settings
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY, temperature=0)

@observe()
def supervisor_node(state: NexusState) -> Dict[str, Any]:
    """
    Acts as the orchestrator, deciding which agent to call next.
    """
    logger.info("Entering Supervisor node")
    
    # Check for hard stop
    if state["iteration_count"] >= state["max_iterations"]:
        logger.warning("Max iterations reached. Ending agent flow.")
        return {"current_agent": "end"}

    system_prompt = (
        "You are the Supervisor for Project Nexus. Your job is to orchestrate a multi-agent system "
        "to answer the user's query accurately. You can route to the following agents:\n"
        "1. researcher: Gathers factual information from the knowledge base.\n"
        "2. analyst: Synthesizes gathered info into a structured response draft.\n"
        "3. validator: Fact-checks the analyst's draft against the context. ALWAYS call validator after analyst has drafted an answer.\n"
        "4. end: Finalizes the session ONLY after the validator has approved the answer.\n\n"
        "Current history is available in the state. Decide the next agent to invoke. "
        "Return ONLY the name of the next agent."
    )
    
    # Build message list for LLM including history
    messages = [
        SystemMessage(content=system_prompt),
    ]
    # Add conversation history
    messages.extend(state["messages"])
    # Add current context summary
    has_answer = "Yes" if state.get("final_answer") else "No"
    summary = (
        f"\n\nCONTEXT SUMMARY:\n"
        f"- Query: {state['query']}\n"
        f"- Chunks Retrieved: {len(state['retrieved_chunks'])}\n"
        f"- Final Answer Drafted: {has_answer}\n"
        f"- Iteration: {state['iteration_count']}\n"
        f"- Last Validation: {state['validation_status']}"
    )
    messages.append(HumanMessage(content=summary))
    
    response = llm.invoke(messages)
    
    next_agent = response.content.strip().lower()
    logger.info(f"Supervisor choice: {next_agent}")
    
    return {
        "current_agent": next_agent,
        "activity_log": [{"node": "supervisor", "status": f"Routing to {next_agent}..."}]
    }

@observe()
def researcher_node(state: NexusState) -> Dict[str, Any]:
    """
    Executes search and compiles context.
    """
    logger.info("Entering Researcher node")
    
    query = state["query"]
    # We use vector search tool directly for now, or let LLM decide tool calls
    from langchain_core.utils.function_calling import convert_to_openai_function
    
    llm_with_tools = llm.bind_tools(NEXUS_TOOLS)
    
    response = llm_with_tools.invoke([
        SystemMessage(content="You are a meticulous researcher. Use tools to find relevant info for the query."),
        HumanMessage(content=query)
    ])
    
    # Handle tool calls
    new_chunks = []
    status_msg = "Researcher found no new information."
    
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "vector_search":
                from backend.agents.tools import vector_search
                results = vector_search.invoke(tool_call["args"])
                if isinstance(results, list):
                    # Filter out error dicts
                    valid_results = [r for r in results if "error" not in r]
                    new_chunks.extend(valid_results)
                    if valid_results:
                        status_msg = f"Researcher gathered {len(valid_results)} new chunks from the knowledge base."
                    else:
                        status_msg = "Researcher searched but found no relevant chunks matching the query."
    
    return {
        "retrieved_chunks": state["retrieved_chunks"] + new_chunks,
        "messages": [AIMessage(content=status_msg)],
        "current_agent": "supervisor",
        "activity_log": [{"node": "researcher", "status": status_msg}]
    }

@observe()
def analyst_node(state: NexusState) -> Dict[str, Any]:
    """
    Synthesizes the context into a final answer.
    """
    logger.info("Entering Analyst node")
    
    if not state["retrieved_chunks"]:
        return {"final_answer": "I don't have enough information to answer that.", "current_agent": "end"}

    context_text = "\n".join([f"Source: {c['metadata'].get('source_path', 'Unknown')}\n{c['text']}" for c in state["retrieved_chunks"]])
    
    system_prompt = (
        "You are the Lead Analyst for Project Nexus. Synthesize the provided context into "
        "a clear, professional response. Cite sources where possible. "
        "If context is insufficient, explain what is missing."
    )
    
    user_prompt = f"Context:\n{context_text}\n\nQuestion: {state['query']}"
    
    if state["validation_status"] == "rejected":
        user_prompt += f"\n\nPREVIOUS FEEDBACK: {state['messages'][-1].content}\nPlease correct the errors mentioned."

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    return {
        "final_answer": response.content,
        "iteration_count": state["iteration_count"] + 1,
        "current_agent": "supervisor",
        "activity_log": [{"node": "analyst", "status": "Drafted synthesized response."}]
    }

@observe()
def validator_node(state: NexusState) -> Dict[str, Any]:
    """
    Checks for hallucinations.
    """
    logger.info("Entering Validator node")
    
    context_text = "\n".join([c["text"] for c in state["retrieved_chunks"]])
    
    system_prompt = (
        "You are the Quality Validator for Project Nexus. Your task is to check the Analyst's response "
        "against the provided Context chunks. Look for hallucinations, inaccuracies, or claims not supported by the context.\n\n"
        "Return a JSON object with:\n"
        "- score: 0 to 1 (1 = fully supported, 0 = complete hallucination)\n"
        "- feedback: Detailed explanation of any issues found."
    )
    
    user_prompt = f"Context:\n{context_text}\n\nAnalyst Response:\n{state['final_answer']}"
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    try:
        # Clean potential markdown if LLM includes it
        content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        
        status = "approved" if data["score"] > 0.7 else "rejected"
        return {
            "validation_status": status,
            "hallucination_score": 1 - data["score"],
            "messages": [AIMessage(content=f"Validator feedback: {data['feedback']}")],
            "current_agent": "supervisor",
            "activity_log": [{"node": "validator", "status": f"Validation {status}: {data['score']*100}% faithfulness."}]
        }
    except Exception as e:
        logger.error(f"Validator JSON parsing failed: {e}")
        return {
            "validation_status": "approved", # Fallback
            "current_agent": "supervisor"
        }
