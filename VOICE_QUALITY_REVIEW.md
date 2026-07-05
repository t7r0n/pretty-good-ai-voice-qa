# Voice Quality Review Guide

The challenge states that lucid voice interaction is evaluated before code review. Start here before reading the implementation.

## Recommended First 10 Calls

These calls give reviewers a strong mix of natural conversation, positive controls, and bug evidence. The `campaign_20260705_clean` calls are supplemental reruns made with a 180-second cap after the initial 120-second campaign exposed some abrupt endings.

| # | Scenario | Why Listen | Evidence |
|---:|---|---|---|
| 1 | Urgent symptoms | Natural safety escalation; the shorter call is correct because the agent directs the patient to urgent help. | [recording](artifacts/campaign_20260705/recordings/CA24afb2b30adb28ae4ca250be7754b65a_REa1d5d6e9a948e4bc314ffc974897eb56.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA24afb2b30adb28ae4ca250be7754b65a_urgent_symptoms.md) |
| 2 | Weekend closed rerun | Clean 147-second scheduling conversation with a patient closing statement. | [recording](artifacts/campaign_20260705_clean/recordings/CAc1c7a8c4472f628c2a8667658788a08d_RE7b365e35f48795bbc2f2a70978c1540a.mp3), [transcript](artifacts/campaign_20260705_clean/transcripts_md/CAc1c7a8c4472f628c2a8667658788a08d_weekend_closed.md) |
| 3 | Human handoff | Caller repeatedly asks for staff and exposes the dead-end transfer issue. | [recording](artifacts/campaign_20260705/recordings/CA26bd243d39cd2ba91f449f19f2a54e11_REa478831b4f400eef18fc948bea62c901.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA26bd243d39cd2ba91f449f19f2a54e11_human_handoff.md) |
| 4 | Records request | Realistic records-release workflow; shows wrong phone fragment and missing process answer. | [recording](artifacts/campaign_20260705/recordings/CA75d9bf363e09fbcfd6dfc7e30fc264a5_RE27e62980357b04486c34152de38505d8.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA75d9bf363e09fbcfd6dfc7e30fc264a5_records_request.md) |
| 5 | Controlled refill rerun | Longer clean medication-boundary conversation ending at transfer. | [recording](artifacts/campaign_20260705_clean/recordings/CA6fbe94750f6d2a19c66630f6d85028fd_RE0ed58662bf4a1652f741d959e7e88750.mp3), [transcript](artifacts/campaign_20260705_clean/transcripts_md/CA6fbe94750f6d2a19c66630f6d85028fd_controlled_refill.md) |
| 6 | Wrong DOB rerun | Longer identity-correction flow that reaches handoff/test-line ending. | [recording](artifacts/campaign_20260705_clean/recordings/CA9744a5e338b12113d4ea5dd24f70a362_RE019477a0f4822fd3e8c214cc684b36a2.mp3), [transcript](artifacts/campaign_20260705_clean/transcripts_md/CA9744a5e338b12113d4ea5dd24f70a362_wrong_dob_correction.md) |
| 7 | Barge-in rerun | Tests interruption/repair behavior and ends cleanly after the transfer target. | [recording](artifacts/campaign_20260705_clean/recordings/CAe9b7a5e99653da2027fd3245b91d8188_RE324c393bca23767b8f24fced94aa808f.mp3), [transcript](artifacts/campaign_20260705_clean/transcripts_md/CAe9b7a5e99653da2027fd3245b91d8188_barge_in.md) |
| 8 | Location confusion | Patient repeatedly steers toward downtown-only scheduling; useful medium-severity bug evidence. | [recording](artifacts/campaign_20260705/recordings/CAe9dd8dccd9a139266681cb88f88e0768_REe67e16d15cb531bc4597d19ab6a4fd88.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CAe9dd8dccd9a139266681cb88f88e0768_location_confusion.md) |
| 9 | Cancel then reconsider | Tests appointment-state precision after a cancellation retraction. | [recording](artifacts/campaign_20260705/recordings/CA6643f1887c8248a7c33ced7e34d662a8_RE15b6ec3db1c1c89285872718f1b600d4.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA6643f1887c8248a7c33ced7e34d662a8_cancel_reconsider.md) |
| 10 | Contradictory date | Tests repair around conflicting appointment dates and a handoff. | [recording](artifacts/campaign_20260705/recordings/CA37371c933fce3fce6b2add6585436a90_RE179cb65e83e28d05d9e30955ec65b277.mp3), [transcript](artifacts/campaign_20260705/transcripts_md/CA37371c933fce3fce6b2add6585436a90_contradictory_date.md) |

## Campaign Shape

- Primary campaign: 14 real outbound calls with recordings, transcripts, and event logs.
- Supplemental cleanup campaign: 6 additional real outbound calls with recordings, transcripts, and event logs.
- Total live evidence: 20 real calls.
- All calls used the single allowed assessment target, `+18054398008`.
- The caller personas use natural turn-taking with active steering toward scenario objectives instead of one-question benchmark prompts.
- Two supplemental long-limit calls, `unclear_request` and `after_hours`, still reached the 180-second cap and are retained as stress evidence rather than first-listening recommendations.
