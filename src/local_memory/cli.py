from __future__ import annotations

import sqlite3
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import MemoryConfig, is_within, should_exclude
from .storage import MemoryStore

app = typer.Typer(help="Workspace-local memory for this directory.")
console = Console()


@app.command()
def init() -> None:
    """Initialize local memory state and schema."""
    config = MemoryConfig.discover()
    config.ensure_dirs()
    config.write_default_config()
    with MemoryStore(config) as store:  # type: ignore[attr-defined]
        mcp_path = store.write_mcp_example()
        status = store.health()
    console.print(f"Initialized local memory at [bold]{config.state_dir}[/bold]")
    console.print(f"Database: {status['db']}")
    console.print(f"Local MCP example: {mcp_path}")


@app.command()
def remember(
    text: str = typer.Argument(..., help="Durable text to remember verbatim."),
    title: str = typer.Option("Memory note", "--title", "-t"),
    kind: str = typer.Option("note", "--kind", "-k"),
) -> None:
    """Save a durable note and index it."""
    with _store() as store:
        chunks = store.remember(text, title=title, kind=kind)
        embedded = store.embed_missing(limit=max(chunks, 1))
    console.print(f"Remembered [bold]{title}[/bold] ({chunks} indexed chunk(s), {embedded} embedded).")


@app.command()
def ingest(
    path: Path = typer.Argument(Path("."), help="File or directory to index."),
    embed: bool = typer.Option(False, "--embed", help="Also backfill vector embeddings."),
) -> None:
    """Index workspace text files."""
    config = MemoryConfig.discover()
    target = path.resolve()
    if not is_within(target, config.root):
        raise typer.BadParameter("Path must be inside this workspace.")
    indexed = 0
    with _store() as store:
        if target.is_file():
            indexed += store.index_file(target)
        else:
            for item in target.rglob("*"):
                if item.is_file() and not should_exclude(item, config.root):
                    indexed += store.index_file(item)
        embedded = store.embed_missing(limit=2048) if embed else 0
    console.print(f"Indexed {indexed} chunk(s). Embedded {embedded} chunk(s).")


@app.command()
def search(query: str, limit: int = typer.Option(8, "--limit", "-n")) -> None:
    """Search hybrid keyword/vector/graph memory."""
    with _store() as store:
        results = store.search(query, limit=limit)
    table = Table("Score", "Source", "Path", "Excerpt")
    for result in results:
        excerpt = " ".join(result.text.split())[:260]
        table.add_row(str(result.score), result.source, result.path, excerpt)
    console.print(table if results else "No results.")


@app.command()
def context(query: str, limit: int = typer.Option(6, "--limit", "-n")) -> None:
    """Print compact recall context for an agent prompt."""
    with _store() as store:
        results = store.search(query, limit=limit)
    for idx, result in enumerate(results, start=1):
        console.print(f"\n## Memory {idx}: {result.title} ({result.path}, score={result.score})")
        console.print(result.text.strip())


@app.command()
def backup() -> None:
    """Create a timestamped SQLite backup."""
    with _store() as store:
        path = store.backup()
    console.print(f"Backup written: {path}")


@app.command()
def embed(limit: int = typer.Option(2048, "--limit", "-n")) -> None:
    """Backfill local vector embeddings for already indexed chunks."""
    with _store() as store:
        count = store.embed_missing(limit=limit)
    console.print(f"Embedded {count} chunk(s).")


@app.command()
def health() -> None:
    """Run integrity checks and print index counts."""
    with _store() as store:
        status = store.health()
    table = Table("Check", "Value")
    table.add_row("Root", status["root"])
    table.add_row("DB", status["db"])
    table.add_row("Integrity", status["integrity"])
    table.add_row("sqlite-vec", str(status["sqlite_vec"]))
    table.add_row("Vector rows", str(status["vector_rows"]))
    table.add_row("FTS rows", str(status["fts_rows"]))
    table.add_row("OK", str(status["ok"]))
    table.add_row("Issues", ", ".join(status["issues"]) if status["issues"] else "none")
    for key, value in status["counts"].items():
        table.add_row(key, str(value))
    console.print(table)


@app.command()
def verify() -> None:
    """Run a production pre-flight check against the live memory database."""
    failures: list[str] = []
    with _store() as store:
        status = store.health()
        if not status["ok"]:
            failures.extend(status["issues"])
        if not status["sqlite_vec"]:
            failures.append("sqlite_vec_unavailable")
        if status["counts"]["documents"] and not status["counts"]["chunks"]:
            failures.append("documents_without_chunks")
        probe = store.conn.execute(
            "SELECT text FROM chunks ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if probe:
            probe_query = " ".join(str(probe["text"]).split()[:8])
            if probe_query and not store.search(probe_query, limit=3):
                failures.append("search_probe_failed")
        backup_path = store.backup()

    with sqlite3.connect(backup_path) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            failures.append("backup_integrity_failed")
        if conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] != status["counts"]["chunks"]:
            failures.append("backup_chunk_count_mismatch")

    if failures:
        for failure in failures:
            console.print(f"[red]FAIL[/red] {failure}")
        raise typer.Exit(1)
    console.print(f"[green]OK[/green] memory verification passed. Backup: {backup_path}")


def _store() -> MemoryStore:
    return MemoryStore(MemoryConfig.discover())
