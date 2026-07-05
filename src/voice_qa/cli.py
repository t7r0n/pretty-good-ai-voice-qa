from __future__ import annotations

import json
from pathlib import Path
import shutil

import typer
from rich.console import Console
from rich.table import Table

from .artifacts import write_bug_report, write_call_artifacts, write_index
from .call_server import create_app
from .config import (
    ALLOWED_TARGET_NUMBER,
    assert_allowed_target,
    resolve_artifact_output_path,
    resolve_output_path,
    secret_status,
    validate_transcription_input,
)
from .groq_client import transcribe_audio
from .scenarios import find_scenario, load_scenarios
from .simulator import simulate_call
from .twilio_client import build_dial_request, create_outbound_call, download_call_recording
from .twiml import build_voice_twiml
from .submission import validate_campaign, validate_final_readiness, write_evidence_manifest

app = typer.Typer(help="Pretty Good AI voice QA harness.")
console = Console()


@app.command("env-check")
def env_check() -> None:
    """Show required/optional secret presence without printing values."""
    table = Table("Key", "Present")
    for status in secret_status():
        table.add_row(status.key, str(status.present))
    console.print(table)


@app.command("guard")
def guard(number: str = typer.Argument(...)) -> None:
    """Verify the target number guardrail."""
    try:
        normalized = assert_allowed_target(number)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Allowed target: {normalized}")


@app.command("scenarios")
def scenarios() -> None:
    """List available scenario IDs."""
    table = Table("ID", "Category", "Severity", "Title")
    for scenario in load_scenarios():
        table.add_row(scenario.id, scenario.category, scenario.expected_severity, scenario.title)
    console.print(table)


@app.command("simulate")
def simulate(
    scenario_id: str | None = typer.Option(None, "--scenario", "-s"),
    all_scenarios: bool = typer.Option(False, "--all"),
    count: int = typer.Option(3, "--count", "-n"),
    output: Path = typer.Option(Path("artifacts/local_sim"), "--output", "-o"),
    clean: bool = typer.Option(True, "--clean/--append", help="Remove previous generated calls before writing."),
) -> None:
    """Run free local text simulation and generate artifacts."""
    try:
        output = resolve_artifact_output_path(output)
        scenarios_to_run = load_scenarios()
        if scenario_id:
            scenarios_to_run = [find_scenario(scenario_id)]
        elif not all_scenarios:
            scenarios_to_run = scenarios_to_run[:count]
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    calls = [simulate_call(scenario, index + 1) for index, scenario in enumerate(scenarios_to_run)]
    for call in calls:
        write_call_artifacts(call, output)
    write_index(calls, output)
    write_bug_report(calls, output)
    console.print(f"Wrote {len(calls)} simulated call artifact(s) under {output}")


