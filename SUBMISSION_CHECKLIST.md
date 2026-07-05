# Submission Checklist

Status: ready for video recording and GitHub publication.

## Required Challenge Deliverables

- [x] Working Python code.
- [x] README with setup and run instructions.
- [x] `.env.example` documenting environment variables.
- [x] Architecture doc: [ARCHITECTURE.md](ARCHITECTURE.md).
- [x] Final submission packet: [FINAL_SUBMISSION_PACKET.md](FINAL_SUBMISSION_PACKET.md).
- [x] Recording runbook: [RECORDING_RUNBOOK.md](RECORDING_RUNBOOK.md).
- [x] PDF requirement audit: [REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md).
- [x] Voice quality review guide: [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md).
- [x] Minimum 10 real call evidence sets: 20 captured calls with MP3 recordings, Groq transcripts, timestamped markdown, and event logs across [artifacts/campaign_20260705/CALL_INDEX.md](artifacts/campaign_20260705/CALL_INDEX.md) and [artifacts/campaign_20260705_clean/CALL_INDEX.md](artifacts/campaign_20260705_clean/CALL_INDEX.md).
- [x] MP3 recordings: 20 files across the primary and supplemental campaign directories.
- [x] Transcripts: 20 JSON transcripts and 20 timestamped markdown transcripts.
- [x] Bug report: [BUG_REPORT.md](BUG_REPORT.md).
- [x] Single allowed assessment target: enforced in code as `+18054398008`.
- [x] Tests: `50 passed`.
- [x] Submission artifact validator: `uv run voiceqa validate-submission` passes.
- [x] Validation report: [artifacts/campaign_20260705/VALIDATION_REPORT.md](artifacts/campaign_20260705/VALIDATION_REPORT.md).
- [ ] Loom walkthrough link.
- [ ] 5-minute AI-debugging screen recording link.
- [x] Public GitHub repository link: [t7r0n/pretty-good-ai-voice-qa](https://github.com/t7r0n/pretty-good-ai-voice-qa).
- [ ] Submission form filled at [Pretty Good AI - AI Engineer Submission](https://forms.gle/sdnbrJX2XbgZeQaY6) with the one Twilio caller number used, in E.164 format.

## Before Publishing GitHub

- [x] Initialize local Git repository on branch `main`.
- [x] Confirm `.env` is ignored by Git.
- [x] Confirm `artifacts/campaign_20260705/` is tracked.
- [x] Confirm `artifacts/campaign_20260705_clean/` is tracked.
- [x] Confirm MP3 recordings open from GitHub.
- [x] Confirm markdown links in `CALL_INDEX.md` and `BUG_REPORT.md` work on GitHub.
- [x] Confirm top-level `README.md`, `FINAL_SUBMISSION_PACKET.md`, `ARCHITECTURE.md`, `REQUIREMENTS_AUDIT.md`, `VOICE_QUALITY_REVIEW.md`, `CALL_INDEX.md`, `BUG_REPORT.md`, `LOOM.md`, and this checklist are visible at repo root.

## Suggested Final Review Order

1. Open [CALL_INDEX.md](CALL_INDEX.md).
2. Open [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md) and play `urgent_symptoms` or `weekend_closed`.
3. Open [BUG_REPORT.md](BUG_REPORT.md).
4. Play BUG-001 and BUG-002 snippets from the linked recordings.
5. Verify `uv run pytest -q` and `uv run voiceqa validate-submission` still pass.
6. Record Loom walkthrough.
7. Record AI-debugging walkthrough.
8. Use [RECORDING_RUNBOOK.md](RECORDING_RUNBOOK.md) to keep both videos under 5 minutes and avoid showing `.env`.
9. Apply video links with `uv run python scripts/apply_video_links.py --loom "$LOOM_URL" --debug "$DEBUG_RECORDING_URL"`.
10. Commit, push, and submit the form.
