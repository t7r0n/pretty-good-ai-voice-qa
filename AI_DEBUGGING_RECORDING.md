# AI-Debugging Screen Recording Script

Target length: 5 minutes.

The challenge asks for a separate 5-minute screen recording showing how AI was used to debug and fix code. Use this script to make the recording concise and credible.

## 0:00-0:30 - Context

Show the repo and explain:

> I used Codex to build and debug a real voice QA harness. The key debugging loop was not cosmetic: Twilio trial restrictions, signed webhook handling, Twilio Stream URL constraints, Realtime event shape, and recording/transcription all had to be fixed and verified.

## 0:30-1:20 - Real Failure

Show a concrete example from the work:

- Twilio initially rejected the live call because the account was trial-restricted.
- After upgrade, `.env` used `twilio_number`, which the code did not recognize.
- The fix added `twilio_number` as an accepted alias and reran `voiceqa env-check`.

Files to show:

- [src/voice_qa/config.py](src/voice_qa/config.py)
- [.env.example](.env.example)

## 1:20-2:20 - Security/Correctness Debugging

Explain that subagent review found issues:

- public webhook authentication
- query-controlled mode override
- Twilio `<Stream>` URL query parameters
- incomplete OpenAI bridge

Show final code:

- [src/voice_qa/call_server.py](src/voice_qa/call_server.py)
- [src/voice_qa/twiml.py](src/voice_qa/twiml.py)
- [src/voice_qa/realtime.py](src/voice_qa/realtime.py)

## 2:20-3:20 - Verification

Run or show:

```bash
uv run pytest -q
uv run voiceqa env-check
```

Then show the campaign validation:

- 20 complete live call sets across primary and supplemental evidence
- 20 recordings
- 20 transcripts
- 20 event logs
- no broken report links

## 3:20-4:20 - Evidence Quality

Show [artifacts/campaign_20260705/CALL_INDEX.md](artifacts/campaign_20260705/CALL_INDEX.md) and [artifacts/campaign_20260705/BUG_REPORT.md](artifacts/campaign_20260705/BUG_REPORT.md).

Explain how weak findings were filtered out:

- urgent symptoms was a pass, not a bug
- weekend closed was a pass, not a bug
- final bug report uses only defensible issues
- supplemental 180-second reruns were added after transcript tails exposed abrupt 120-second endings

## 4:20-5:00 - Final State

Show [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).

Close with:

> The AI-assisted loop was: build, run real calls, inspect evidence, have agents review risks, patch, rerun tests, and package only the strongest findings.
