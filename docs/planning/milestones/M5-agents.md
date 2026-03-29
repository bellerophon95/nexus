# M5 — Multi-Agent Orchestration (LangGraph)

> **Release goal:** Complex, multi-hop queries are routed to a LangGraph agent system (Supervisor → Researcher → Analyst → Validator) with a reflection loop. Tier 3 is fully functional.

## Deliverables

### 1. Agent State Schema (`agents/state.py`) — Extend M4 version
- [ ] `AgentMessage(sender, content, confidence, citations, tool_calls)`
- [ ] Extend `NexusState` with: `agent_messages`, `current_agent`, `iteration_count`, `max_iterations`, `validation_status`, `hallucination_score`

### 2. Supervisor Agent (`agents/supervisor.py`)
- [ ] `supervisor_node(state)` — reads state, decides next agent via LLM
- [ ] Decision prompt gives iteration count, chunk count, validation status
- [ ] Returns `{"current_agent": "researcher|analyst|validator|generate"}`
- [ ] Hard-stops at `max_iterations=3` regardless of validation status

### 3. Tool Definitions (`agents/tools.py`)
- [ ] `vector_search_tool` — wraps `retrieval_pipeline()` as a LangChain tool
- [ ] `web_search_tool` — Tavily or SerpAPI search (optional, can be stubbed in v1)
- [ ] `sql_query_tool` — parameterized Supabase query tool

### 4. Researcher Agent (`agents/researcher.py`)
- [ ] `researcher_node(state)` — ReAct agent with `RESEARCHER_TOOLS`
- [ ] Accumulates chunks into `state.retrieved_chunks`
- [ ] Appends `AgentMessage(sender="researcher", ...)` to state
- [ ] May execute multiple tool calls for multi-hop queries

### 5. Analyst Agent (`agents/analyst.py`)
- [ ] `analyst_node(state)` — synthesizes all retrieved chunks into a structured answer
- [ ] If `validation_status == "rejected"`, receives rejection feedback and must address it
- [ ] Prompt requires per-claim citations + confidence levels
- [ ] Appends analyst `AgentMessage` to state

### 6. Validator Agent (`agents/validator.py`)
- [ ] `validator_node(state)` — NLI-based fact check on analyst output
- [ ] Claims extracted from analyst message
- [ ] Each claim scored against all retrieved chunks via `cross-encoder/nli-deberta-v3-small`
- [ ] `avg_hallucination > 0.3` → `validation_status = "rejected"`, feedback appended
- [ ] Otherwise → `validation_status = "approved"`

### 7. LangGraph Compilation (`agents/graph.py`)
- [ ] `build_nexus_graph()` — `StateGraph(NexusState)` with all nodes
- [ ] Conditional edges:
  - `router` → `generate | retrieve | supervisor`
  - `supervisor` → `researcher | analyst | validator | generate`
  - `validator` → `generate (approved) | supervisor (rejected)`
- [ ] Persist checkpoints via `SqliteSaver` 
- [ ] Compile with `checkpointer`

### 8. Wire Tier 3 into Query Endpoint
- [ ] Update `routes_query.py` to stream agent step events
- [ ] SSE event type `agent_step` carries `{"tool": "...", "agent": "..."}`
- [ ] Final `done` event carries full citations from `NexusState.citations`

## LangGraph Node Map

```
[router]
   ├── direct → [generate] → END
   ├── rag    → [retrieve] → [generate] → END
   └── agentic → [supervisor]
                    ├── researcher → [researcher] → [supervisor]
                    ├── analyst   → [analyst]   → [supervisor]
                    ├── validator → [validator]
                    │                ├── approved → [generate] → END
                    │                └── rejected → [supervisor]
                    └── generate  → [generate] → END
```

## Tests

- [ ] `tests/unit/test_router.py` — simple queries → tier 1/2, complex → tier 3
- [ ] `tests/integration/test_agent_graph.py` — run a multi-hop question through the full graph, assert validator runs, final answer contains citations
- [ ] Reflection loop test: mock validator to reject on first pass, verify analyst reinvokes

## Acceptance Criteria

- [ ] A multi-hop question (e.g. "Compare the methodologies used by author X and author Y in papers about Z") triggers Supervisor → Researcher → Analyst → Validator flow
- [ ] Langfuse trace shows all agent spans with correct hierarchy
- [ ] Reflection loop activates when hallucination > 30% — analyst retries with feedback
- [ ] System never infinite-loops — hard cap at `max_iterations=3`
- [ ] SSE stream emits `agent_step` events as agents work

## Estimated Effort: 3–4 days
