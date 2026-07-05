from __future__ import annotations

from pathlib import Path
import sqlite3

from local_memory.config import MemoryConfig, should_exclude
from local_memory.cli import app
from local_memory.mcp_server import memory_health, memory_remember, memory_search
from local_memory.storage import MemoryStore
from typer.testing import CliRunner


def test_remember_and_search(tmp_path: Path) -> None:
    config = MemoryConfig.discover(tmp_path)
    config.ensure_dirs()
    with MemoryStore(config) as store:  # type: ignore[attr-defined]
        store.remember(
            "Decision: the memory system must stay local to the workspace and use uv only.",
            title="Local-only rule",
        )
        results = store.search("workspace uv memory")
    assert results
    assert "local" in results[0].text.lower()


def test_index_file_is_idempotent(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Alpha\n\nGraph memory and semantic search.")
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:  # type: ignore[attr-defined]
        first = store.index_file(note)
        second = store.index_file(note)
        health = store.health()
    assert first >= 1
    assert second == 0
    assert health["counts"]["documents"] == 1


def test_cli_ingest_directory(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "doc.md").write_text("Codex memory uses local uv only.")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "."])
    assert result.exit_code == 0, result.output
    assert "Indexed" in result.output


def test_should_exclude_local_venv_symlink(tmp_path: Path) -> None:
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    py_link = venv_bin / "python"
    py_link.symlink_to("/usr/bin/python3")
    assert should_exclude(py_link, tmp_path)


def test_duplicate_content_keeps_separate_provenance(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("Shared decision text about Project Atlas.")
    (tmp_path / "b.md").write_text("Shared decision text about Project Atlas.")
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:
        assert store.index_file(tmp_path / "a.md") == 1
        assert store.index_file(tmp_path / "b.md") == 1
        health = store.health()
        results = store.search("Project Atlas", limit=10)
    paths = {result.path for result in results}
    assert health["counts"]["documents"] == 2
    assert health["counts"]["chunks"] == 2
    assert {"a.md", "b.md"} <= paths


def test_remember_is_idempotent_by_content(tmp_path: Path) -> None:
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:
        first = store.remember("Decision: repeatable memory note.", title="Repeat")
        second = store.remember("Decision: repeatable memory note.", title="Repeat")
        health = store.health()
    assert first == 1
    assert second == 0
    assert health["counts"]["episodes"] == 1
    assert health["counts"]["documents"] == 1


def test_vector_backfill_and_health_invariants(tmp_path: Path) -> None:
    (tmp_path / "semantic.md").write_text("Semantic recall should find durable architecture memory.")
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:
        store.index_file(tmp_path / "semantic.md")
        before = store.health()
        embedded = store.embed_missing(limit=100)
        after = store.health()
        results = store.search("durable architecture recall", limit=3)
    assert before["ok"] is False
    assert any("vector_count_mismatch" in issue for issue in before["issues"])
    assert embedded == 1
    assert after["ok"] is True
    assert results
    assert results[0].path == "semantic.md"


def test_graph_expansion_returns_related_chunks(tmp_path: Path) -> None:
    (tmp_path / "one.md").write_text("Project Atlas uses a caller harness. UniqueNeedleOne.")
    (tmp_path / "two.md").write_text("Project Atlas requires durable graph recall. RelatedNeedleTwo.")
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:
        store.index_file(tmp_path / "one.md")
        store.index_file(tmp_path / "two.md")
        store.embed_missing(limit=100)
        results = store.search("UniqueNeedleOne", limit=5)
    paths = {result.path for result in results}
    assert "one.md" in paths
    assert "two.md" in paths


def test_backup_is_unique_and_restorable(tmp_path: Path) -> None:
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:
        store.remember("Backup restore memory sentinel.", title="Backup Sentinel")
        first = store.backup()
        second = store.backup()
    assert first != second
    for backup in (first, second):
        with sqlite3.connect(backup) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_cli_rejects_sibling_prefix_path(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "work"
    sibling = tmp_path / "workspace"
    root.mkdir()
    sibling.mkdir()
    outside = sibling / "outside.md"
    outside.write_text("This file must not be indexed.")
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", str(outside)])
    assert result.exit_code != 0
    assert "inside this workspace" in result.output


def test_empty_and_punctuation_queries_do_not_crash(tmp_path: Path) -> None:
    (tmp_path / "query.md").write_text("Memory handles punctuation queries safely.")
    config = MemoryConfig.discover(tmp_path)
    with MemoryStore(config) as store:
        store.index_file(tmp_path / "query.md")
        store.embed_missing(limit=10)
        empty_results = store.search("", limit=3)
        punctuation_results = store.search('"memory" OR safely', limit=3)
    assert isinstance(empty_results, list)
    assert punctuation_results


def test_mcp_functions_use_current_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert "remembered" in memory_remember("MCP durable sentinel.", title="MCP Sentinel")
    results = memory_search("durable sentinel", limit=3)
    health = memory_health()
    assert results
    assert health["counts"]["documents"] == 1


def test_cli_verify_passes_on_healthy_database(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "verify.md").write_text("Verify command probes local memory retrieval.")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    ingest = runner.invoke(app, ["ingest", ".", "--embed"])
    assert ingest.exit_code == 0, ingest.output
    verify = runner.invoke(app, ["verify"])
    assert verify.exit_code == 0, verify.output
    assert "memory verification passed" in verify.output
