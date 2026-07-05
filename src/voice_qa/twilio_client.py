from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from .config import ALLOWED_TARGET_NUMBER, assert_allowed_target, get_secret, normalize_phone, resolve_artifact_output_path
from .scenarios import find_scenario

CALL_SID_RE = re.compile(r"^CA[a-fA-F0-9]{32}$")
RECORDING_SID_RE = re.compile(r"^RE[a-fA-F0-9]{32}$")


@dataclass(frozen=True)
class TwilioSettings:
    account_sid: str
    auth_token: str
    from_number: str


@dataclass(frozen=True)
class DialRequest:
    to_number: str
    from_number: str
    webhook_url: str
    scenario_id: str
    dry_run: bool
    time_limit_seconds: int
    record_call: bool


def load_twilio_settings() -> TwilioSettings:
    account_sid = get_secret("twilio_account_sid")
    auth_token = get_secret("twilio_auth_token")
    from_number = get_secret("twilio_from_number")
    missing = [
        name
        for name, value in (
            ("twilio_account_sid", account_sid),
            ("twilio_auth_token", auth_token),
            ("twilio_from_number", from_number),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Twilio setting(s): {', '.join(missing)}")
    return TwilioSettings(account_sid=account_sid, auth_token=auth_token, from_number=normalize_phone(from_number))


def build_dial_request(
    *,
    scenario_id: str,
    public_base_url: str,
    to_number: str = ALLOWED_TARGET_NUMBER,
    dry_run: bool = True,
    time_limit_seconds: int = 180,
    record_call: bool = False,
) -> DialRequest:
    target = assert_allowed_target(to_number)
    scenario = find_scenario(scenario_id)
    settings = load_twilio_settings()
    parsed = urlparse(public_base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("public_base_url must be an externally reachable https:// URL for Twilio.")
    if parsed.query or parsed.fragment:
        raise ValueError("public_base_url may not contain query or fragment.")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"} or parsed.hostname.endswith(".local"):
        raise ValueError("public_base_url must not point at localhost for a Twilio call.")
    try:
        address = ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError("public_base_url must be publicly reachable for a Twilio call.")
    if time_limit_seconds != 0 and not 15 <= time_limit_seconds <= 600:
        raise ValueError("time_limit_seconds must be 0 or between 15 and 600.")
    webhook_url = urlunparse((parsed.scheme, parsed.netloc, "/twilio/voice", "", urlencode({"scenario": scenario.id}), ""))
    return DialRequest(
        to_number=target,
        from_number=settings.from_number,
        webhook_url=webhook_url,
        scenario_id=scenario_id,
        dry_run=dry_run,
        time_limit_seconds=time_limit_seconds,
        record_call=record_call,
    )


def create_outbound_call(request: DialRequest) -> str:
    if request.dry_run:
        return "dry-run"
    settings = load_twilio_settings()
    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client

    client = Client(settings.account_sid, settings.auth_token)
    kwargs = {"to": request.to_number, "from_": request.from_number, "url": request.webhook_url}
    if request.time_limit_seconds:
        kwargs["time_limit"] = request.time_limit_seconds
    if request.record_call:
        kwargs["record"] = True
    try:
        call = client.calls.create(**kwargs)
    except TwilioRestException as exc:
        raise RuntimeError(f"Twilio refused to create the call: {exc.msg}") from exc
    return str(call.sid)


@dataclass(frozen=True)
class RecordingDownload:
    recording_sid: str
    call_sid: str
    status: str
    duration_seconds: str | None
    path: Path


def download_call_recording(
    call_sid: str,
    output_dir: Path = Path("artifacts/recordings"),
    *,
    wait_seconds: int = 90,
    poll_interval_seconds: int = 5,
) -> RecordingDownload:
    if not CALL_SID_RE.fullmatch(call_sid):
        raise ValueError("call_sid must be a valid Twilio CallSid.")
    settings = load_twilio_settings()
    from twilio.rest import Client

    client = Client(settings.account_sid, settings.auth_token)
    deadline = time.time() + wait_seconds
    recordings = []
    while time.time() <= deadline:
        recordings = client.recordings.list(call_sid=call_sid, limit=5)
        completed = [recording for recording in recordings if getattr(recording, "status", "") == "completed"]
        if completed:
            recording = completed[0]
            break
        time.sleep(poll_interval_seconds)
    else:
        if not recordings:
            raise RuntimeError(f"No recording is available yet for call {call_sid}.")
        statuses = ", ".join(str(getattr(recording, "status", "unknown")) for recording in recordings)
        raise RuntimeError(f"Recording is not completed yet for call {call_sid}; status: {statuses}.")

    resolved_dir = resolve_artifact_output_path(output_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    recording_sid = str(recording.sid)
    if not RECORDING_SID_RE.fullmatch(recording_sid):
        raise RuntimeError("Twilio returned an invalid recording SID.")
    path = resolved_dir / f"{call_sid}_{recording_sid}.mp3"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.account_sid}/Recordings/{recording_sid}.mp3"
    request = Request(url)
    credentials = f"{settings.account_sid}:{settings.auth_token}".encode("utf-8")
    import base64

    request.add_header("Authorization", f"Basic {base64.b64encode(credentials).decode('ascii')}")
    try:
        with urlopen(request, timeout=30) as response:
            path.write_bytes(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"Twilio recording download failed with HTTP {exc.code}.") from exc
    if path.stat().st_size <= 0:
        raise RuntimeError("Downloaded recording is empty.")
    return RecordingDownload(
        recording_sid=recording_sid,
        call_sid=call_sid,
        status=str(recording.status),
        duration_seconds=str(getattr(recording, "duration", "") or "") or None,
        path=path,
    )
