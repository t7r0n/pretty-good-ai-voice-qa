# Loom Walkthrough Script

Target length: 5 minutes.

## 0:00-0:30 - Framing

I built a patient-simulation QA harness, not just a phone script. The goal is to stress-test the AI agent with realistic patient calls and produce reviewer-friendly evidence: recordings, transcripts, event logs, and a focused bug report.

## 0:30-1:20 - Architecture

Show `ARCHITECTURE.md`. Explain:

- Twilio places the outbound call to the single allowed number.
- FastAPI serves signed Twilio webhooks and a bidirectional Media Stream.
- OpenAI Realtime acts as the live patient.
- Twilio records the full call.
- Groq transcribes the final MP3.
- The artifact generator produces the call index and bug report.

## 1:20-2:20 - Natural Conversation Evidence

Open `CALL_INDEX.md`, then play 20-30 seconds from a clean control call:

- `urgent_symptoms`: shows emergency escalation working correctly.
- `weekend_closed`: shows the agent correctly refusing Sunday scheduling.

Use this to show that the system can hold coherent voice conversations and that not every call is forced into a bug. Also show [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md), which points reviewers to the cleanest first 10 calls across the primary and supplemental campaigns.

## 2:20-3:40 - Strongest Bug

Open the canonical bug report and show BUG-001 or BUG-002.

Recommended:

- BUG-001: human handoff request delayed and dead-ended.
- BUG-002: records request reads wrong phone fragment and fails to explain records-release process.

Play the timestamped recording snippet and show the matching transcript.

## 3:40-4:30 - Iteration And Quality

Mention the initial operator check found a 60-second cutoff issue, so the primary campaign used 120-second limits. After reviewing transcript tails, several otherwise useful calls still ended abruptly, so a supplemental cleanup batch reran six scenarios with a 180-second cap and added cleaner reviewer evidence.

## 4:30-5:00 - How To Run

Show:

```bash
uv sync
uv run pytest
uv run voiceqa scenarios
uv run voiceqa dial --public-base-url <https-tunnel> --scenario baseline_scheduling --record-call --yes-i-approve-real-call
uv run voiceqa recording <CALL_SID>
uv run voiceqa transcribe artifacts/recordings/<file>.mp3
```

Close by emphasizing that the code enforces the allowed target number and keeps artifacts local.
