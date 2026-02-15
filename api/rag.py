"""RAG pipeline: retrieve relevant chunks from ChromaDB and generate responses."""

import os
from typing import AsyncIterator

import chromadb

SYSTEM_PROMPT = """You are an AI research assistant analyzing the Jeffrey Epstein document archive. \
Answer questions based only on the provided document excerpts. \
Cite sources by document title and page number when referencing specific information. \
If the documents don't contain enough information to answer the question, say so clearly. \
Be precise and factual. Do not speculate beyond what the documents show."""


def get_collection() -> chromadb.Collection:
    chroma_path = os.environ.get("CHROMA_DB_PATH", "chroma_db")
    client = chromadb.PersistentClient(path=chroma_path)
    return client.get_or_create_collection(
        name="epstein_docs",
        metadata={"hnsw:space": "cosine"},
    )


def retrieve(query: str, n_results: int = 8) -> list[dict]:
    """Retrieve relevant document chunks for a query."""
    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    return chunks


def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into context for the LLM."""
    if not chunks:
        return "No relevant documents found in the archive."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        source_label = f"{meta.get('title', meta.get('filename', 'Unknown'))}"
        page = meta.get("page_num", "?")
        parts.append(
            f"[Source {i}: {source_label}, Page {page}]\n{chunk['text']}"
        )

    return "\n\n---\n\n".join(parts)


def build_messages(
    query: str,
    chunks: list[dict],
    history: list[dict] | None = None,
) -> list[dict]:
    """Build the message list for the LLM call."""
    context = build_context(chunks)

    messages = []

    # Include conversation history (last 10 turns max)
    if history:
        for msg in history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

    # Current query with context
    user_message = f"""Based on the following document excerpts from the Epstein archive, answer my question.

DOCUMENT EXCERPTS:
{context}

QUESTION: {query}"""

    messages.append({"role": "user", "content": user_message})
    return messages


async def generate_anthropic(
    messages: list[dict],
) -> AsyncIterator[str]:
    """Stream response from Anthropic Claude."""
    import anthropic

    client = anthropic.AsyncAnthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )

    async with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def generate_openai(
    messages: list[dict],
) -> AsyncIterator[str]:
    """Stream response from OpenAI."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    system_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=system_messages + messages,
        max_tokens=2048,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


async def generate(
    query: str,
    history: list[dict] | None = None,
    provider: str = "anthropic",
    n_results: int = 8,
) -> tuple[list[dict], AsyncIterator[str]]:
    """Full RAG pipeline: retrieve + generate.

    Returns (sources, text_stream) where sources is the list of retrieved chunks
    and text_stream is an async iterator of response text.
    """
    chunks = retrieve(query, n_results=n_results)
    messages = build_messages(query, chunks, history)

    if provider == "openai":
        stream = generate_openai(messages)
    else:
        stream = generate_anthropic(messages)

    # Return sources metadata for citation
    sources = []
    for chunk in chunks:
        meta = chunk["metadata"]
        sources.append({
            "title": meta.get("title", ""),
            "filename": meta.get("filename", ""),
            "page_num": meta.get("page_num"),
            "source": meta.get("source", ""),
            "url": meta.get("url", ""),
            "distance": chunk["distance"],
        })

    return sources, stream
