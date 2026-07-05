from __future__ import annotations

import base64
import math
import json
import shutil
import struct
import warnings
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator
from typer.testing import CliRunner

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning, message="'audioop' is deprecated.*")
    import audioop

from voice_qa.audio import (
    StreamingAudioConverter,
    openai_pcm24_to_twilio_payload,
    silence_openai_pcm24,
    silence_twilio_payload,
    twilio_payload_to_openai_pcm24,
)
from voice_qa.call_server import create_app, create_stream_token, twilio_media_openai_message, validate_stream_token
from voice_qa.cli import app
from voice_qa.realtime import (
    RealtimeConfig,
    append_twilio_media_event,
    initial_response_event,
    queue_events,
    session_update_event,
    twilio_media_message,
)
from voice_qa.scenarios import find_scenario
from voice_qa.twilio_client import build_dial_request, download_call_recording
from voice_qa.twiml import build_stream_url, build_voice_twiml


def write_twilio_env(root: Path) -> None:
    (root / ".env").write_text(
        "\n".join(
            [
                "twilio_SID=AC00000000000000000000000000000000",
                "twilio_ClientSecret=test_auth_token",
                "twilio_trail_number=+15551234567",
                "openai_api_key=sk-test",
            ]
        )
        + "\n"
    )


def test_twiml_uses_bidirectional_wss_stream_and_custom_parameters() -> None:
    body = build_voice_twiml("https://public.example.com/base", "weekend_closed", mode="mock", token="signed")
    assert "<Connect>" in body
    assert 'url="wss://public.example.com/twilio/media"' in body
    assert "twilio/media?" not in body
    assert 'name="scenario_id" value="weekend_closed"' in body
    assert 'name="mode" value="mock"' in body
    assert 'name="token" value="signed"' in body
    assert "http://" not in body


def test_stream_url_rejects_non_tls_public_url() -> None:
    try:
        build_stream_url("http://localhost:8765")
    except ValueError as exc:
        assert "https:// or wss://" in str(exc)
    else:
        raise AssertionError("non-TLS public stream URL should be rejected")


def test_audio_codecs_round_trip_base64_shapes() -> None:
    twilio_payload = silence_twilio_payload(40)
    openai_payload = twilio_payload_to_openai_pcm24(twilio_payload)
    assert abs(len(base64.b64decode(openai_payload)) - (40 * 24 * 2)) <= 4
    recovered = openai_pcm24_to_twilio_payload(openai_payload)
    assert abs(len(base64.b64decode(recovered)) - (40 * 8)) <= 2


def test_streaming_audio_converter_matches_one_shot_for_chunked_tone() -> None:
    pcm8 = b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * sample / 8000))) for sample in range(1600)
    )
    mulaw = audioop.lin2ulaw(pcm8, 2)
    one_shot = base64.b64decode(twilio_payload_to_openai_pcm24(base64.b64encode(mulaw).decode("ascii")))
    converter = StreamingAudioConverter()
    chunks = [
        base64.b64decode(
            converter.twilio_payload_to_openai_pcm24(base64.b64encode(mulaw[index : index + 160]).decode("ascii"))
        )
        for index in range(0, len(mulaw), 160)
    ]
    chunked = b"".join(chunks)
    assert abs(len(chunked) - len(one_shot)) <= 4
    assert chunked[: min(len(chunked), len(one_shot)) - 4] == one_shot[: min(len(chunked), len(one_shot)) - 4]


def test_realtime_session_events_are_scenario_specific() -> None:
    scenario = find_scenario("urgent_symptoms")
    event = session_update_event(scenario, RealtimeConfig(model="gpt-realtime-2", voice="marin"))
    assert event["type"] == "session.update"
    assert event["session"]["model"] == "gpt-realtime-2"
    assert event["session"]["output_modalities"] == ["audio"]
    assert event["session"]["audio"]["input"]["format"]["rate"] == 24000
    assert "urgent" in event["session"]["instructions"].lower()
    opening = initial_response_event(scenario)
    assert scenario.opening in opening["response"]["instructions"]
    assert opening["response"]["output_modalities"] == ["audio"]
    assert "modalities" not in opening["response"]


def test_realtime_media_event_mapping() -> None:
    twilio_payload = silence_twilio_payload(20)
    append_event = append_twilio_media_event(twilio_payload)
    assert append_event["type"] == "input_audio_buffer.append"
    assert abs(len(base64.b64decode(append_event["audio"])) - (20 * 24 * 2)) <= 4
    outbound = twilio_media_message("MZ123", silence_openai_pcm24(20))
    assert outbound["event"] == "media"
    assert outbound["streamSid"] == "MZ123"
    assert len(base64.b64decode(outbound["media"]["payload"])) == 20 * 8


