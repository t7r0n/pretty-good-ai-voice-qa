from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from .chunking import chunk_text, estimate_tokens, extract_entities, normalize_entity, sha256_text
from .config import MemoryConfig


TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".csv",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".pdf",
}


@dataclass(frozen=True)
class SearchResult:
    chunk_id: int
    path: str
    title: str
    score: float
    text: str
    source: str


class MemoryStore:
    def __init__(self, config: MemoryConfig | None = None) -> None:
        self.config = config or MemoryConfig.discover()
        self.config.ensure_dirs()
        self.conn = sqlite3.connect(self.config.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._vec_available = self._load_vec()
        self.init_schema()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def _load_vec(self) -> bool:
        try:
            import sqlite_vec

            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
            return True
        except Exception:
            try:
                self.conn.enable_load_extension(False)
            except Exception:
                pass
            return False

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                mtime REAL,
                size INTEGER NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL,
                text TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                tokens_est INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                source TEXT NOT NULL,
                summary TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                valid_from REAL NOT NULL,
                valid_to REAL
            );
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY,
                name_norm TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'concept',
                summary TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY,
                subject_id INTEGER NOT NULL REFERENCES entities(id),
                predicate TEXT NOT NULL,
                object_id INTEGER NOT NULL REFERENCES entities(id),
                confidence REAL NOT NULL DEFAULT 0.5,
                episode_id TEXT REFERENCES episodes(id),
                valid_from REAL NOT NULL,
                valid_to REAL,
                invalidated_by TEXT,
                created_at REAL NOT NULL,
                UNIQUE(subject_id, predicate, object_id, episode_id)
            );
            CREATE TABLE IF NOT EXISTS chunk_entities (
                chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
                entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                PRIMARY KEY (chunk_id, entity_id)
            );
            """
        )
        self._ensure_fts_table()
        if self._vec_available:
            try:
                self.conn.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0(embedding float[{self.config.embedding_dim}])"
                )
            except sqlite3.DatabaseError:
                self._vec_available = False
        self.conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', '1')"
        )
        self.conn.commit()

    def _ensure_fts_table(self) -> None:
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchone()
        if row and "content=''" in (row["sql"] or ""):
            self.conn.execute("DROP TABLE chunks_fts")
            row = None
        if not row:
            self.conn.execute(
                "CREATE VIRTUAL TABLE chunks_fts USING fts5(title, path, text)"
            )
            existing = self.conn.execute(
                """
                SELECT c.id, c.text, d.title, d.path
                FROM chunks c JOIN documents d ON d.id = c.document_id
                """
            ).fetchall()
            for item in existing:
                self.conn.execute(
                    "INSERT OR REPLACE INTO chunks_fts(rowid, title, path, text) VALUES (?, ?, ?, ?)",
                    (item["id"], item["title"], item["path"], item["text"]),
                )

    def remember(self, text: str, title: str = "Memory note", kind: str = "note") -> int:
        digest = sha256_text(text)
        note_id = f"memory://{digest}"
        now = time.time()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO episodes(id, kind, source, summary, raw_text, sha256, created_at, valid_from)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (note_id, kind, note_id, title, text, digest, now, now),
        )
        return self.index_text(note_id, text, title=title, source_type=kind)

    def index_file(self, path: Path) -> int:
        resolved = path.resolve()
        suffix = resolved.suffix.lower()
        if suffix not in TEXT_EXTENSIONS:
            return 0
        if suffix == ".pdf":
            text = _extract_pdf_text(resolved)
        else:
            try:
                text = resolved.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = resolved.read_text(encoding="utf-8", errors="ignore")
        rel = resolved.relative_to(self.config.root).as_posix()
        stat = resolved.stat()
        return self.index_text(
            rel,
            text,
            title=resolved.name,
            source_type="file",
            mtime=stat.st_mtime,
            size=stat.st_size,
        )

    def index_text(
        self,
        path: str,
        text: str,
        title: str,
        source_type: str,
        mtime: float | None = None,
        size: int | None = None,
    ) -> int:
        now = time.time()
        digest = sha256_text(text)
        size = size if size is not None else len(text.encode("utf-8"))
        existing = self.conn.execute("SELECT id, sha256 FROM documents WHERE path = ?", (path,)).fetchone()
        if existing and existing["sha256"] == digest:
            return 0
        if existing:
            doc_id = int(existing["id"])
            old_chunks = self.conn.execute("SELECT id FROM chunks WHERE document_id = ?", (doc_id,)).fetchall()
            for row in old_chunks:
                self.conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (row["id"],))
                if self._vec_available:
                    self.conn.execute("DELETE FROM chunk_vec WHERE rowid = ?", (row["id"],))
            self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            self.conn.execute(
                """
                UPDATE documents SET title=?, sha256=?, mtime=?, size=?, updated_at=?
                WHERE id=?
                """,
                (title, digest, mtime, size, now, doc_id),
            )
        else:
            cur = self.conn.execute(
                """
                INSERT INTO documents(path, source_type, title, sha256, mtime, size, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (path, source_type, title, digest, mtime, size, now, now),
            )
            doc_id = int(cur.lastrowid)

        chunks = chunk_text(text, self.config.chunk_chars, self.config.chunk_overlap)
        for chunk in chunks:
            storage_sha = sha256_text(f"{path}\0{chunk.ordinal}\0{chunk.text}")
            self.conn.execute(
                """
                INSERT OR IGNORE INTO chunks(document_id, ordinal, text, sha256, start_char, end_char, tokens_est, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    chunk.ordinal,
                    chunk.text,
                    storage_sha,
                    chunk.start_char,
                    chunk.end_char,
                    estimate_tokens(chunk.text),
                    now,
                ),
            )
            row = self.conn.execute(
                "SELECT id FROM chunks WHERE document_id = ? AND ordinal = ?",
                (doc_id, chunk.ordinal),
            ).fetchone()
            chunk_id = int(row["id"])
            self.conn.execute(
                "INSERT OR REPLACE INTO chunks_fts(rowid, title, path, text) VALUES (?, ?, ?, ?)",
                (chunk_id, title, path, chunk.text),
            )
            self._index_entities(chunk_id, chunk.text, now)
        self.conn.commit()
        return len(chunks)

    def _index_entities(self, chunk_id: int, text: str, now: float) -> None:
        entities = extract_entities(text)
        entity_ids: list[int] = []
        for name in entities:
            norm = normalize_entity(name)
            self.conn.execute(
                """
                INSERT OR IGNORE INTO entities(name_norm, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (norm, name, now, now),
            )
            row = self.conn.execute("SELECT id FROM entities WHERE name_norm = ?", (norm,)).fetchone()
            entity_id = int(row["id"])
            entity_ids.append(entity_id)
            self.conn.execute(
                "INSERT OR IGNORE INTO chunk_entities(chunk_id, entity_id) VALUES (?, ?)",
                (chunk_id, entity_id),
            )
        for idx, subject_id in enumerate(entity_ids):
            for object_id in entity_ids[idx + 1 : idx + 6]:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO facts(subject_id, predicate, object_id, confidence, valid_from, created_at)
                    VALUES (?, 'co_occurs_with', ?, 0.35, ?, ?)
                    """,
                    (subject_id, object_id, now, now),
                )

    def embed_missing(self, limit: int = 128) -> int:
        if not self._vec_available:
            return 0
        rows = self.conn.execute(
            """
            SELECT c.id, c.text FROM chunks c
            LEFT JOIN chunk_vec v ON v.rowid = c.id
            WHERE v.rowid IS NULL
            ORDER BY c.id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        if not rows:
            return 0
        try:
            import sqlite_vec

            from .embeddings import embed_texts

            vectors = embed_texts([row["text"] for row in rows], self.config.embedding_model)
            for row, vector in zip(rows, vectors, strict=True):
                if len(vector) != self.config.embedding_dim:
                    self._vec_available = False
                    return 0
                self.conn.execute(
                    "INSERT OR REPLACE INTO chunk_vec(rowid, embedding) VALUES (?, ?)",
                    (row["id"], sqlite_vec.serialize_float32(vector)),
                )
            self.conn.commit()
            return len(rows)
        except Exception:
            self._vec_available = False
            return 0

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        candidates: dict[int, float] = {}
        fts_rows = self.conn.execute(
            """
            SELECT rowid AS chunk_id, bm25(chunks_fts) AS rank
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (_fts_query(query), max(limit * 4, 20)),
        ).fetchall()
        for pos, row in enumerate(fts_rows):
            candidates[int(row["chunk_id"])] = candidates.get(int(row["chunk_id"]), 0.0) + 1.0 / (pos + 1)

        if self._vec_available and self.config.vector_search_enabled:
            try:
                import sqlite_vec

                from .embeddings import embed_texts

                [vector] = embed_texts([query], self.config.embedding_model)
                vec_rows = self.conn.execute(
                    """
                    SELECT rowid AS chunk_id, distance
                    FROM chunk_vec
                    WHERE embedding MATCH ? AND k = ?
                    ORDER BY distance
                    """,
                    (sqlite_vec.serialize_float32(vector), max(limit * 4, 20)),
                ).fetchall()
                for pos, row in enumerate(vec_rows):
                    candidates[int(row["chunk_id"])] = candidates.get(int(row["chunk_id"]), 0.0) + 0.8 / (pos + 1)
            except Exception:
                self._vec_available = False

        if not candidates:
            rows = self.conn.execute("SELECT id, text FROM chunks ORDER BY id DESC LIMIT 200").fetchall()
            for row in rows:
                score = fuzz.partial_ratio(query.lower(), row["text"].lower()) / 100.0
                if score > 0.35:
                    candidates[int(row["id"])] = score * 0.25

        expanded = self._expand_graph(candidates)
        candidates.update(expanded)
        ranked_ids = sorted(candidates, key=lambda cid: candidates[cid], reverse=True)[:limit]
        if not ranked_ids:
            return []
        placeholders = ",".join("?" for _ in ranked_ids)
        rows = self.conn.execute(
            f"""
            SELECT c.id, c.text, d.path, d.title, d.source_type
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE c.id IN ({placeholders})
            """,
            ranked_ids,
        ).fetchall()
        by_id = {int(row["id"]): row for row in rows}
        return [
            SearchResult(
                chunk_id=cid,
                path=by_id[cid]["path"],
                title=by_id[cid]["title"],
                score=round(candidates[cid], 4),
                text=by_id[cid]["text"],
                source=by_id[cid]["source_type"],
            )
            for cid in ranked_ids
            if cid in by_id
        ]

    def _expand_graph(self, candidates: dict[int, float]) -> dict[int, float]:
        if not candidates:
            return {}
        top_ids = list(candidates)[:8]
        placeholders = ",".join("?" for _ in top_ids)
        rows = self.conn.execute(
            f"""
            SELECT DISTINCT ce2.chunk_id
            FROM chunk_entities ce1
            JOIN facts f ON f.subject_id = ce1.entity_id OR f.object_id = ce1.entity_id
            JOIN chunk_entities ce2 ON ce2.entity_id = f.subject_id OR ce2.entity_id = f.object_id
            WHERE ce1.chunk_id IN ({placeholders}) AND ce2.chunk_id NOT IN ({placeholders})
            LIMIT 24
            """,
            top_ids + top_ids,
        ).fetchall()
        return {int(row["chunk_id"]): 0.12 for row in rows}

    def invalidate_fact(self, fact_id: int, reason: str) -> None:
        now = time.time()
        self.conn.execute(
            "UPDATE facts SET valid_to=?, invalidated_by=? WHERE id=? AND valid_to IS NULL",
            (now, reason, fact_id),
        )
        self.conn.commit()

    def backup(self) -> Path:
        self.config.backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = f"{time.time_ns()}-{uuid.uuid4().hex[:8]}"
        target = self.config.backups_dir / f"memory-{stamp}-{suffix}.sqlite"
        with sqlite3.connect(target) as dst:
            self.conn.backup(dst)
        return target

    def health(self) -> dict[str, Any]:
        integrity = self.conn.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            table: int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ["documents", "chunks", "episodes", "entities", "facts"]
        }
        vec_count = None
        if self._vec_available:
            try:
                vec_count = int(self.conn.execute("SELECT COUNT(*) FROM chunk_vec").fetchone()[0])
            except sqlite3.DatabaseError:
                vec_count = None
        fts_count = int(self.conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0])
        orphan_chunk_entities = int(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM chunk_entities ce
                LEFT JOIN chunks c ON c.id = ce.chunk_id
                LEFT JOIN entities e ON e.id = ce.entity_id
                WHERE c.id IS NULL OR e.id IS NULL
                """
            ).fetchone()[0]
        )
        orphan_facts = int(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM facts f
                LEFT JOIN entities s ON s.id = f.subject_id
                LEFT JOIN entities o ON o.id = f.object_id
                WHERE s.id IS NULL OR o.id IS NULL
                """
            ).fetchone()[0]
        )
        issues: list[str] = []
        if integrity != "ok":
            issues.append(f"sqlite_integrity:{integrity}")
        if fts_count != counts["chunks"]:
            issues.append(f"fts_count_mismatch:{fts_count}!={counts['chunks']}")
        if self._vec_available and vec_count not in (None, counts["chunks"]):
            issues.append(f"vector_count_mismatch:{vec_count}!={counts['chunks']}")
        if orphan_chunk_entities:
            issues.append(f"orphan_chunk_entities:{orphan_chunk_entities}")
        if orphan_facts:
            issues.append(f"orphan_facts:{orphan_facts}")
        return {
            "root": str(self.config.root),
            "db": str(self.config.db_path),
            "integrity": integrity,
            "sqlite_vec": self._vec_available,
            "vector_rows": vec_count,
            "fts_rows": fts_count,
            "issues": issues,
            "ok": not issues,
            "counts": counts,
        }

    def write_mcp_example(self) -> Path:
        path = self.config.state_dir / "mcp.local.example.json"
        payload = {
            "mcpServers": {
                "pretty-good-local-memory": {
                    "command": "uv",
                    "args": ["run", "pg-memory-mcp"],
                    "cwd": str(self.config.root),
                }
            }
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path


def _fts_query(query: str) -> str:
    terms = [term.replace('"', "") for term in query.split() if term.strip()]
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms[:12])


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n\n[PDF page {index}]\n{text}")
    return "\n".join(pages).strip()
