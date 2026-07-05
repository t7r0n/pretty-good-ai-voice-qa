from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import MemoryConfig
from .storage import MemoryStore

mcp = FastMCP("pretty-good-local-memory")


@mcp.tool()
def memory_remember(text: str, title: str = "MCP memory note", kind: str = "note") -> str:
    """Save a durable note in this workspace-local memory database."""
    with MemoryStore(MemoryConfig.discover()) as store:  # type: ignore[attr-defined]
        chunks = store.remember(text, title=title, kind=kind)
        embedded = store.embed_missing(limit=max(chunks, 1))
    return f"remembered {chunks} chunk(s), embedded {embedded}"


@mcp.tool()
def memory_search(query: str, limit: int = 6) -> list[dict[str, str | float | int]]:
    """Search this workspace-local memory database."""
    with MemoryStore(MemoryConfig.discover()) as store:  # type: ignore[attr-defined]
        results = store.search(query, limit=limit)
    return [
        {
            "chunk_id": result.chunk_id,
            "path": result.path,
            "title": result.title,
            "score": result.score,
            "text": result.text,
            "source": result.source,
        }
        for result in results
    ]


@mcp.tool()
def memory_health() -> dict:
    """Inspect local memory health and index counts."""
    with MemoryStore(MemoryConfig.discover()) as store:  # type: ignore[attr-defined]
        return store.health()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
