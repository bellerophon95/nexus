import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agents.state import NexusState
from backend.agents.tools import NEXUS_TOOLS
from backend.config import settings
from backend.observability.tracing import observe
from backend.retrieval.self_rag import check_hallucination

logger = logging.getLogger(__name__)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY, temperature=0)


@observe()
async def supervisor_node(state: NexusState) -> dict[str, Any]:
    """
    Acts as the orchestrator, deciding which agent to call next.
    """
    # 1. Termination: If we already have an approved answer, end the flow.
    if state.get("final_answer") and state.get("validation_status") == "approved":
        logger.info("Approved final answer present. Terminating graph.")
        return {"current_agent": "end"}

    # 2. Catch simple greetings/out-of-scope early to avoid search loops
    query = state.get("query", "").strip().lower()
    # Greetings must be a very specific set of short, isolated words
    # We removed 'what is this' and 'who are you' as they can be part of research queries.
    simple_greetings = {"hi", "hello", "howdy", "hey", "howdie"}

    if (
        query in simple_greetings
        and not state["retrieved_chunks"]
        and state["iteration_count"] == 0
    ):
        logger.info(f"Detected simple greeting: '{query}'. Routing to analyst.")
        return {"current_agent": "analyst", "is_greeting": True}

    # 3. Check for hard stop (Max iterations or no progress after multiple searches)
    if state["iteration_count"] >= state["max_iterations"] or state.get("search_count", 0) >= 2:
        logger.warning("Max iterations or excessive search attempts reached. Ending agent flow.")
        return {
            "current_agent": "end",
            "activity_log": [
                {
                    "node": "supervisor",
                    "status": "Terminating",
                    "rationale": "Max iterations or search attempts reached to avoid infinite loops.",
                }
            ],
        }

    system_prompt = (
        "You are the Supervisor for Project Nexus. Your job is to orchestrate a multi-agent system "
        "to answer the user's query accurately. You can route to the following agents:\n"
        "1. researcher: Gathers factual information from the knowledge base.\n"
        "2. analyst: Synthesizes gathered info into a structured response draft.\n"
        "3. validator: Fact-checks the analyst's draft against the context. ALWAYS call validator after analyst has drafted an answer.\n"
        "4. end: Finalizes the session ONLY after the validator has approved the answer.\n\n"
        "Current history is available in the state. Decide the next agent to invoke. "
        "Return ONLY the name of the next agent. If no more research is possible or needed, call 'analyst' or 'end'."
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
        f"- Search Count: {state.get('search_count', 0)}\n"
        f"- Last Validation: {state['validation_status']}"
    )
    messages.append(HumanMessage(content=summary))

    response = llm.invoke(messages)

    next_agent = response.content.strip().lower()
    logger.info(f"Supervisor choice: {next_agent}")

    return {
        "current_agent": next_agent,
        "activity_log": [
            {
                "node": "supervisor",
                "status": f"Routing to {next_agent}...",
                "rationale": f"Based on context, the {next_agent} is best suited for the next step.",
            }
        ],
    }