@app.command("transcribe")
def transcribe(
    audio: Path = typer.Argument(..., exists=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Transcribe an audio file with Groq. No real phone call is made."""
    try:
        audio = validate_transcription_input(audio)
        if output:
            output = resolve_artifact_output_path(output)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print("Uploading local audio to Groq for transcription. Secret values will not be printed.")
    result = transcribe_audio(audio)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result)
        console.print(f"Wrote transcript JSON: {output}")
    else:
        console.print(result)


@app.command("status")
def status() -> None:
    """Show current free/local readiness."""
    console.print(f"Allowed assessment target: {ALLOWED_TARGET_NUMBER}")
    console.print("Local simulator: ready")
    console.print("Call server: ready for mock mode")
    console.print("Real calls: blocked until explicit --yes-i-approve-real-call")


@app.command("twiml")
def twiml(
    public_base_url: str = typer.Option(..., "--public-base-url"),
    scenario_id: str = typer.Option("weekend_closed", "--scenario", "-s"),
    mode: str = typer.Option("mock", "--mode", help="Retained for CLI compatibility; server mode is process-local."),
) -> None:
    """Render Twilio TwiML for a scenario media stream."""
    try:
        body = build_voice_twiml(public_base_url, scenario_id, mode=mode)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(body)


@app.command("server")
def server(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    public_base_url: str = typer.Option("https://example.com", "--public-base-url"),
    output: Path = typer.Option(Path("artifacts/call_streams"), "--output", "-o"),
    mode: str = typer.Option("mock", "--mode", help="mock or openai"),
    allow_unsigned_webhooks: bool = typer.Option(
        False,
        "--allow-unsigned-webhooks",
        help="Local testing only. Do not use when exposing the server publicly.",
    ),
) -> None:
    """Run the Twilio media-stream server locally."""
    if mode not in {"mock", "openai"}:
        raise typer.BadParameter("mode must be mock or openai")
    try:
        app_instance = create_app(
            public_base_url=public_base_url,
            output_dir=output,
            mode=mode,
            require_twilio_auth=not allow_unsigned_webhooks,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    import uvicorn

    uvicorn.run(app_instance, host=host, port=port)


@app.command("dial")
def dial(
    public_base_url: str = typer.Option(..., "--public-base-url"),
    scenario_id: str = typer.Option("weekend_closed", "--scenario", "-s"),
    to_number: str = typer.Option(ALLOWED_TARGET_NUMBER, "--to"),
    yes_i_approve_real_call: bool = typer.Option(
        False,
        "--yes-i-approve-real-call",
        help="Actually place the Twilio call. Without this flag, dial is a dry-run.",
    ),
    time_limit_seconds: int = typer.Option(
        180,
        "--time-limit-seconds",
        help="Hard Twilio call duration limit. Use 0 only when a trial account rejects TimeLimit.",
    ),
    record_call: bool = typer.Option(False, "--record-call", help="Ask Twilio to record the whole call."),
) -> None:
    """Prepare or place a guarded Twilio outbound call."""
    try:
        find_scenario(scenario_id)
        request = build_dial_request(
            scenario_id=scenario_id,
            public_base_url=public_base_url,
            to_number=to_number,
            dry_run=not yes_i_approve_real_call,
            time_limit_seconds=time_limit_seconds,
            record_call=record_call,
        )
        call_sid = create_outbound_call(request)
    except (ValueError, RuntimeError, KeyError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if request.dry_run:
        console.print("Dry run only. No call was placed.")
        console.print(f"Target: {request.to_number}")
        console.print(f"From number present: {bool(request.from_number)}")
        console.print(f"Webhook: {request.webhook_url}")
        console.print(f"Time limit: {request.time_limit_seconds}s")
        console.print(f"Record call: {request.record_call}")
    else:
        console.print(f"Placed call SID: {call_sid}")
        if request.record_call:
            console.print("Recording requested. Download it after completion with voiceqa recording.")


@app.command("recording")
def recording(
    call_sid: str = typer.Argument(...),
    output: Path = typer.Option(Path("artifacts/recordings"), "--output", "-o"),
    wait_seconds: int = typer.Option(90, "--wait-seconds"),
) -> None:
    """Download the completed Twilio recording for a call."""
    try:
        result = download_call_recording(call_sid, output_dir=output, wait_seconds=wait_seconds)
    except (ValueError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Recording SID: {result.recording_sid}")
    console.print(f"Status: {result.status}")
    console.print(f"Duration: {result.duration_seconds or 'unknown'}s")
    console.print(f"Wrote: {result.path}")


@app.command("validate-submission")
def validate_submission(
    root: Path = typer.Option(Path("artifacts/campaign_20260705"), "--root"),
) -> None:
    """Validate the final campaign artifact package."""
    result = validate_campaign(root)
    table = Table("Metric", "Count")
    for key, value in result.summary.items():
        table.add_row(key, str(value))
    console.print(table)
    if result.issues:
        for issue in result.issues:
            console.print(f"[red]ISSUE[/red] {issue}")
        raise typer.Exit(code=1)
    console.print("Submission artifact validation passed.")


@app.command("evidence-manifest")
def evidence_manifest(
    root: Path = typer.Option(Path("artifacts/campaign_20260705"), "--root"),
    output: Path = typer.Option(Path("EVIDENCE_MANIFEST.md"), "--output", "-o"),
) -> None:
    """Write a hash-and-duration manifest for the final evidence package."""
    try:
        path = write_evidence_manifest(root=root, output=output)
    except (ValueError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(f"Wrote evidence manifest: {path}")


@app.command("final-check")
def final_check(
    root: Path = typer.Option(Path("artifacts/campaign_20260705"), "--root"),
) -> None:
    """Validate artifact package plus final external submission links."""
    result = validate_final_readiness(root)
    table = Table("Metric", "Count")
    for key, value in result.summary.items():
        table.add_row(key, str(value))
    console.print(table)
    if result.issues:
        for issue in result.issues:
            console.print(f"[red]ISSUE[/red] {issue}")
        raise typer.Exit(code=1)
    console.print("Final submission readiness check passed.")


if __name__ == "__main__":
    app()
