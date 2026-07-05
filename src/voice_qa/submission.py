from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubmissionValidation:
    ok: bool
    issues: list[str]
    summary: dict[str, int]


def validate_campaign(root: Path = Path("artifacts/campaign_20260705")) -> SubmissionValidation:
    issues: list[str] = []
    root = root.resolve()
    required = [
        root / "CALL_INDEX.md",
        root / "BUG_REPORT.md",
        root / "VALIDATION_REPORT.md",
        Path("README.md").resolve(),
        Path("FINAL_SUBMISSION_PACKET.md").resolve(),
        Path("ARCHITECTURE.md").resolve(),
        Path("REQUIREMENTS_AUDIT.md").resolve(),
        Path("VOICE_QUALITY_REVIEW.md").resolve(),
        Path("CALL_INDEX.md").resolve(),
        Path("BUG_REPORT.md").resolve(),
        Path("LOOM.md").resolve(),
        Path("AI_DEBUGGING_RECORDING.md").resolve(),
        Path("SUBMISSION_CHECKLIST.md").resolve(),
    ]
    for path in required:
        if not path.exists():
            issues.append(f"Missing required file: {path}")

    recordings = sorted((root / "recordings").glob("*.mp3"))
    transcripts_json = sorted((root / "transcripts").glob("*.json"))
    transcripts_md = sorted((root / "transcripts_md").glob("*.md"))
    event_logs = sorted((root / "events").glob("CA*/events.jsonl"))

    if len(recordings) < 10:
        issues.append(f"Need at least 10 MP3 recordings, found {len(recordings)}.")
    if len(transcripts_json) < 10:
        issues.append(f"Need at least 10 transcript JSON files, found {len(transcripts_json)}.")
    if len(transcripts_md) < 10:
        issues.append(f"Need at least 10 timestamped transcript markdown files, found {len(transcripts_md)}.")
    if len(event_logs) < 10:
        issues.append(f"Need at least 10 event logs, found {len(event_logs)}.")

    recording_sids = {_sid_from_name(path.name) for path in recordings}
    transcript_sids = {_sid_from_name(path.name) for path in transcripts_json}
    markdown_sids = {_sid_from_name(path.name) for path in transcripts_md}
    event_sids = {path.parent.name for path in event_logs}
    common_sids = recording_sids & transcript_sids & markdown_sids & event_sids
    if len(common_sids) < 10:
        issues.append(f"Need at least 10 calls with recording+transcript+markdown+events, found {len(common_sids)}.")

    recording_durations: dict[str, float] = {}
    for recording in recordings:
        sid = _sid_from_name(recording.name)
        issues.extend(_recording_issues(recording))
        duration = _recording_duration_seconds(recording)
        if duration is not None:
            recording_durations[sid] = duration
            if duration < 45:
                issues.append(f"Recording duration too short for full call: {recording} ({duration:.1f}s).")

    for transcript in transcripts_json:
        try:
            data = json.loads(transcript.read_text())
        except json.JSONDecodeError as exc:
            issues.append(f"Invalid JSON transcript {transcript}: {exc}")
            continue
        duration = float(data.get("duration") or 0)
        text = data.get("text") or ""
        if duration < 45:
            issues.append(f"Transcript duration too short for full call: {transcript} ({duration:.1f}s).")
        if len(text) < 250:
            issues.append(f"Transcript text too short: {transcript}.")
        recording_duration = recording_durations.get(_sid_from_name(transcript.name))
        if recording_duration is not None and abs(recording_duration - duration) > 5:
            issues.append(
                f"Transcript duration does not match recording: {transcript} "
                f"({duration:.1f}s transcript vs {recording_duration:.1f}s recording)."
            )

    for markdown in transcripts_md:
        if not re.search(r"^\[\d{3}\.\d{2}-\d{3}\.\d{2}\]", markdown.read_text(), re.MULTILINE):
            issues.append(f"Timestamped transcript markdown has no timestamp lines: {markdown}")

    for event_log in event_logs:
        rows = [json.loads(line) for line in event_log.read_text().splitlines() if line.strip()]
        counts = Counter(row.get("event") for row in rows)
        for event in ("start", "media", "openai_outbound", "stop"):
            if counts[event] <= 0:
                issues.append(f"Event log missing {event}: {event_log}")

    markdowns_to_check = [
        root / "CALL_INDEX.md",
        root / "BUG_REPORT.md",
        Path("README.md"),
        Path("FINAL_SUBMISSION_PACKET.md"),
        Path("ARCHITECTURE.md"),
        Path("REQUIREMENTS_AUDIT.md"),
        Path("VOICE_QUALITY_REVIEW.md"),
        Path("CALL_INDEX.md"),
        Path("BUG_REPORT.md"),
        Path("LOOM.md"),
        Path("AI_DEBUGGING_RECORDING.md"),
        Path("SUBMISSION_CHECKLIST.md"),
    ]
    for markdown in markdowns_to_check:
        if markdown.exists():
            issues.extend(_broken_links(markdown))

    supplemental_root = Path("artifacts/campaign_20260705_clean").resolve()
    supplemental_complete_sets = 0
    if supplemental_root.exists():
        supplemental_index = supplemental_root / "CALL_INDEX.md"
        if not supplemental_index.exists():
            issues.append(f"Missing supplemental call index: {supplemental_index}")
        else:
            issues.extend(_broken_links(supplemental_index))
        supplemental_recordings = sorted((supplemental_root / "recordings").glob("*.mp3"))
        supplemental_transcripts = sorted((supplemental_root / "transcripts").glob("*.json"))
        supplemental_markdown = sorted((supplemental_root / "transcripts_md").glob("*.md"))
        supplemental_events = sorted((supplemental_root / "events").glob("CA*/events.jsonl"))
        supplemental_common = (
            {_sid_from_name(path.name) for path in supplemental_recordings}
            & {_sid_from_name(path.name) for path in supplemental_transcripts}
            & {_sid_from_name(path.name) for path in supplemental_markdown}
            & {path.parent.name for path in supplemental_events}
        )
        supplemental_complete_sets = len(supplemental_common)
        if supplemental_complete_sets < 6:
            issues.append(f"Need 6 supplemental cleanup call sets, found {supplemental_complete_sets}.")
        supplemental_durations: dict[str, float] = {}
        for recording in supplemental_recordings:
            sid = _sid_from_name(recording.name)
            issues.extend(_recording_issues(recording))
            duration = _recording_duration_seconds(recording)
            if duration is not None:
                supplemental_durations[sid] = duration
                if duration < 45:
                    issues.append(f"Supplemental recording duration too short: {recording} ({duration:.1f}s).")
        for transcript in supplemental_transcripts:
            try:
                data = json.loads(transcript.read_text())
            except json.JSONDecodeError as exc:
                issues.append(f"Invalid supplemental JSON transcript {transcript}: {exc}")
                continue
            duration = float(data.get("duration") or 0)
            text = data.get("text") or ""
            if duration < 45:
                issues.append(f"Supplemental transcript duration too short: {transcript} ({duration:.1f}s).")
            if len(text) < 250:
                issues.append(f"Supplemental transcript text too short: {transcript}.")
            recording_duration = supplemental_durations.get(_sid_from_name(transcript.name))
            if recording_duration is not None and abs(recording_duration - duration) > 5:
                issues.append(
                    f"Supplemental transcript duration does not match recording: {transcript} "
                    f"({duration:.1f}s transcript vs {recording_duration:.1f}s recording)."
                )
        for markdown in supplemental_markdown:
            if not re.search(r"^\[\d{3}\.\d{2}-\d{3}\.\d{2}\]", markdown.read_text(), re.MULTILINE):
                issues.append(f"Supplemental timestamped transcript markdown has no timestamp lines: {markdown}")
        for event_log in supplemental_events:
            rows = [json.loads(line) for line in event_log.read_text().splitlines() if line.strip()]
            counts = Counter(row.get("event") for row in rows)
            for event in ("start", "media", "openai_outbound", "stop"):
                if counts[event] <= 0:
                    issues.append(f"Supplemental event log missing {event}: {event_log}")

    summary = {
        "recordings": len(recordings),
        "transcripts_json": len(transcripts_json),
        "transcripts_md": len(transcripts_md),
        "event_logs": len(event_logs),
        "complete_call_sets": len(common_sids),
        "supplemental_complete_call_sets": supplemental_complete_sets,
        "total_complete_call_sets": len(common_sids) + supplemental_complete_sets,
    }
    return SubmissionValidation(ok=not issues, issues=issues, summary=summary)


def _sid_from_name(name: str) -> str:
    return name.split("_", 1)[0]


def _recording_issues(path: Path) -> list[str]:
    issues: list[str] = []
    data = path.read_bytes()
    if len(data) < 100_000:
        issues.append(f"Recording file is unexpectedly small: {path} ({len(data)} bytes).")
    if not (data.startswith(b"ID3") or data[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}):
        issues.append(f"Recording does not look like an MP3 file: {path}")
    if shutil.which("ffprobe") and _recording_duration_seconds(path) is None:
        issues.append(f"ffprobe could not read MP3 duration: {path}")
    return issues


def _recording_duration_seconds(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        output = subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    try:
        return float(output.strip())
    except ValueError:
        return None


def _broken_links(markdown: Path) -> list[str]:
    text = markdown.read_text()
    broken: list[str] = []
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#")):
            continue
        if not (markdown.parent / target).exists():
            broken.append(f"Broken link in {markdown}: {target}")
    return broken
