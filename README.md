# Pretty Good AI Voice QA Harness

This repository is a patient-simulation QA harness for the Pretty Good AI engineering challenge. It makes real guarded calls to the assessment line, simulates realistic patient scenarios through OpenAI Realtime, records call evidence with Twilio, transcribes recordings with Groq, and packages evidence into a reviewer-friendly call index, bug report, and integrity manifest.

Start here:

- Public GitHub repository: [t7r0n/pretty-good-ai-voice-qa](https://github.com/t7r0n/pretty-good-ai-voice-qa)
- Reviewer brief: [REVIEWER_BRIEF.md](REVIEWER_BRIEF.md)
- Final submission packet: [FINAL_SUBMISSION_PACKET.md](FINAL_SUBMISSION_PACKET.md)
- Recording runbook: [RECORDING_RUNBOOK.md](RECORDING_RUNBOOK.md)
- [CALL_INDEX.md](CALL_INDEX.md): reviewer entry point for all campaign calls.
- [BUG_REPORT.md](BUG_REPORT.md): curated findings with evidence links.
- [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md): hashes, durations, transcript stats, and event counts for all call evidence.
- [ARCHITECTURE.md](ARCHITECTURE.md): short architecture explanation.
- [REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md): PDF requirement-to-evidence map.
- [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md): recommended listening order for the top judging criterion.
- [LOOM.md](LOOM.md): 5-minute walkthrough script.
- [AI_DEBUGGING_RECORDING.md](AI_DEBUGGING_RECORDING.md): 5-minute AI-debugging recording script.
- [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md): final submission checklist.

## Challenge Evidence

The canonical evidence set is under `artifacts/campaign_20260705/`:

- 14 completed real outbound calls to `+18054398008`.
- 14 Twilio MP3 recordings with both sides of each call.
- 14 Groq transcript JSON files.
- 14 timestamped transcript markdown files.
- 14 Twilio/OpenAI event logs.
- 5 curated bug findings.

Supplemental voice-quality reruns are under `artifacts/campaign_20260705_clean/`:

- 6 additional real outbound calls using a 180-second cap.
- 6 Twilio MP3 recordings, 6 Groq JSON transcripts, 6 timestamped markdown transcripts, and 6 event logs.
- The first four reruns are cleaner replacements for calls that were useful but had abrupt 120-second endings in the primary campaign.

Validated entry points:

- [artifacts/campaign_20260705/CALL_INDEX.md](artifacts/campaign_20260705/CALL_INDEX.md)
- [artifacts/campaign_20260705/BUG_REPORT.md](artifacts/campaign_20260705/BUG_REPORT.md)
- [artifacts/campaign_20260705_clean/CALL_INDEX.md](artifacts/campaign_20260705_clean/CALL_INDEX.md)
- [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md)

## Quick Start

```bash
export UV_CACHE_DIR="$PWD/.codex_local_memory/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.codex_local_memory/python"
export XDG_CACHE_HOME="$PWD/.codex_local_memory/cache"
export HF_HOME="$PWD/.codex_local_memory/cache/huggingface"

uv sync
uv run pytest
uv run voiceqa evidence-manifest
uv run voiceqa validate-submission
uv run voiceqa env-check
uv run voiceqa scenarios
```

The dialer refuses to call any target except `+18054398008`.

## Environment

Copy `.env.example` to `.env` and fill values locally. Do not commit `.env`.

Required for live calls and evidence:

- `OPENAI_API_KEY` or `openai_api_key`
- `GROQ_API_KEY` or `groq_api_key`
- `TWILIO_ACCOUNT_SID` or `twilio_account_sid` / `twilio_SID`
- `TWILIO_AUTH_TOKEN` or `twilio_auth_token` / `twilio_ClientSecret`
- `TWILIO_FROM_NUMBER` or `twilio_from_number` / `twilio_number`

## Live Run Commands

Expose the local server through an HTTPS/WSS tunnel, then run:

```bash
uv run voiceqa server \
  --host 127.0.0.1 \
  --port 8765 \
  --public-base-url https://your-public-tunnel.example.com \
  --mode openai \
  --output artifacts/new_campaign/events

uv run voiceqa dial \
  --public-base-url https://your-public-tunnel.example.com \
  --scenario baseline_scheduling \
  --time-limit-seconds 120 \
  --record-call \
  --yes-i-approve-real-call

uv run voiceqa recording <CALL_SID> --output artifacts/new_campaign/recordings
uv run voiceqa transcribe artifacts/new_campaign/recordings/<recording>.mp3 \
  --output artifacts/new_campaign/transcripts/<CALL_SID>.json
```

Do not use `--allow-unsigned-webhooks` for public live calls. It is for local mock testing only.

## Local Memory

This workspace has a local-only memory system for Codex-style sessions. It does not edit global Codex config, global MCP config, or sibling projects.

## Setup

```bash
export UV_CACHE_DIR="$PWD/.codex_local_memory/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.codex_local_memory/python"
export XDG_CACHE_HOME="$PWD/.codex_local_memory/cache"
export HF_HOME="$PWD/.codex_local_memory/cache/huggingface"

uv sync
uv run pg-memory init
uv run pg-memory ingest .
uv run pg-memory verify
```

All state lives in `.codex_local_memory/`. The Python environment lives in `.venv/`.

## Daily Use

```bash
export UV_CACHE_DIR="$PWD/.codex_local_memory/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.codex_local_memory/python"
export XDG_CACHE_HOME="$PWD/.codex_local_memory/cache"
export HF_HOME="$PWD/.codex_local_memory/cache/huggingface"

uv run pg-memory remember "Decision: use local SQLite memory only." --title "Memory decision"
uv run pg-memory search "SQLite memory"
uv run pg-memory context "what did we decide about memory?"
uv run pg-memory backup
```

## Free Local Challenge Harness

The `voiceqa` CLI builds everything possible before paid telephony or Realtime voice:

```bash
export UV_CACHE_DIR="$PWD/.codex_local_memory/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.codex_local_memory/python"
export XDG_CACHE_HOME="$PWD/.codex_local_memory/cache"
export HF_HOME="$PWD/.codex_local_memory/cache/huggingface"

uv run voiceqa env-check
uv run voiceqa guard "+1 (805) 439-8008"
uv run voiceqa scenarios
uv run voiceqa simulate --all --output artifacts/local_sim
```

This generates local simulated transcripts, event logs, metadata, per-call bug drafts, `CALL_INDEX.md`, and `BUG_REPORT.md`. It does not place real calls.

Groq transcription is available for local audio files once recordings exist:

```bash
uv run voiceqa transcribe path/to/audio.mp3 --output artifacts/transcript.json
```

## Call Stack Dry Run

The project now includes the guarded live-call path: Twilio TwiML generation, a Twilio Media Streams server, audio conversion between Twilio mu-law/8 kHz and OpenAI PCM16/24 kHz, and a Realtime patient prompt builder. The safe default is mock mode:

```bash
uv run voiceqa twiml --public-base-url https://your-public-tunnel.example.com --scenario weekend_closed --mode mock
uv run voiceqa server --host 127.0.0.1 --port 8765 --public-base-url https://your-public-tunnel.example.com --mode mock --allow-unsigned-webhooks
uv run voiceqa dial --public-base-url https://your-public-tunnel.example.com --scenario weekend_closed
```

The `dial` command is a dry run unless `--yes-i-approve-real-call` is passed. It refuses every target except `+18054398008`.

For a real call, expose the local server over HTTPS/WSS with a tunnel, switch the server to `--mode openai`, and do not use `--allow-unsigned-webhooks`. The server validates Twilio request signatures on POST callbacks and puts signed stream tokens into Twilio custom parameters. The `<Stream>` URL intentionally has no query string because Twilio requires custom values to be passed as nested `<Parameter>` entries.

```bash
uv run voiceqa server --host 127.0.0.1 --port 8765 --public-base-url https://your-public-tunnel.example.com --mode openai
uv run voiceqa dial --public-base-url https://your-public-tunnel.example.com --scenario weekend_closed --yes-i-approve-real-call
```

Do not place a real assessment call until the mock server, artifacts, and credentials check pass.

## Submission Artifacts

The winning-run artifact set is under `artifacts/campaign_20260705/`:

- [CALL_INDEX.md](artifacts/campaign_20260705/CALL_INDEX.md): recordings, transcripts, event logs, and notes for 14 real calls.
- [BUG_REPORT.md](artifacts/campaign_20260705/BUG_REPORT.md): curated high-signal bugs with timestamped evidence.
- `recordings/`: Twilio MP3 recordings.
- `transcripts/`: Groq transcript JSON.
- `transcripts_md/`: timestamped transcript markdown.
- `events/`: Twilio/OpenAI event logs.

Top-level [CALL_INDEX.md](CALL_INDEX.md), [BUG_REPORT.md](BUG_REPORT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [LOOM.md](LOOM.md) are the reviewer entry points.

Supplemental cleaner reruns for voice-quality review are indexed at [artifacts/campaign_20260705_clean/CALL_INDEX.md](artifacts/campaign_20260705_clean/CALL_INDEX.md).

Run the final local submission gate with:

```bash
uv run voiceqa validate-submission
```

## Preflight

Before a long session or submission packaging:

```bash
uv run pytest
uv run voiceqa simulate --all --output artifacts/local_sim
uv run voiceqa twiml --public-base-url https://example.com --scenario weekend_closed --mode mock
uv run pg-memory verify
uv build --out-dir /tmp/pretty_good_build
```

Vector rows are stored locally with `sqlite-vec`. The default embedding backend is `local-hash-v1`, a deterministic local vectorizer that needs no model download. If you switch `embedding_model` to a `fastembed` model later, make runtime vector search opt-in until the model is cached:

```bash
PG_MEMORY_VECTOR_SEARCH=1 uv run pg-memory search "query"
```

Optional local MCP server:

```bash
uv run pg-memory-mcp
```

An example MCP stanza is generated at `.codex_local_memory/mcp.local.example.json`. Use it only for this workspace.

## Upstream Memory Review

- [LLM-wiki](https://github.com/Ss1024sS/LLM-wiki): useful for compile-first markdown writeback and `AGENTS.md` workflow.
- [MemPalace](https://github.com/MemPalace/mempalace): useful for local-first verbatim storage and hybrid retrieval ideas.
- [Hermes Agent memory](https://github.com/NousResearch/hermes-agent): useful for bounded curated memory plus on-demand session search.
- [knowledge_graph](https://github.com/rahulnyk/knowledge_graph): useful for concept co-occurrence graph retrieval.
- [Graphiti](https://github.com/getzep/graphiti): useful for temporal facts, provenance, and invalidation, but not used directly because it normally expects graph services and LLM-backed extraction.
- [EM-LLM](https://github.com/em-llm/EM-LLM-model): useful for event segmentation and contiguous episodic recall ideas, not practical as a workspace dependency.
- [MemoRAG](https://github.com/qhjqhj00/MemoRAG): useful for cached memory-model retrieval concepts, but too GPU/model-heavy for a default local Codex workspace.
- [agentmemory](https://github.com/rohitg00/agentmemory): useful for MCP/hook ergonomics and lifecycle ideas, but global npm/server wiring would violate this workspace-only requirement.

This implementation borrows the durable ideas, not the global installers.
