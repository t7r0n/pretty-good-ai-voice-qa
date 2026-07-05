---
title: Current Status
updated: 2026-06-28
---

# Current Status

This workspace now uses a local-only Python memory package. State belongs under `.codex_local_memory/`; project notes belong under `docs/wiki/`.

The Pretty Good AI free/local harness is available as `uv run voiceqa`. Current no-paid-call capabilities include scenario listing, target-number guardrail validation, local simulated calls, transcript/event/metadata artifacts, bug report drafts, and Groq transcription for existing audio files.

Run:

```bash
uv run pg-memory health
uv run pg-memory search "query"
uv run pg-memory context "query"
```
