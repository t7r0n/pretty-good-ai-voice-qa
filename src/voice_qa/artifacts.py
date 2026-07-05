from __future__ import annotations

import json
from pathlib import Path

from .models import ArtifactPaths, SimulatedCall
from .oracle import judge_call


def write_call_artifacts(call: SimulatedCall, output_dir: Path) -> ArtifactPaths:
    call_dir = output_dir / "calls" / call.call_id
    call_dir.mkdir(parents=True, exist_ok=True)
    transcript = call_dir / "transcript.md"
    events = call_dir / "events.jsonl"
    metadata = call_dir / "metadata.json"
    bug = call_dir / "bug.md"

    severity, suspected_bug = judge_call(call)
    transcript.write_text(_render_transcript(call))
    events.write_text(_render_events(call))
    metadata.write_text(json.dumps(_metadata(call, severity, suspected_bug), indent=2) + "\n")
    bug.write_text(_render_bug(call, severity, suspected_bug))
    return ArtifactPaths(call_dir, transcript, events, metadata, bug)


def write_index(calls: list[SimulatedCall], output_dir: Path) -> Path:
    path = output_dir / "CALL_INDEX.md"
    lines = [
        "# Call Index",
        "",
        "| Call | Scenario | Duration | Transcript | Bug | Severity |",
        "|---|---|---:|---|---|---|",
    ]
    for call in calls:
        severity, bug = judge_call(call)
        rel = f"calls/{call.call_id}/transcript.md"
        lines.append(
            f"| {call.call_id} | {call.scenario.title} | {call.duration_seconds:.0f}s | {rel} | {bug or 'None'} | {severity} |"
        )
    path.write_text("\n".join(lines) + "\n")
    return path


def write_bug_report(calls: list[SimulatedCall], output_dir: Path) -> Path:
    path = output_dir / "BUG_REPORT.md"
    sections = ["# Bug Report", ""]
    bug_count = 0
    for call in calls:
        severity, bug = judge_call(call)
        if not bug or severity == "None":
            continue
        bug_count += 1
        sections.extend(
            [
                f"## BUG-{bug_count:03d}: {call.scenario.title}",
                "",
                f"Severity: {severity}",
                f"Call: {call.call_id}",
                f"Transcript: calls/{call.call_id}/transcript.md",
                "",
                "What happened:",
                bug,
                "",
                "Why this matters:",
                _why_it_matters(severity),
                "",
                "Expected behavior:",
                "\n".join(f"- {item}" for item in call.scenario.expected_behavior),
                "",
            ]
        )
    if bug_count == 0:
        sections.append("No high-confidence bugs found in this run.")
    path.write_text("\n".join(sections).strip() + "\n")
    return path


def _render_transcript(call: SimulatedCall) -> str:
    lines = [f"# Transcript: {call.call_id}", "", f"Scenario: {call.scenario.title}", ""]
    for turn in call.turns:
        lines.append(
            f"[{_timestamp(turn.start_seconds)}-{_timestamp(turn.end_seconds)}] "
            f"**{turn.speaker.title()}**: {turn.text}"
        )
    return "\n".join(lines) + "\n"


def _render_events(call: SimulatedCall) -> str:
    events = []
    for index, turn in enumerate(call.turns):
        events.append(
            json.dumps(
                {
                    "event": "turn",
                    "index": index,
                    "speaker": turn.speaker,
                    "start_seconds": round(turn.start_seconds, 2),
                    "end_seconds": round(turn.end_seconds, 2),
                    "text": turn.text,
                }
            )
        )
    return "\n".join(events) + "\n"


def _metadata(call: SimulatedCall, severity: str, suspected_bug: str | None) -> dict:
    return {
        "call_id": call.call_id,
        "scenario_id": call.scenario.id,
        "title": call.scenario.title,
        "category": call.scenario.category,
        "duration_seconds": round(call.duration_seconds, 2),
        "severity": severity,
        "suspected_bug": suspected_bug,
        "simulated": True,
    }


def _render_bug(call: SimulatedCall, severity: str, suspected_bug: str | None) -> str:
    if not suspected_bug or severity == "None":
        return f"# {call.call_id}\n\nNo high-confidence bug in local simulation.\n"
    return (
        f"# {call.call_id}: {call.scenario.title}\n\n"
        f"Severity: {severity}\n\n"
        f"What happened:\n{suspected_bug}\n\n"
        "Expected behavior:\n"
        + "\n".join(f"- {item}" for item in call.scenario.expected_behavior)
        + "\n"
    )


def _why_it_matters(severity: str) -> str:
    if severity == "Critical":
        return "This can affect patient safety, privacy, or urgent escalation."
    if severity == "High":
        return "This can create false expectations, operational cleanup, or incorrect patient guidance."
    return "This can degrade task completion or patient trust."


def _timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    rem = int(seconds % 60)
    return f"{minutes:02d}:{rem:02d}"
