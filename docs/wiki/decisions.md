---
title: Decisions
updated: 2026-06-28
---

# Decisions

- Use `uv` and the local `.venv/` only.
- Do not install global MCPs, npm packages, Python tools, or Codex config for this memory system.
- Prefer local SQLite with WAL, FTS5, optional vector embeddings, graph/provenance tables, and explicit backups.
- Keep upstream memory projects as design references unless a future task explicitly opts into their heavier runtimes.
- For the Pretty Good AI challenge, first build all free/local pieces: scenario DSL, deterministic simulator, artifact generator, bug report drafts, target-number guardrail, and Groq transcription adapter. Defer real calls until Twilio/OpenAI credentials and paid-call approval exist.
