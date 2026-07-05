# Validation Report

Date: 2026-07-05

## Automated Gates

- `uv run pytest -q`: passed, 48 tests.
- `uv run voiceqa validate-submission`: passed, including supplemental cleanup evidence.
- `uv run python -m compileall -q src tests`: passed.
- `uv build --out-dir artifacts/build_dist`: passed.
- `uv run pg-memory verify`: passed with a fresh SQLite backup.

## Evidence Inventory

- Recordings: 14 MP3 files.
- Transcript JSON files: 14.
- Timestamped transcript markdown files: 14.
- Live call event logs: 14.
- Complete call sets with recording, transcript JSON, transcript markdown, and event log: 14.
- Supplemental cleanup recordings: 6 MP3 files.
- Supplemental cleanup transcript JSON files: 6.
- Supplemental cleanup timestamped transcript markdown files: 6.
- Supplemental cleanup live call event logs: 6.
- Total complete live call sets across primary and supplemental evidence: 20.

## Readiness Notes

- The final evidence package is under `artifacts/campaign_20260705/`.
- The strongest curated findings are in `BUG_REPORT.md`.
- The call-by-call evidence index is in `CALL_INDEX.md`.
- Supplemental cleaner voice-quality reruns are indexed in `artifacts/campaign_20260705_clean/CALL_INDEX.md`.
- The remaining non-code submission steps are recording the Loom walkthrough, recording the AI-debugging screen capture, publishing the repository, and submitting the official challenge form.