@observe()
async def researcher_node(state: NexusState) -> dict[str, Any]:
    """
    Executes search and compiles context.
    """
    logger.info("Entering Researcher node")

    query = state["query"]
    llm_with_tools = llm.bind_tools(NEXUS_TOOLS)

    response = llm_with_tools.invoke(
        [
            SystemMessage(
                content="You are a meticulous researcher. Use tools to find relevant info for the query."
            ),
            HumanMessage(content=query),
        ]
    )

    # Handle tool calls
    new_chunks = []
    status_msg = "Researcher found no new information."
    rationale = (
        "The model did not find specific document search tool calls necessary for this query."
    )
    search_triggered = 0

    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "vector_search":
                from backend.agents.tools import vector_search

                search_triggered = 1
                # Inject user_id and Tune Engine settings from state into the tool call arguments
                args = dict(tool_call["args"])
                args["user_id"] = state.get("user_id")
                # Force state usage, default to 0.4 if missing (never 0.2)
                args["match_threshold"] = state.get("match_threshold", 0.4)
                args["rerank"] = state.get("rerank", True)
                logger.info(
                    f"Researcher invoking vector_search with threshold: {args['match_threshold']}"
                )
                search_data = vector_search.invoke(args)

                if isinstance(search_data, dict):
                    valid_results = search_data.get("results", [])
                    meta = search_data.get("meta", {})
                    new_chunks.extend(valid_results)

                    if valid_results:
                        # Construct a dynamic, transparent status message
                        techniques = []
                        if meta.get("hybrid_boost"):
                            techniques.append("Hybrid-Boosted Sparse Search")
                        if meta.get("reranked"):
                            techniques.append("Cohere Reranking")
                        tech_str = " via " + " & ".join(techniques) if techniques else ""

                        status_msg = (
                            f"Researcher gathered {len(valid_results)} optimized chunks{tech_str}."
                        )
                        rationale = f"Advanced retrieval engaged for '{args.get('query')}'. "
                        if meta.get("hybrid_boost"):
                            rationale += "Exact token matching (Sparse) prioritized rare keywords. "
                        if meta.get("reranked"):
                            rationale += "Cross-encoder reranking finalized relevance sorting."
                    else:
                        # Diagnostic Check: Does the user even have documents?
                        from backend.database.supabase import get_supabase

                        try:
                            # 1. Check if the user has ANY documents linked to THIS ID
                            doc_check = (
                                get_supabase()
                                .table("documents")
                                .select("id")
                                .or_(f"user_id.eq.{state.get('user_id')},is_personal.eq.false")
                                .limit(1)
                                .execute()
                            )
                            if doc_check.data:
                                status_msg = "Found your document library, but the specific query did not yield high-relevance matches."
                                rationale = "Documents exist for this session, but the retrieval threshold filtered them out. Try a more general question."
                            else:
                                # 2. Check if a document with a similar name exists under ANY ID (Session Mismatch Detection)
                                # We use a broad check to help the user identify Incognito/Session issues.
                                query_terms = state["query"].split()
                                possible_matches = []
                                for term in query_terms:
                                    if len(term) > 3:
                                        m = (
                                            get_supabase()
                                            .table("documents")
                                            .select("filename")
                                            .ilike("filename", f"%{term}%")
                                            .limit(1)
                                            .execute()
                                        )
                                        if m.data:
                                            possible_matches.append(m.data[0]["filename"])

                                if possible_matches:
                                    status_msg = f"Security Alert: Document '{possible_matches[0]}' exists but belongs to a different session ID."
                                    rationale = "The document was found in the global database but you are not the owner in this Incognito tab. Please re-upload it."
                                else:
                                    status_msg = "No documents found linked to this session ID."
                                    rationale = f"Researcher confirmed that user_id '{state.get('user_id')}' has no uploaded documents."
                        except Exception as de:
                            logger.error(f"Diagnostic check failed: {de}")
                            status_msg = "Researcher searched but found no relevant chunks matching the query."
                            rationale = "The knowledge base did not contain direct matches."

    return {
        "retrieved_chunks": state["retrieved_chunks"] + new_chunks,
        "search_count": state.get("search_count", 0) + search_triggered,
        "messages": [AIMessage(content=status_msg)],
        "current_agent": "supervisor",
        "activity_log": [{"node": "researcher", "status": status_msg, "rationale": rationale}],
    }


