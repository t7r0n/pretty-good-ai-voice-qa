# Reviewer Brief

Use this page as the shortest path through the submission.

## What Was Built

This is a guarded live voice QA harness for the Pretty Good AI challenge. It places controlled outbound calls to the allowed assessment number, drives realistic patient personas through OpenAI Realtime, records both sides with Twilio, transcribes the recordings with Groq, and packages each call with timestamped transcripts and event logs.

## Evidence Package

- 20 real outbound call evidence sets: 14 primary calls plus 6 supplemental cleanup reruns.
- 20 Twilio MP3 recordings, 20 Groq JSON transcripts, 20 timestamped markdown transcripts, and 20 Twilio/OpenAI event logs.
- 2,403.7 seconds of recordings and 122,463 Twilio media frames, summarized in [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md).
- Supplemental calls were added after the first 120-second campaign exposed useful but abrupt endings. Two long-limit supplemental calls still hit the 180-second cap and are retained as stress evidence.

## Start Here

1. Open [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md) and listen to the first 10 recommended calls.
2. Open [BUG_REPORT.md](BUG_REPORT.md) for the curated findings.
3. Open [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md) to verify hashes, durations, transcript sizes, and event counts.
4. Open [ARCHITECTURE.md](ARCHITECTURE.md) for the implementation shape.

## Strongest Findings

| Priority | Finding | Evidence |
|---:|---|---|
| 1 | Human handoff is delayed and resolves to a dead-end transfer. | [recording](artifacts/campaign_20260705/recordings/CA26bd243d39cd2ba91f449f19f2a54e11_REa478831b4f400eef18fc948bea62c901.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA26bd243d39cd2ba91f449f19f2a54e11_human_handoff.md) |
| 2 | Medical-records request reads an incorrect phone fragment and does not explain the release process. | [recording](artifacts/campaign_20260705/recordings/CA75d9bf363e09fbcfd6dfc7e30fc264a5_RE27e62980357b04486c34152de38505d8.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA75d9bf363e09fbcfd6dfc7e30fc264a5_records_request.md) |
| 3 | Location-specific appointment request is never confirmed before handoff. | [recording](artifacts/campaign_20260705/recordings/CAe9dd8dccd9a139266681cb88f88e0768_REe67e16d15cb531bc4597d19ab6a4fd88.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CAe9dd8dccd9a139266681cb88f88e0768_location_confusion.md) |
| 4 | Cancellation retraction is not explicitly confirmed before support handoff. | [recording](artifacts/campaign_20260705/recordings/CA6643f1887c8248a7c33ced7e34d662a8_RE15b6ec3db1c1c89285872718f1b600d4.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA6643f1887c8248a7c33ced7e34d662a8_cancel_reconsider.md) |
| 5 | Baseline scheduling leaks demo/internal phrasing and contradicts earlier identity handling. | [recording](artifacts/campaign_20260705/recordings/CAec5971f74b3e3d3b43337414834b71d8_RE9a218ee27c6e7cdb04bf46d34c89db67.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CAec5971f74b3e3d3b43337414834b71d8_baseline_scheduling.md) |

## Verification Commands

```bash
uv run pytest -q
uv run voiceqa evidence-manifest
uv run voiceqa validate-submission
```

`voiceqa final-check` intentionally stays red until the public Loom and AI-debugging video URLs are added to [FINAL_SUBMISSION_PACKET.md](FINAL_SUBMISSION_PACKET.md).
