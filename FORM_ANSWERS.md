# Submission Form Answers

Use this page when filling out the official Pretty Good AI submission form. Do not paste secrets from `.env`.

Official form: [Pretty Good AI - AI Engineer Submission](https://forms.gle/sdnbrJX2XbgZeQaY6)

## Required Fields

- GitHub repository: [https://github.com/t7r0n/pretty-good-ai-voice-qa](https://github.com/t7r0n/pretty-good-ai-voice-qa)
- Loom walkthrough link: Pending Loom walkthrough URL.
- AI-debugging screen recording link: Pending AI-debugging screen recording URL.
- One caller phone number used for testing: use `TWILIO_FROM_NUMBER` from local `.env`, in E.164 format. Do not commit the value.

## Short Project Summary

Live voice QA harness for the Pretty Good AI challenge. It places guarded outbound calls to the allowed assessment line, drives realistic patient personas through OpenAI Realtime, records calls with Twilio, transcribes them with Groq, and packages evidence into call indexes, a bug report, timestamped transcripts, event logs, and an integrity manifest.

## Reviewer Path

1. Start with [REVIEWER_BRIEF.md](REVIEWER_BRIEF.md).
2. Listen to the first 10 calls in [VOICE_QUALITY_REVIEW.md](VOICE_QUALITY_REVIEW.md).
3. Read [BUG_REPORT.md](BUG_REPORT.md) for the strongest findings.
4. Verify evidence hashes and event counts in [EVIDENCE_MANIFEST.md](EVIDENCE_MANIFEST.md).