def test_dial_dry_run_is_guarded_and_does_not_place_call(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    request = build_dial_request(
        scenario_id="weekend_closed",
        public_base_url="https://public.example.com",
        to_number="805-439-8008",
        dry_run=True,
    )
    assert request.dry_run is True
    assert request.to_number == "+18054398008"
    assert request.webhook_url.endswith("/twilio/voice?scenario=weekend_closed")
    assert request.time_limit_seconds == 180
    assert request.record_call is False
    try:
        build_dial_request(
            scenario_id="weekend_closed",
            public_base_url="https://public.example.com",
            to_number="+18054398009",
        )
    except ValueError as exc:
        assert "only +18054398008" in str(exc)
    else:
        raise AssertionError("dial should reject every target except assessment number")


def test_recording_download_rejects_invalid_call_sid_before_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    try:
        download_call_recording("../bad", output_dir=Path("artifacts/recordings"))
    except ValueError as exc:
        assert "CallSid" in str(exc)
    else:
        raise AssertionError("recording download should reject unsafe call SIDs")


def test_cli_dial_dry_run_redacts_secret_values(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "dial",
            "--public-base-url",
            "https://public.example.com",
            "--scenario",
            "weekend_closed",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Dry run only" in result.output
    assert "test_auth_token" not in result.output
    assert "AC00000000000000000000000000000000" not in result.output


def test_call_server_health_twiml_and_websocket_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "artifacts" / "test_call_stack"
    if output.exists():
        shutil.rmtree(output)
    app_instance = create_app(
        public_base_url="https://public.example.com",
        output_dir=output,
        mode="mock",
        require_twilio_auth=False,
    )
    client = TestClient(app_instance)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "mode": "mock"}
    twiml = client.post("/twilio/voice?scenario=weekend_closed&mode=openai")
    assert twiml.status_code == 200
    assert "application/xml" in twiml.headers["content-type"]
    assert "<Stream" in twiml.text
    assert "mode=\"openai\"" not in twiml.text

    with client.websocket_connect("/twilio/media") as websocket:
        websocket.send_json(
            {
                "event": "start",
                "start": {
                    "callSid": "CA_test",
                    "streamSid": "MZ_test",
                    "customParameters": {"scenario_id": "weekend_closed", "mode": "openai"},
                },
            }
        )
        first = websocket.receive_json()
        second = websocket.receive_json()
        assert first["event"] == "media"
        assert second["event"] == "mark"
        websocket.send_json({"event": "media", "streamSid": "MZ_test", "media": {"track": "inbound", "chunk": "1"}})
        websocket.send_json({"event": "stop", "streamSid": "MZ_test"})

    events = output / "CA_test" / "events.jsonl"
    rows = [json.loads(line) for line in events.read_text().splitlines()]
    assert [row["event"] for row in rows] == ["start", "media", "stop"]
    assert rows[0]["scenario_id"] == "weekend_closed"


def test_call_server_rejects_unsigned_twilio_voice_by_default(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "artifacts" / "test_call_stack_auth"
    if output.exists():
        shutil.rmtree(output)
    app_instance = create_app(public_base_url="https://public.example.com", output_dir=output, mode="mock")
    client = TestClient(app_instance)
    response = client.post("/twilio/voice?scenario=weekend_closed", data={"To": "+18054398008"})
    assert response.status_code == 403


def test_call_server_voice_endpoint_is_post_only(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "artifacts" / "test_call_stack_get"
    app_instance = create_app(public_base_url="https://public.example.com", output_dir=output, mode="mock")
    client = TestClient(app_instance)
    response = client.get("/twilio/voice?scenario=weekend_closed&To=%2B18054398008&CallSid=CA_get")
    assert response.status_code == 405


def test_call_server_accepts_signed_twilio_voice_and_stream_token(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "artifacts" / "test_call_stack_signed"
    if output.exists():
        shutil.rmtree(output)
    app_instance = create_app(public_base_url="https://public.example.com", output_dir=output, mode="mock")
    client = TestClient(app_instance)
    params = {"scenario": "weekend_closed"}
    form = {"To": "+18054398008", "CallSid": "CA" + "1" * 32}
    url = "https://public.example.com/twilio/voice?" + urlencode(params)
    signature = RequestValidator("test_auth_token").compute_signature(url, form)
    response = client.post(
        "/twilio/voice?" + urlencode(params),
        data=form,
        headers={"X-Twilio-Signature": signature},
    )
    assert response.status_code == 200, response.text
    assert 'name="token"' in response.text


def test_call_server_rejects_signed_voice_without_valid_call_sid(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    app_instance = create_app(public_base_url="https://public.example.com", mode="mock")
    client = TestClient(app_instance)
    params = {"scenario": "weekend_closed"}
    form = {"To": "+18054398008"}
    url = "https://public.example.com/twilio/voice?" + urlencode(params)
    signature = RequestValidator("test_auth_token").compute_signature(url, form)

    response = client.post(
        "/twilio/voice?" + urlencode(params),
        data=form,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 400
    assert "CallSid" in response.text


def test_stream_token_requires_exact_call_sid(tmp_path: Path, monkeypatch) -> None:
    write_twilio_env(tmp_path)
    monkeypatch.chdir(tmp_path)
    call_sid = "CA" + "2" * 32
    other_call_sid = "CA" + "3" * 32
    token = create_stream_token(scenario_id="weekend_closed", mode="mock", call_sid=call_sid)

    validate_stream_token(token, "weekend_closed", "mock", call_sid)
    try:
        validate_stream_token(token, "weekend_closed", "mock", other_call_sid)
    except ValueError as exc:
        assert "call SID mismatch" in str(exc)
    else:
        raise AssertionError("stream token should not replay across call SIDs")

    try:
        create_stream_token(scenario_id="weekend_closed", mode="mock", call_sid="")
    except ValueError as exc:
        assert "CallSid" in str(exc)
    else:
        raise AssertionError("stream token signing should require a call SID")


def test_openai_mode_local_mapping_does_not_require_network() -> None:
    outbound = twilio_media_openai_message("MZ_test")
    assert outbound["event"] == "media"
    assert outbound["streamSid"] == "MZ_test"


def test_openai_media_bridge_forwards_both_directions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "artifacts" / "test_call_stack_openai"
    if output.exists():
        shutil.rmtree(output)

    sockets: list[FakeOpenAIWebSocket] = []

    class FakeBridge:
        def __init__(self, scenario) -> None:
            self.scenario = scenario

        async def connect(self) -> "FakeOpenAIWebSocket":
            socket = FakeOpenAIWebSocket()
            sockets.append(socket)
            return socket

        async def iter_twilio_messages(self, openai_events, stream_sid: str):
            async for event in openai_events:
                if event["type"] == "response.output_audio.delta":
                    yield twilio_media_message(stream_sid, event["delta"])

    app_instance = create_app(
        public_base_url="https://public.example.com",
        output_dir=output,
        mode="openai",
        require_twilio_auth=False,
        bridge_factory=FakeBridge,
    )
    client = TestClient(app_instance)
    with client.websocket_connect("/twilio/media") as websocket:
        websocket.send_json(
            {
                "event": "start",
                "start": {
                    "callSid": "CA_openai",
                    "streamSid": "MZ_openai",
                    "customParameters": {"scenario_id": "weekend_closed"},
                },
            }
        )
        first = websocket.receive_json()
        assert first["event"] == "media"
        websocket.send_json(
            {
                "event": "media",
                "streamSid": "MZ_openai",
                "media": {"track": "inbound", "chunk": "1", "payload": silence_twilio_payload(20)},
            }
        )
        websocket.send_json({"event": "stop", "streamSid": "MZ_openai"})

    assert sockets
    sent = [json.loads(item) for item in sockets[0].sent]
    assert any(item["type"] == "input_audio_buffer.append" for item in sent)
    assert sockets[0].closed is True


def test_queue_events_async_iterator() -> None:
    async def collect() -> list[dict]:
        return [item async for item in queue_events([{"type": "a"}, {"type": "b"}])]

    import asyncio

    assert asyncio.run(collect()) == [{"type": "a"}, {"type": "b"}]


class FakeOpenAIWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False
        self._emitted = False

    async def send(self, item: str) -> None:
        self.sent.append(item)

    def __aiter__(self) -> "FakeOpenAIWebSocket":
        return self

    async def __anext__(self) -> str:
        import asyncio

        if not self._emitted:
            self._emitted = True
            return json.dumps({"type": "response.output_audio.delta", "delta": silence_openai_pcm24(20)})
        await asyncio.sleep(60)
        raise StopAsyncIteration

    async def close(self) -> None:
        self.closed = True
