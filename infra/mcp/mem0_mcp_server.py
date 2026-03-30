"""MCP server wrapping self-hosted Mem0 REST API."""

import os
import httpx
from fastmcp import FastMCP

MEM0_BASE_URL = os.environ.get("MEM0_BASE_URL", "http://localhost:8888")

mcp = FastMCP("mem0-local")
_client = httpx.Client(base_url=MEM0_BASE_URL, timeout=30)


@mcp.tool()
def add_memory(content: str, user_id: str = "bench") -> str:
    """Store a memory in Mem0 for a given user."""
    resp = _client.post("/memories", json={
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
    })
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    return f"Added {len(results)} memories"


@mcp.tool()
def search_memory(query: str, user_id: str = "bench", limit: int = 10) -> str:
    """Search memories by semantic similarity."""
    resp = _client.post("/search", json={
        "query": query,
        "user_id": user_id,
        "limit": limit,
    })
    resp.raise_for_status()
    data = resp.json()
    memories = data if isinstance(data, list) else data.get("results", [])
    if not memories:
        return "No memories found"
    parts = []
    for m in memories:
        text = m.get("memory", m.get("text", str(m)))
        score = m.get("score", "?")
        parts.append(f"[score={score}] {text}")
    return "\n---\n".join(parts)


@mcp.tool()
def list_memories(user_id: str = "bench") -> str:
    """List all memories for a user."""
    resp = _client.get("/memories", params={"user_id": user_id})
    resp.raise_for_status()
    data = resp.json()
    memories = data if isinstance(data, list) else data.get("results", [])
    if not memories:
        return "No memories"
    parts = []
    for m in memories:
        mid = m.get("id", "?")
        text = m.get("memory", m.get("text", ""))[:120]
        parts.append(f"[{mid}] {text}")
    return f"{len(parts)} memories:\n" + "\n".join(parts)


@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete a specific memory by ID."""
    resp = _client.delete(f"/memories/{memory_id}")
    resp.raise_for_status()
    return f"Deleted memory {memory_id}"


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
