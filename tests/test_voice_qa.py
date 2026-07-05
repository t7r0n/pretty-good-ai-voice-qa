from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from voice_qa.artifacts import write_bug_report, write_call_artifacts, write_index
from voice_qa.cli import app
from voice_qa.config import assert_allowed_target, get_secret, secret_status
from voice_qa.scenarios import load_scenarios
from voice_qa.simulator import simulate_call
from voice_qa.submission import FORM_URL, REPOSITORY_URL, validate_campaign, validate_final_readiness, write_evidence_manifest


def test_target_guard_accepts_only_assessment_number() -> None:
    assert assert_allowed_target("(805) 439-8008") == "+18054398008"
    try:
        assert_allowed_target("+18054398009")
    except ValueError as exc:
        assert "only +18054398008" in str(exc)
    else:
        raise AssertionError("guard should reject non-assessment number")


def test_env_aliases_do_not_expose_secret_values(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("groq_api_key=gsk_test_secret\nHF_token=hf_test_secret\n")
    assert get_secret("groq_api_key", tmp_path) == "gsk_test_secret"
    statuses = {status.key: status for status in secret_status(tmp_path)}
    assert statuses["groq_api_key"].present


def test_env_does_not_fall_back_to_process_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("groq_api_key", "global_secret_should_not_apply")
    assert get_secret("groq_api_key", tmp_path) is None


def test_scenarios_load_and_cover_required_categories() -> None:
    scenarios = load_scenarios(Path("scenarios"))
    categories = {scenario.category for scenario in scenarios}
    assert len(scenarios) >= 10
    assert {"scheduling", "medication", "insurance", "safety"} <= categories


def test_local_simulation_writes_artifacts(tmp_path: Path) -> None:
    scenario = load_scenarios(Path("scenarios"))[0]
    call = simulate_call(scenario, 1)
    paths = write_call_artifacts(call, tmp_path)
    write_index([call], tmp_path)
    write_bug_report([call], tmp_path)
    assert paths.transcript.exists()
    assert paths.events.exists()
    metadata = json.loads(paths.metadata.read_text())
    assert metadata["simulated"] is True
    assert (tmp_path / "CALL_INDEX.md").exists()
    assert (tmp_path / "BUG_REPORT.md").exists()
    transcript = paths.transcript.read_text()
    assert scenario.expected_bug not in transcript


def test_voiceqa_cli_simulate(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(app, ["simulate", "--count", "2", "--output", "artifacts/local_sim"])
    assert result.exit_code == 0, result.output
    assert (workspace / "artifacts/local_sim/CALL_INDEX.md").exists()
    assert (workspace / "artifacts/local_sim/BUG_REPORT.md").exists()


def test_voiceqa_cli_simulate_cleans_stale_calls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full = runner.invoke(app, ["simulate", "--all", "--output", "artifacts/local_sim"])
    assert full.exit_code == 0, full.output
    short = runner.invoke(app, ["simulate", "--count", "2", "--output", "artifacts/local_sim"])
    assert short.exit_code == 0, short.output
    call_dirs = list((tmp_path / "artifacts/local_sim/calls").iterdir())
    assert len(call_dirs) == 2


def test_voiceqa_cli_rejects_output_outside_workspace(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(app, ["simulate", "--count", "1", "--output", str(outside)])
    assert result.exit_code != 0
    assert "inside workspace" in result.output


def test_voiceqa_cli_rejects_destructive_workspace_root_output(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(app, ["simulate", "--count", "1", "--output", "."])
    assert result.exit_code != 0
    assert "workspace root" in result.output


def test_voiceqa_cli_unknown_scenario_is_clean_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["simulate", "--scenario", "missing", "--output", "artifacts/local_sim"])
    assert result.exit_code != 0
    assert "Unknown scenario" in result.output


def test_transcribe_rejects_files_outside_artifacts(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"not-real-audio")
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(app, ["transcribe", str(outside)])
    assert result.exit_code != 0
    assert "inside workspace" in result.output or "artifacts/" in result.output


def test_transcribe_rejects_unsupported_artifact_extension(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    audio_dir = workspace / "artifacts" / "recordings"
    audio_dir.mkdir(parents=True)
    bad = audio_dir / "audio.txt"
    bad.write_text("not audio")
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(app, ["transcribe", str(bad)])
    assert result.exit_code != 0
    assert "Unsupported audio extension" in result.output


def test_transcribe_rejects_secret_output_path(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    audio_dir = workspace / "artifacts" / "recordings"
    audio_dir.mkdir(parents=True)
    wav = audio_dir / "audio.wav"
    wav.write_bytes(b"not-real-audio")
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(app, ["transcribe", str(wav), "--output", ".env"])
    assert result.exit_code != 0
    assert "artifacts/" in result.output


def test_voiceqa_cli_writes_evidence_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    _write_submission_fixture(tmp_path, complete_calls=10)
    (tmp_path / "EVIDENCE_MANIFEST.md").unlink()
    runner = CliRunner()

    result = runner.invoke(app, ["evidence-manifest"])

    assert result.exit_code == 0, result.output
    manifest = tmp_path / "EVIDENCE_MANIFEST.md"
    assert manifest.exists()
    text = manifest.read_text()
    assert "| Evidence sets | 16 |" in text
    assert "MP3 SHA-256" in text


def test_submission_validator_accepts_complete_campaign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)

    result = validate_campaign(campaign)

    assert result.ok is True
    assert result.issues == []
    assert result.summary["complete_call_sets"] == 10
    assert result.summary["supplemental_complete_call_sets"] == 6


def test_submission_validator_requires_supplemental_cleanup_campaign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)
    shutil.rmtree(tmp_path / "artifacts" / "campaign_20260705_clean")

    result = validate_campaign(campaign)

    assert result.ok is False
    assert any("Missing supplemental cleanup campaign" in issue for issue in result.issues)


def test_submission_validator_catches_event_log_sid_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)
    sid = "CA000000000000000000000000000000000"
    rows = _fixture_event_rows(sid)
    rows[0]["call_sid"] = "CA999999999999999999999999999999999"
    (campaign / "events" / sid / "events.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    result = validate_campaign(campaign)

    assert result.ok is False
    assert any("start call_sid does not match" in issue for issue in result.issues)


def test_submission_validator_catches_stale_evidence_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)
    (tmp_path / "EVIDENCE_MANIFEST.md").write_text("# stale\n")

    result = validate_campaign(campaign)

    assert result.ok is False
    assert any("EVIDENCE_MANIFEST.md is stale" in issue for issue in result.issues)


def test_submission_validator_catches_missing_events_and_broken_links(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)
    (campaign / "events" / "CA000000000000000000000000000000000" / "events.jsonl").write_text(
        "\n".join([json.dumps({"event": "start"}), json.dumps({"event": "stop"})]) + "\n"
    )
    (campaign / "BUG_REPORT.md").write_text("[missing](transcripts_md/missing.md)\n")

    result = validate_campaign(campaign)

    assert result.ok is False
    assert any("too few Twilio media frames" in issue for issue in result.issues)
    assert any("missing OpenAI outbound audio" in issue for issue in result.issues)
    assert any("Broken link" in issue for issue in result.issues)


def test_submission_validator_catches_fake_recordings_without_ffprobe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)
    recording = next((campaign / "recordings").glob("*.mp3"))
    recording.write_bytes(b"fake mp3")

    result = validate_campaign(campaign)

    assert result.ok is False
    assert any("unexpectedly small" in issue for issue in result.issues)
    assert any("does not look like an MP3" in issue for issue in result.issues)


def test_final_readiness_fails_until_video_links_are_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)

    result = validate_final_readiness(campaign)

    assert result.ok is False
    assert any("Missing final Loom" in issue for issue in result.issues)
    assert any("Missing final AI-debugging" in issue for issue in result.issues)


