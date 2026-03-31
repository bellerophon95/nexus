import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.observability.cost_tracker import calculate_cost, score_cost
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Initialize Async OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


@observe(name="Generate RAG Answer")
async def generate_answer(
    query: str, context_chunks: list[dict[str, Any]], history: list[dict[str, Any]] | None = None
) -> str:
    """
    Generates a natural language answer based on the provided query, context, and history.
    """
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set.")
        return "Error: OpenAI API key is missing."

    # Format context for the prompt
    context_text = ""
    for i, chunk in enumerate(context_chunks):
        title = chunk.get("title", "Unknown Source")
        context_text += f"\n--- Source: {title} (Chunk {i + 1}) ---\n{chunk['text']}\n"

    system_prompt = (
        "You are Project Nexus, an advanced AI research assistant. "
        "Your primary goal is to answer the user's question accurately. "
        "If context information is provided below, prioritize it and cite sources specifically. "
        "If a question is conversational (e.g., greetings, 'Who are you?', 'What can you do?'), "
        "answer naturally based on your persona as Project Nexus. "
        "If you are answering factual questions without context, explicitly state that you "
        "are using your general knowledge because no specific documents were found. "
        "Be professional, precise, and helpful. Use clear Markdown formatting."
    )

    # Build message list with history
    messages = [{"role": "system", "content": system_prompt}]

    if history:
        # Include last 10 messages for context window efficiency
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current query with context
    user_content = f"Context Information (if any):\n{context_text}\n\nUser Question: {query}"
    messages.append({"role": "user", "content": user_content})

    try:
        model_name = "gpt-4o-mini"
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3,  # Slightly higher for better conversational flow
        )

        # Track cost
        usage = response.usage
        cost = calculate_cost(
            model_name=model_name,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

        # Extract trace_id from langfuse (requires langfuse >= 2.x)
        from langfuse.decorators import langfuse_context

        trace_id = langfuse_context.get_current_trace_id()
        if trace_id:
            score_cost(trace_id, cost)

        answer = response.choices[0].message.content
        logger.info(f"Successfully generated RAG answer. Cost: ${cost:.6f}")
        return answer

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return f"Error: Failed to generate an answer. {e!s}"


@observe(name="Generate RAG Answer Stream")
async def generate_answer_stream(
    query: str, context_chunks: list[dict[str, Any]], history: list[dict[str, Any]] | None = None
):
    """
    Generates a natural language answer using streaming with multi-turn history support.
    """
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set.")
        yield "Error: OpenAI API key is missing."
        return

    # Format context for the prompt
    context_text = ""
    for i, chunk in enumerate(context_chunks):
        title = chunk.get("title", "Unknown Source")
        context_text += f"\n--- Source: {title} (Chunk {i + 1}) ---\n{chunk['text']}\n"

    system_prompt = (
        "You are Project Nexus, an advanced AI research assistant. "
        "Your primary goal is to answer the user's question accurately. "
        "If context information is provided below, prioritize it and cite sources specifically. "
        "If a question is conversational (e.g., greetings, 'Who are you?', 'What can you do?'), "
        "answer naturally based on your persona as Project Nexus. "
        "If you are answering factual questions without context, explicitly state that you "
        "are using your general knowledge because no specific documents were found. "
        "Be professional, precise, and helpful. Use clear Markdown formatting."
    )

    # Build message list with history
    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_content = f"Context Information (if any):\n{context_text}\n\nUser Question: {query}"
    messages.append({"role": "user", "content": user_content})

    try:
        model_name = "gpt-4o-mini"
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.3,  # Slightly higher for more natural flow while staying precise
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"Streaming generation failed: {e}")
        yield f"Error: Failed to generate an answer. {e!s}"


@observe(name="Generate Chat Title")
async def generate_title(query: str) -> str:
    """
    Summarizes a user query into a concise 2-4 word title for the chat history sidebar.
    """
    if not settings.OPENAI_API_KEY:
        return query[:30] + "..."

    try:
        model_name = "gpt-4o-mini"
        system_prompt = (
            "You are a helpful assistant that generates concise, 2-4 word titles for chat threads. "
            "The title should be professional and reflect the core topic of the user's query. "
            "Do NOT use quotes, periods, or the word 'Title'. "
            "Example Query: 'How do I index a PDF into the vector store?' -> 'PDF Vector Indexing'"
        )

        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            max_tokens=20,
            temperature=0.3,
        )

        title = response.choices[0].message.content.strip()
        # Fallback if too long or empty
        if not title or len(title) > 50:
            return query[:30] + "..."
        return title

    except Exception as e:
        logger.error(f"Title generation failed: {e}")
        return query[:30] + "..."
