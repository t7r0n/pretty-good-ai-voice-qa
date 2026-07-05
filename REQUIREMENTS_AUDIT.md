# Requirements Audit

Source: `Pretty Good AI - AI Engineering Challenge (Final).pdf`

Status: public artifact package is ready for video recording and final form submission. The remaining external steps are adding the Loom link, adding the AI-debugging recording link, and submitting the official form with the single caller number used.

## Deliverables

| Requirement | Current evidence | Status |
|---|---|---|
| Working Python voice bot | `src/voice_qa/`, `pyproject.toml`, `uv.lock` | Ready |
| README with setup/run instructions | `README.md` | Ready |
| Architecture doc, 1-2 paragraph explanation | `ARCHITECTURE.md` | Ready |
| Minimum 10 call evidence sets | 20 real call evidence sets across `artifacts/campaign_20260705/CALL_INDEX.md` and `artifacts/campaign_20260705_clean/CALL_INDEX.md`; first-listening order in `VOICE_QUALITY_REVIEW.md` | Ready |
| Audio recordings in mp3 or ogg | 20 MP3s across the primary and supplemental campaign directories | Ready |
| Transcripts with both sides | 20 Groq JSON transcripts and 20 timestamped markdown transcripts | Ready |
| Bug report | `artifacts/campaign_20260705/BUG_REPORT.md` and top-level `BUG_REPORT.md` | Ready |
| Loom walkthrough, max 5 minutes | `LOOM.md` script exists; link still needs to be recorded and added | External step |
| AI-debugging screen recording, 5 minutes | `AI_DEBUGGING_RECORDING.md` script exists; link still needs to be recorded and added | External step |
| Public GitHub repository | [https://github.com/t7r0n/pretty-good-ai-voice-qa](https://github.com/t7r0n/pretty-good-ai-voice-qa) | Ready |
| Single caller phone number in E.164 format | Calls were made from one configured Twilio caller number; submit that exact number in the form | External step |
| Do not commit secrets | `.env` is ignored; `.env.example` documents required variables | Ready |

Submission form: [Pretty Good AI - AI Engineer Submission](https://forms.gle/sdnbrJX2XbgZeQaY6)

## Evaluation Criteria Mapping

| Criterion | Evidence |
|---|---|
| Lucid voice conversation | 20 MP3 recordings, with recommended first-10 listening order in `VOICE_QUALITY_REVIEW.md` |
| Useful bugs, not nitpicks | 5 curated findings in `BUG_REPORT.md`; positive controls are intentionally not filed as bugs |
| Working code that makes real calls | Twilio dialer, FastAPI media server, OpenAI Realtime bridge, Groq transcription, and event logs |
| Clear thinking | `ARCHITECTURE.md`, `LOOM.md`, `AI_DEBUGGING_RECORDING.md`, and this audit |
| Evidence of iteration | `AI_DEBUGGING_RECORDING.md`, `SUBMISSION_CHECKLIST.md`, `VALIDATION_REPORT.md`, and `artifacts/campaign_20260705_clean/CALL_INDEX.md` show trial restrictions, 60-second cutoff, env alias fixes, 120-second cutoff cleanup reruns, and final validation |
| Clean enough code | `uv run pytest -q`, `uv run voiceqa validate-submission`, and `uv build --out-dir artifacts/build_dist` pass |

## Final Local Gate

Run before publishing:

```bash
uv run pytest -q
uv run voiceqa evidence-manifest
uv run voiceqa validate-submission
uv run python -m compileall -q src tests
uv build --out-dir artifacts/build_dist
uv run pg-memory verify
```
