# Final Submission Packet

Use this page when filling out the Pretty Good AI submission form.

Submission form: [Pretty Good AI - AI Engineer Submission](https://forms.gle/sdnbrJX2XbgZeQaY6)

Form-answer sheet: [FORM_ANSWERS.md](FORM_ANSWERS.md)

## Form Fields

- GitHub repository: [https://github.com/t7r0n/pretty-good-ai-voice-qa](https://github.com/t7r0n/pretty-good-ai-voice-qa)
- Loom walkthrough link: add after recording.
- AI-debugging screen recording link: add after recording.
- One caller phone number used for testing: use the Twilio caller number from local `.env`, in E.164 format. Do not paste any other number.

## Reviewer Entry Points

- Reviewer brief: [REVIEWER_BRIEF.md](REVIEWER_BRIEF.md)
- Voice quality first-listening guide: [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md)
- Primary call index: [CALL_INDEX.md](CALL_INDEX.md)
- Curated bug report: [BUG_REPORT.md](BUG_REPORT.md)
- Evidence manifest: [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Requirement audit: [REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md)
- Validation report: [artifacts/campaign_20260705/VALIDATION_REPORT.md](artifacts/campaign_20260705/VALIDATION_REPORT.md)

## Video Recording Order

1. Record the Loom walkthrough using [LOOM.md](LOOM.md).
2. Record the AI-debugging screen capture using [AI_DEBUGGING_RECORDING.md](AI_DEBUGGING_RECORDING.md).
3. Use [RECORDING_RUNBOOK.md](RECORDING_RUNBOOK.md) as the exact shot list and secret-safety checklist.
4. Add both public video links:

```bash
uv run python scripts/apply_video_links.py \
  --loom "$LOOM_URL" \
  --debug "$DEBUG_RECORDING_URL"
```

5. Run `uv run voiceqa evidence-manifest`.
6. Run `uv run voiceqa validate-submission`.
7. Commit and push the link update.

## Final Local Verification

```bash
uv run pytest -q
uv run voiceqa evidence-manifest
uv run voiceqa validate-submission
uv build --out-dir artifacts/build_dist
git status --short
```
