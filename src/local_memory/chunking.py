from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    start_char: int
    end_char: int
    sha256: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str, chunk_chars: int = 1800, overlap: int = 220) -> list[Chunk]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) <= chunk_chars:
        body = normalized.strip()
        return [Chunk(0, body, 0, len(normalized), sha256_text(body))] if body else []

    chunks: list[Chunk] = []
    start = 0
    ordinal = 0
    while start < len(normalized):
        hard_end = min(start + chunk_chars, len(normalized))
        window = normalized[start:hard_end]
        split_at = _best_split(window)
        end = start + split_at if split_at else hard_end
        body = normalized[start:end].strip()
        if body:
            chunks.append(Chunk(ordinal, body, start, end, sha256_text(body)))
            ordinal += 1
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _best_split(window: str) -> int | None:
    if len(window) < 400:
        return len(window)
    candidates = [m.end() for m in re.finditer(r"\n\n|[.!?]\s+", window)]
    candidates = [idx for idx in candidates if idx >= len(window) * 0.55]
    return max(candidates) if candidates else None


ENTITY_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9_/-]{2,})(?:\s+[A-Z][A-Za-z0-9_/-]{2,}){0,3}\b|"
    r"`([A-Za-z_][A-Za-z0-9_./:-]{2,})`|"
    r"\b([a-z]+_[a-z0-9_]{2,})\b"
)


def extract_entities(text: str, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    entities: list[str] = []
    for match in ENTITY_RE.finditer(text):
        value = next((group for group in match.groups() if group), match.group(0))
        value = value.strip("` ").strip()
        norm = normalize_entity(value)
        if len(norm) < 3 or norm in seen:
            continue
        seen.add(norm)
        entities.append(value)
        if len(entities) >= limit:
            break
    return entities


def normalize_entity(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())
