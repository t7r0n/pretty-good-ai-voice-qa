from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    ".codex_local_memory",
    "artifacts",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".codex_local_memory/cache",
    ".codex_local_memory/backups",
    "node_modules",
}


@dataclass(frozen=True)
class MemoryConfig:
    root: Path
    state_dir: Path
    db_path: Path
    backups_dir: Path
    cache_dir: Path
    embedding_model: str = "local-hash-v1"
    embedding_dim: int = 384
    vector_search_enabled: bool = True
    chunk_chars: int = 1800
    chunk_overlap: int = 220

    @classmethod
    def discover(cls, root: Path | None = None) -> "MemoryConfig":
        project_root = (root or Path.cwd()).resolve()
        state_dir = project_root / ".codex_local_memory"
        data = {}
        config_path = state_dir / "config.yaml"
        if config_path.exists():
            data = yaml.safe_load(config_path.read_text()) or {}
        return cls(
            root=project_root,
            state_dir=state_dir,
            db_path=state_dir / "memory.sqlite",
            backups_dir=state_dir / "backups",
            cache_dir=state_dir / "cache",
            embedding_model=data.get("embedding_model", "local-hash-v1"),
            embedding_dim=int(data.get("embedding_dim", 384)),
            vector_search_enabled=_bool_config(
                data.get("vector_search_enabled", True),
                os.getenv("PG_MEMORY_VECTOR_SEARCH"),
            ),
            chunk_chars=int(data.get("chunk_chars", 1800)),
            chunk_overlap=int(data.get("chunk_overlap", 220)),
        )

    def ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def write_default_config(self) -> None:
        self.ensure_dirs()
        path = self.state_dir / "config.yaml"
        if path.exists():
            return
        path.write_text(
            yaml.safe_dump(
                {
                    "embedding_model": self.embedding_model,
                    "embedding_dim": self.embedding_dim,
                    "vector_search_enabled": self.vector_search_enabled,
                    "chunk_chars": self.chunk_chars,
                    "chunk_overlap": self.chunk_overlap,
                    "scope": "workspace-local-only",
                },
                sort_keys=False,
            )
        )


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def should_exclude(path: Path, root: Path) -> bool:
    try:
        rel = path.absolute().relative_to(root.resolve()).as_posix()
    except ValueError:
        return True
    parts = set(rel.split("/"))
    if parts & {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}:
        return True
    return any(rel == item or rel.startswith(f"{item}/") for item in DEFAULT_EXCLUDES)


def _bool_config(value: object, env_value: str | None) -> bool:
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
