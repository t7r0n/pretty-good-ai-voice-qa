# Recording Runbook

Use this to record the two required videos without exposing secrets or wandering through the repo.

Run every command from this repository root with the workspace-local uv environment required by `AGENTS.md`:

```bash
export UV_CACHE_DIR=$PWD/.codex_local_memory/uv-cache
export UV_PYTHON_INSTALL_DIR=$PWD/.codex_local_memory/python
export XDG_CACHE_HOME=$PWD/.codex_local_memory/cache
export HF_HOME=$PWD/.codex_local_memory/cache/huggingface
```

## Before Recording

```bash
uv run pytest -q
uv run voiceqa evidence-manifest
uv run voiceqa validate-submission
uv run voiceqa final-check
```

Expected before video links are applied: `final-check` should fail only because the Loom and AI-debugging URLs are missing and their placeholder text is still present. Do not show `.env` or print secret values.

Open these files in tabs before starting:

- `README.md`
- `FORM_ANSWERS.md`
- `VOICE_QUALITY_REVIEW.md`
- `BUG_REPORT.md`
- `ARCHITECTURE.md`
- `FINAL_SUBMISSION_PACKET.md`
- `SUBMISSION_CHECKLIST.md`

## Loom Walkthrough

Target: 5 minutes max.

1. 0:00-0:30: show `README.md` and state that this is a real patient-simulation voice QA harness.
2. 0:30-1:15: show `ARCHITECTURE.md`; describe Twilio, FastAPI Media Streams, OpenAI Realtime, Twilio recording, and Groq transcription.
3. 1:15-2:10: show `VOICE_QUALITY_REVIEW.md`; play a short segment from `urgent_symptoms` or the supplemental `weekend_closed` rerun.
4. 2:10-3:30: show `BUG_REPORT.md`; focus on BUG-001 or BUG-002 with the linked recording and transcript.
5. 3:30-4:20: show `artifacts/campaign_20260705_clean/CALL_INDEX.md`; explain that six 180-second cleanup reruns were added after reviewing abrupt transcript tails.
6. 4:20-5:00: show `FINAL_SUBMISSION_PACKET.md`; close with the public GitHub repo and validation commands.

## AI-Debugging Screen Recording

Target: 5 minutes.

1. 0:00-0:30: show the public repo and explain the AI-assisted loop: build, run real calls, inspect evidence, patch, retest.
2. 0:30-1:20: show `src/voice_qa/config.py` and `.env.example`; explain fixing environment aliases such as `twilio_number` without printing `.env`.
3. 1:20-2:20: show `src/voice_qa/call_server.py`, `src/voice_qa/twiml.py`, and `src/voice_qa/realtime.py`; explain signed webhooks, signed stream tokens, no query-controlled mode override, and Realtime audio bridging.
4. 2:20-3:20: run or show `uv run pytest -q`, `uv run voiceqa evidence-manifest`, and `uv run voiceqa validate-submission`.
5. 3:20-4:15: show `src/voice_qa/submission.py`; explain the stronger evidence validator and `voiceqa final-check`.
6. 4:15-5:00: show `SUBMISSION_CHECKLIST.md`; explain remaining form submission and video-link application.

## After Recording

```bash
uv run python scripts/apply_video_links.py \
  --loom "$LOOM_URL" \
  --debug "$DEBUG_RECORDING_URL"

uv run voiceqa evidence-manifest
uv run voiceqa final-check
git add README.md FINAL_SUBMISSION_PACKET.md FORM_ANSWERS.md SUBMISSION_CHECKLIST.md EVIDENCE_MANIFEST.md
git commit -m "Add final video links"
git push
```

The automated test `test_apply_video_links_makes_final_readiness_pass` covers this link-application path on a complete fixture.

Then submit the form at [Pretty Good AI - AI Engineer Submission](https://forms.gle/sdnbrJX2XbgZeQaY6) using [FORM_ANSWERS.md](FORM_ANSWERS.md) and the single Twilio caller number from local `.env` in E.164 format.