@observe()
async def analyst_node(state: NexusState) -> dict[str, Any]:
    """
    Synthesizes the context into a final answer.
    """
    logger.info("Entering Analyst node")

    # Handle greetings or empty context
    if state.get("is_greeting"):
        return {
            "final_answer": "Hello! I am Nexus AI. I'm ready to help you research and analyze your documents. What would you like to know?",
            "current_agent": "supervisor",  # Route to supervisor to finalize via validator or end
            "activity_log": [
                {
                    "node": "analyst",
                    "status": "Handling greeting",
                    "rationale": "User input identified as a general greeting rather than a research query.",
                }
            ],
        }

    if not state["retrieved_chunks"]:
        return {
            "final_answer": "I'm sorry, I couldn't find any information locally related to your request. Please try broadening your search or check if the relevant documents have been uploaded.",
            "current_agent": "supervisor",
            "activity_log": [
                {
                    "node": "analyst",
                    "status": "Insufficient context",
                    "rationale": "No relevant document chunks were found after multiple research attempts.",
                }
            ],
        }

    # Sort retrieved chunks by score to ensure top (possibly boosted) hits are first in context
    sorted_chunks = sorted(state["retrieved_chunks"], key=lambda x: x.get("score", 0), reverse=True)

    context_text = "\n".join(
        [
            f"Source: {c['metadata'].get('source_path', 'Unknown')} (Relevance: {c.get('score', 0):.2f})\n{c['text']}"
            for c in sorted_chunks
        ]
    )

    system_prompt = (
        "You are the Lead Analyst for Project Nexus. Synthesize the provided context into "
        "a professional response. "
        "STRICT RULE: You MUST ONLY use the provided Context to answer. Do NOT use outside knowledge. "
        "If the information requested is not present in the context, clearly state that "
        "it is not in the documents.\n\n"
        "NOTE: Context segments are sorted by retrieval relevance score. Prioritize higher-scoring segments as they have "
        "been validated by the Hybrid Search engine. Important entities (like organization names, 'mymailkeeper', etc.) "
        "may be found within email addresses or system IDs—extract them carefully.\n\n"
        "HELPFULNESS RULE: If a keyword is found as an affiliation, domain, or part of an ID but not fully defined, "
        "report exactly what is known about it from that context (e.g., 'is mentioned as a domain in an email') "
        "instead of saying you have no information."
    )

    user_prompt = f"Context:\n{context_text}\n\nQuestion: {state['query']}"

    if state["validation_status"] == "rejected":
        user_prompt += f"\n\nPREVIOUS FEEDBACK: {state['messages'][-1].content}\nPlease correct the errors mentioned."

    # Use structured output to get internal reasoning for the rationale field
    # We define the schema inline for simplicity
    from pydantic import BaseModel, Field

    class AnalystResponse(BaseModel):
        reasoning: str = Field(
            description="Step-by-step reasoning on how to answer based on context."
        )
        answer: str = Field(description="The final synthesized answer based STRICTLY on context.")

    structured_llm = llm.with_structured_output(AnalystResponse)

    try:
        response = structured_llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        final_answer = response.answer
        internal_reasoning = response.reasoning
    except Exception as e:
        logger.error(f"Structured synthesis failed: {e}")
        # Fallback to standard invoke if structured fails
        raw_response = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        final_answer = raw_response.content
        internal_reasoning = "Synthesized response using available context (Standard Mode)."

    return {
        "final_answer": final_answer,
        "iteration_count": state["iteration_count"] + 1,
        "current_agent": "validator",
        "activity_log": [
            {
                "node": "analyst",
                "status": "Drafted synthesized response.",
                "rationale": internal_reasoning,
            }
        ],
    }


@observe()
async def validator_node(state: NexusState) -> dict[str, Any]:
    """
    Checks for hallucinations using the cost-optimized LLM-based Self-RAG utility.
    """
    logger.info("Entering Validator node")

    if not state.get("final_answer"):
        return {"validation_status": "pending", "current_agent": "supervisor"}

    # Use the new async self_rag utility
    rag_result = await check_hallucination(state["final_answer"], state["retrieved_chunks"])

    passed = rag_result.get("passed", False)
    score = rag_result.get("hallucination_score", 1.0)
    reasoning = rag_result.get("reasoning", "No reasoning provided.")
    unsupported = rag_result.get("unsupported_claims", [])

    status = "approved" if passed else "rejected"

    feedback = reasoning
    if unsupported:
        feedback += f" Unsupported claims: {', '.join(unsupported)}"

    return {
        "validation_status": status,
        "hallucination_score": score,
        "messages": [AIMessage(content=f"Validator feedback: {feedback}")],
        "current_agent": "end" if passed else "supervisor",
        "activity_log": [
            {
                "node": "validator",
                "status": f"Validation {status}: {(1 - score) * 100:.0f}% faithfulness score.",
                "rationale": reasoning,
            }
        ],
    }