def test_final_readiness_passes_with_video_links(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    campaign = _write_submission_fixture(tmp_path, complete_calls=10)
    loom = "https://loom.example.com/share/final"
    debug = "https://videos.example.com/final-debug"
    (tmp_path / "FINAL_SUBMISSION_PACKET.md").write_text(
        "\n".join(
            [
                f"Submission form: [{FORM_URL}]({FORM_URL})",
                f"- GitHub repository: [{REPOSITORY_URL}]({REPOSITORY_URL})",
                f"- Loom walkthrough link: {loom}",
                f"- AI-debugging screen recording link: {debug}",
            ]
        )
        + "\n"
    )
    (tmp_path / "SUBMISSION_CHECKLIST.md").write_text(
        "\n".join(
            [
                f"- [x] Loom walkthrough link: {loom}.",
                f"- [x] 5-minute AI-debugging screen recording link: {debug}.",
                f"- [x] Public GitHub repository link: [{REPOSITORY_URL}]({REPOSITORY_URL}).",
                f"- [ ] Submission form filled at [{FORM_URL}]({FORM_URL}) with the one Twilio caller number used.",
            ]
        )
        + "\n"
    )
    (tmp_path / "README.md").write_text(
        "\n".join(
            [
                f"- Public GitHub repository: [{REPOSITORY_URL}]({REPOSITORY_URL})",
                f"- Loom walkthrough: {loom}",
                f"- AI-debugging screen recording: {debug}",
            ]
        )
        + "\n"
    )

    result = validate_final_readiness(campaign)

    assert result.ok is True
    assert result.summary["final_ready"] == 1


def _write_submission_fixture(workspace: Path, complete_calls: int) -> Path:
    for name in [
        "ARCHITECTURE.md",
        "RECORDING_RUNBOOK.md",
        "REQUIREMENTS_AUDIT.md",
        "VOICE_QUALITY_REVIEW.md",
        "CALL_INDEX.md",
        "BUG_REPORT.md",
        "LOOM.md",
        "AI_DEBUGGING_RECORDING.md",
        "SUBMISSION_CHECKLIST.md",
    ]:
        (workspace / name).write_text("# Fixture\n")
    (workspace / "FINAL_SUBMISSION_PACKET.md").write_text(
        "\n".join(
            [
                f"Submission form: [{FORM_URL}]({FORM_URL})",
                f"- GitHub repository: [{REPOSITORY_URL}]({REPOSITORY_URL})",
                "- Loom walkthrough link: add after recording.",
                "- AI-debugging screen recording link: add after recording.",
            ]
        )
        + "\n"
    )
    (workspace / "SUBMISSION_CHECKLIST.md").write_text(
        "\n".join(
            [
                "- [ ] Loom walkthrough link.",
                "- [ ] 5-minute AI-debugging screen recording link.",
                f"- [x] Public GitHub repository link: [{REPOSITORY_URL}]({REPOSITORY_URL}).",
                f"- [ ] Submission form filled at [{FORM_URL}]({FORM_URL}) with the one Twilio caller number used.",
            ]
        )
        + "\n"
    )
    (workspace / "README.md").write_text(f"- Public GitHub repository: [{REPOSITORY_URL}]({REPOSITORY_URL})\n")

    campaign = workspace / "artifacts" / "campaign_20260705"
    for subdir in ["recordings", "transcripts", "transcripts_md", "events"]:
        (campaign / subdir).mkdir(parents=True, exist_ok=True)
    (campaign / "CALL_INDEX.md").write_text("[call](transcripts_md/CA000000000000000000000000000000000_fixture.md)\n")
    (campaign / "BUG_REPORT.md").write_text("[recording](recordings/CA000000000000000000000000000000000_REfixture.mp3)\n")
    (campaign / "VALIDATION_REPORT.md").write_text("# Validation\n")

    for index in range(complete_calls):
        sid = f"CA{index:033d}"
        (campaign / "recordings" / f"{sid}_REfixture.mp3").write_bytes(b"\xff\xf3" + (b"\x00" * 150_000))
        (campaign / "transcripts" / f"{sid}_fixture.json").write_text(
            json.dumps({"duration": 60.0, "text": "submission transcript evidence " * 20})
        )
        (campaign / "transcripts_md" / f"{sid}_fixture.md").write_text("[000.00-001.00] fixture transcript\n")
        event_dir = campaign / "events" / sid
        event_dir.mkdir()
        event_dir.joinpath("events.jsonl").write_text("\n".join(json.dumps(row) for row in _fixture_event_rows(sid)) + "\n")

    supplemental = workspace / "artifacts" / "campaign_20260705_clean"
    for subdir in ["recordings", "transcripts", "transcripts_md", "events"]:
        (supplemental / subdir).mkdir(parents=True, exist_ok=True)
    (supplemental / "CALL_INDEX.md").write_text("[call](transcripts_md/CA900000000000000000000000000000000_fixture.md)\n")
    for index in range(6):
        sid = f"CA9{index:032d}"
        (supplemental / "recordings" / f"{sid}_REfixture.mp3").write_bytes(b"\xff\xf3" + (b"\x00" * 150_000))
        (supplemental / "transcripts" / f"{sid}_fixture.json").write_text(
            json.dumps({"duration": 60.0, "text": "supplemental transcript evidence " * 20})
        )
        (supplemental / "transcripts_md" / f"{sid}_fixture.md").write_text("[000.00-001.00] fixture transcript\n")
        event_dir = supplemental / "events" / sid
        event_dir.mkdir()
        event_dir.joinpath("events.jsonl").write_text("\n".join(json.dumps(row) for row in _fixture_event_rows(sid)) + "\n")
    write_evidence_manifest(root=campaign, output=workspace / "EVIDENCE_MANIFEST.md")
    return campaign


def _fixture_event_rows(sid: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [{"event": "start", "call_sid": sid, "ts": 0.0}]
    rows.extend({"event": "media", "chunk": str(index), "ts": 0.1 + index} for index in range(12))
    rows.append({"event": "openai_outbound", "ts": 20.0})
    rows.append({"event": "stop", "ts": 21.0})
    return rows
