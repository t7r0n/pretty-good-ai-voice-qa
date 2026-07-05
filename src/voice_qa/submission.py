from __future__ import annotations

import json
import re
import shutil
import subprocess
from hashlib import sha256
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubmissionValidation:
    ok: bool
    issues: list[str]
    summary: dict[str, int]


FORM_URL = "https://forms.gle/sdnbrJX2XbgZeQaY6"
REPOSITORY_URL = "https://github.com/t7r0n/pretty-good-ai-voice-qa"


def validate_campaign(root: Path = Path("artifacts/campaign_20260705")) -> SubmissionValidation:
    issues: list[str] = []
    root = root.resolve()
    required = [
        root / "CALL_INDEX.md",
        root / "BUG_REPORT.md",
        root / "VALIDATION_REPORT.md",
        Path("README.md").resolve(),
        Path("FINAL_SUBMISSION_PACKET.md").resolve(),
        Path("RECORDING_RUNBOOK.md").resolve(),
        Path("ARCHITECTURE.md").resolve(),
        Path("REQUIREMENTS_AUDIT.md").resolve(),
        Path("VOICE_QUALITY_REVIEW.md").resolve(),
        Path("EVIDENCE_MANIFEST.md").resolve(),
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
                issues.append(f"Recording duration too short for usable call evidence: {recording} ({duration:.1f}s).")

    for transcript in transcripts_json:
        try:
            data = json.loads(transcript.read_text())
        except json.JSONDecodeError as exc:
            issues.append(f"Invalid JSON transcript {transcript}: {exc}")
            continue
        duration = float(data.get("duration") or 0)
        text = data.get("text") or ""
        if duration < 45:
            issues.append(f"Transcript duration too short for usable call evidence: {transcript} ({duration:.1f}s).")
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
        issues.extend(_event_log_issues(event_log, expected_sid=event_log.parent.name))

    markdowns_to_check = [
        root / "CALL_INDEX.md",
        root / "BUG_REPORT.md",
        Path("README.md"),
        Path("FINAL_SUBMISSION_PACKET.md"),
        Path("RECORDING_RUNBOOK.md"),
        Path("ARCHITECTURE.md"),
        Path("REQUIREMENTS_AUDIT.md"),
        Path("VOICE_QUALITY_REVIEW.md"),
        Path("EVIDENCE_MANIFEST.md"),
        Path("CALL_INDEX.md"),
        Path("BUG_REPORT.md"),
        Path("LOOM.md"),
        Path("AI_DEBUGGING_RECORDING.md"),
        Path("SUBMISSION_CHECKLIST.md"),
    ]
    for markdown in markdowns_to_check:
        if markdown.exists():
            issues.extend(_broken_links(markdown))

    manifest = Path("EVIDENCE_MANIFEST.md")
    if manifest.exists():
        expected_manifest = build_evidence_manifest(root=root, output=manifest)
        if manifest.read_text() != expected_manifest:
            issues.append("EVIDENCE_MANIFEST.md is stale; regenerate it with `uv run voiceqa evidence-manifest`.")

    supplemental_root = Path("artifacts/campaign_20260705_clean").resolve()
    supplemental_complete_sets = 0
    if not supplemental_root.exists():
        issues.append(f"Missing supplemental cleanup campaign directory: {supplemental_root}")
    else:
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
            issues.extend(_event_log_issues(event_log, expected_sid=event_log.parent.name, label="Supplemental "))

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


def write_evidence_manifest(
    root: Path = Path("artifacts/campaign_20260705"),
    output: Path = Path("EVIDENCE_MANIFEST.md"),
) -> Path:
    output.write_text(build_evidence_manifest(root=root, output=output))
    return output


def build_evidence_manifest(
    root: Path = Path("artifacts/campaign_20260705"),
    output: Path = Path("EVIDENCE_MANIFEST.md"),
) -> str:
    rows = _manifest_rows(root.resolve(), "primary", output)
    supplemental_root = Path("artifacts/campaign_20260705_clean").resolve()
    if supplemental_root.exists():
        rows.extend(_manifest_rows(supplemental_root, "supplemental", output))

    total_recording_seconds = sum(row["recording_seconds"] for row in rows if isinstance(row["recording_seconds"], float))
    total_transcript_seconds = sum(row["transcript_seconds"] for row in rows if isinstance(row["transcript_seconds"], float))
    total_media_frames = sum(int(row["media_frames"]) for row in rows)
    total_openai_outbound = sum(int(row["openai_outbound"]) for row in rows)

    lines = [
        "# Evidence Manifest",
        "",
        "Generated by `uv run voiceqa evidence-manifest`. Hashes are SHA-256 values for the committed local evidence files.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Evidence sets | {len(rows)} |",
        f"| Total recording seconds | {total_recording_seconds:.1f} |",
        f"| Total transcript seconds | {total_transcript_seconds:.1f} |",
        f"| Twilio media frames | {total_media_frames} |",
        f"| OpenAI outbound audio events | {total_openai_outbound} |",
        "",
        "## Per-Call Integrity",
        "",
        "| Campaign | Scenario | Call SID | Recording | Rec s | Tx s | Text chars | Event rows | Media | OpenAI out | MP3 SHA-256 | JSON SHA-256 | MD SHA-256 | Events SHA-256 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {campaign} | {scenario} | `{sid}` | [mp3]({recording_link}) | {recording_seconds:.1f} | "
            "{transcript_seconds:.1f} | {text_chars} | {event_rows} | {media_frames} | {openai_outbound} | "
            "`{recording_sha}` | `{transcript_sha}` | `{markdown_sha}` | `{event_sha}` |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Primary and supplemental evidence sets each include MP3 recording, Groq JSON transcript, timestamped markdown transcript, and local event log.",
            "- Event logs are additionally validated for parseability, one start, one stop, Twilio media frames, OpenAI outbound audio, matching start call SID, and monotonic timestamps.",
            "- Two supplemental long-limit calls reached the 180-second cap and are intentionally retained as stress evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_final_readiness(root: Path = Path("artifacts/campaign_20260705")) -> SubmissionValidation:
    campaign = validate_campaign(root)
    issues = list(campaign.issues)

    packet = Path("FINAL_SUBMISSION_PACKET.md")
    checklist = Path("SUBMISSION_CHECKLIST.md")
    readme = Path("README.md")
    for path in (packet, checklist, readme):
        if not path.exists():
            issues.append(f"Missing final readiness file: {path}")

    packet_text = packet.read_text() if packet.exists() else ""
    checklist_text = checklist.read_text() if checklist.exists() else ""
    readme_text = readme.read_text() if readme.exists() else ""

    loom_url = _extract_line_url(packet_text, "Loom walkthrough link:")
    debug_url = _extract_line_url(packet_text, "AI-debugging screen recording link:")
    if not loom_url:
        issues.append("Missing final Loom walkthrough URL in FINAL_SUBMISSION_PACKET.md.")
    if not debug_url:
        issues.append("Missing final AI-debugging screen recording URL in FINAL_SUBMISSION_PACKET.md.")
    if loom_url and f"- [x] Loom walkthrough link: {loom_url}." not in checklist_text:
        issues.append("SUBMISSION_CHECKLIST.md does not mark the Loom link complete with the packet URL.")
    if debug_url and f"- [x] 5-minute AI-debugging screen recording link: {debug_url}." not in checklist_text:
        issues.append("SUBMISSION_CHECKLIST.md does not mark the AI-debugging recording link complete with the packet URL.")
    if loom_url and f"- Loom walkthrough: {loom_url}" not in readme_text:
        issues.append("README.md does not include the final Loom walkthrough URL.")
    if debug_url and f"- AI-debugging screen recording: {debug_url}" not in readme_text:
        issues.append("README.md does not include the final AI-debugging recording URL.")

    for label, text in (("FINAL_SUBMISSION_PACKET.md", packet_text), ("SUBMISSION_CHECKLIST.md", checklist_text)):
        if FORM_URL not in text:
            issues.append(f"{label} is missing the official submission form URL.")
        if REPOSITORY_URL not in text:
            issues.append(f"{label} is missing the public GitHub repository URL.")

    placeholders = ["add after recording", "https://your-loom-url", "https://your-debug-recording-url"]
    for label, text in (
        ("FINAL_SUBMISSION_PACKET.md", packet_text),
        ("SUBMISSION_CHECKLIST.md", checklist_text),
        ("README.md", readme_text),
    ):
        for placeholder in placeholders:
            if placeholder in text:
                issues.append(f"{label} still contains placeholder text: {placeholder}")

    summary = dict(campaign.summary)
    summary["loom_link_present"] = int(bool(loom_url))
    summary["debug_recording_link_present"] = int(bool(debug_url))
    summary["final_ready"] = int(not issues)
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


def _extract_line_url(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if prefix not in line:
            continue
        match = re.search(r"https://\S+", line)
        if not match:
            return None
        url = match.group(0).rstrip(".,)")
        if "your-" in url:
            return None
        return url
    return None


def _event_log_issues(path: Path, *, expected_sid: str, label: str = "") -> list[str]:
    issues: list[str] = []
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{label}Event log has invalid JSON at {path}:{line_number}: {exc}")
            continue
        if not isinstance(row, dict):
            issues.append(f"{label}Event log row is not an object at {path}:{line_number}")
            continue
        rows.append(row)

    if not rows:
        return [f"{label}Event log is empty: {path}"]

    counts = Counter(row.get("event") for row in rows)
    if counts["start"] != 1:
        issues.append(f"{label}Event log should contain exactly one start event: {path} ({counts['start']}).")
    if counts["stop"] != 1:
        issues.append(f"{label}Event log should contain exactly one stop event: {path} ({counts['stop']}).")
    if counts["media"] < 10:
        issues.append(f"{label}Event log has too few Twilio media frames: {path} ({counts['media']}).")
    if counts["openai_outbound"] <= 0:
        issues.append(f"{label}Event log missing OpenAI outbound audio: {path}")

    start_rows = [row for row in rows if row.get("event") == "start"]
    if start_rows and start_rows[0].get("call_sid") != expected_sid:
        issues.append(
            f"{label}Event log start call_sid does not match directory: {path} "
            f"({start_rows[0].get('call_sid')} vs {expected_sid})."
        )

    timestamps = [row.get("ts") for row in rows if isinstance(row.get("ts"), int | float)]
    if any(current < previous for previous, current in zip(timestamps, timestamps[1:])):
        issues.append(f"{label}Event log timestamps are not monotonic: {path}")

    return issues


def _manifest_rows(root: Path, campaign: str, output: Path) -> list[dict[str, object]]:
    recordings = {_sid_from_name(path.name): path for path in sorted((root / "recordings").glob("*.mp3"))}
    transcripts = {_sid_from_name(path.name): path for path in sorted((root / "transcripts").glob("*.json"))}
    markdowns = {_sid_from_name(path.name): path for path in sorted((root / "transcripts_md").glob("*.md"))}
    events = {path.parent.name: path for path in sorted((root / "events").glob("CA*/events.jsonl"))}
    sids = sorted(recordings.keys() & transcripts.keys() & markdowns.keys() & events.keys())
    rows: list[dict[str, object]] = []
    for sid in sids:
        transcript_data = json.loads(transcripts[sid].read_text())
        event_rows = [json.loads(line) for line in events[sid].read_text().splitlines() if line.strip()]
        counts = Counter(row.get("event") for row in event_rows)
        rows.append(
            {
                "campaign": campaign,
                "scenario": _scenario_from_transcript(transcripts[sid]),
                "sid": sid,
                "recording_link": _markdown_link(output, recordings[sid]),
                "recording_seconds": _recording_duration_seconds(recordings[sid]) or float(transcript_data.get("duration") or 0),
                "transcript_seconds": float(transcript_data.get("duration") or 0),
                "text_chars": len(transcript_data.get("text") or ""),
                "event_rows": len(event_rows),
                "media_frames": counts["media"],
                "openai_outbound": counts["openai_outbound"],
                "recording_sha": _sha256_prefix(recordings[sid]),
                "transcript_sha": _sha256_prefix(transcripts[sid]),
                "markdown_sha": _sha256_prefix(markdowns[sid]),
                "event_sha": _sha256_prefix(events[sid]),
            }
        )
    return rows


def _scenario_from_transcript(path: Path) -> str:
    stem = path.stem
    if "_" not in stem:
        return "unknown"
    return stem.split("_", 1)[1]


def _markdown_link(markdown: Path, target: Path) -> str:
    return target.resolve().relative_to(markdown.resolve().parent).as_posix()


def _sha256_prefix(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
