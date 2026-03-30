"""Graphiti client for benchmark: add episodes and search the knowledge graph."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.llm_client import LLMConfig, OpenAIClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

load_dotenv()

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))

LLM_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.cerebras.ai/v1")
LLM_MODEL = os.getenv("MODEL_NAME", "gpt-oss-120b")

EMBEDDER_BASE_URL = os.getenv("EMBEDDER_BASE_URL", "http://localhost:11434/v1")
EMBEDDER_MODEL = os.getenv("EMBEDDER_MODEL", "nomic-embed-text")
EMBEDDER_API_KEY = os.getenv("EMBEDDER_API_KEY", "not-needed")


async def get_graphiti() -> Graphiti:
    driver = FalkorDriver(host=FALKORDB_HOST, port=FALKORDB_PORT)

    llm_client = OpenAIClient(
        LLMConfig(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            model=LLM_MODEL,
        )
    )

    embedder = OpenAIEmbedder(
        OpenAIEmbedderConfig(
            api_key=EMBEDDER_API_KEY,
            base_url=EMBEDDER_BASE_URL,
            model=EMBEDDER_MODEL,
        )
    )

    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=llm_client,
        embedder=embedder,
    )
    await graphiti.build_indices_and_constraints()
    return graphiti


async def add_episodes(graphiti: Graphiti, episodes: list[dict]):
    """Add a list of episodes. Each dict has 'name' and 'content' keys."""
    for ep in episodes:
        t0 = time.time()
        await graphiti.add_episode(
            name=ep["name"],
            episode_body=ep["content"],
            source_description="Bean & Brew test context",
            reference_time=datetime.now(timezone.utc),
        )
        elapsed = time.time() - t0
        print(f"  Added '{ep['name']}' in {elapsed:.1f}s")


async def search(graphiti: Graphiti, query: str, num_results: int = 10):
    """Search the knowledge graph."""
    t0 = time.time()
    results = await graphiti.search(query=query, num_results=num_results)
    elapsed = time.time() - t0
    print(f"  Search '{query[:50]}...' → {len(results)} results in {elapsed:.1f}s")
    return results


async def main():
    import sys

    graphiti = await get_graphiti()

    if len(sys.argv) < 2:
        print("Usage: python client.py [add|search|clear]")
        return

    cmd = sys.argv[1]

    if cmd == "add":
        with open("test_context_episodes.json") as f:
            episodes = json.load(f)
        await add_episodes(graphiti, episodes)

    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "какие тесты есть в проекте"
        results = await search(graphiti, query)
        for r in results:
            print(f"  [{r.score:.3f}] {r.fact}" if hasattr(r, "fact") else f"  {r}")

    elif cmd == "clear":
        print("Clearing graph...")
        await graphiti.clear()
        print("Done.")

    await graphiti.close()


if __name__ == "__main__":
    asyncio.run(main())
