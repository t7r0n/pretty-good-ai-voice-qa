# Memory Design

## Goals

- Local-only: no global config, no shared daemon, no sibling workspace state.
- Verbatim retention: keep raw source chunks and checksums.
- Hybrid recall: FTS5 keyword search, optional local embeddings through `fastembed` + `sqlite-vec`, and graph-neighborhood expansion.
- Temporal provenance: every durable note is an episode; facts can be invalidated instead of overwritten.
- Recovery: WAL mode, integrity checks, idempotent hashes, and timestamped SQLite backups.

## Why Not Directly Install the Referenced Projects?

LLM-wiki is the right workflow layer, so this repo keeps `docs/wiki/` and mandatory writeback in `AGENTS.md`.

MemPalace and agentmemory are closer to complete agent memory products, but their quick starts favor global tools, shared servers, or cross-agent wiring. That conflicts with local-only isolation.

Graphiti is strong for temporal graphs, but it normally depends on graph backends and LLM-backed extraction. This repo implements the smallest reliable subset locally: episodes, entities, facts, validity windows, and provenance links.

EM-LLM and MemoRAG are research/model systems for long-context memory. Their useful lesson here is event segmentation plus cached retrieval. Pulling them in as runtime dependencies would add GPU/model weight and reduce operational reliability.

## Operating Rule

Memory is not automatic unless the agent writes to it. Important decisions should be written to both:

- `docs/wiki/` for compact current truth.
- `.codex_local_memory/memory.sqlite` through `uv run pg-memory remember ...` for searchable, timestamped recall.
