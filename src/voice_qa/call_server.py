from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from twilio.request_validator import RequestValidator

from .audio import StreamingAudioConverter, silence_openai_pcm24, silence_twilio_payload
from .config import assert_allowed_target, get_secret, resolve_artifact_output_path
from .realtime import RealtimeBridge, append_twilio_media_event_streaming, twilio_media_message
from .scenarios import find_scenario
from .twiml import build_voice_twiml

BridgeFactory = Callable[[Any], RealtimeBridge]
CALL_SID_RE = re.compile(r"^CA[a-fA-F0-9]{32}$")


def create_app(
    *,
    public_base_url: str = "https://example.com",
    output_dir: Path = Path("artifacts/call_streams"),
    mode: str = "mock",
    require_twilio_auth: bool = True,
    bridge_factory: BridgeFactory = RealtimeBridge,
) -> FastAPI:
    app = FastAPI(title="Pretty Good Voice QA Call Server")
    artifacts_root = resolve_artifact_output_path(output_dir)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": mode}

    @app.post("/twilio/voice", response_class=PlainTextResponse)
    async def twilio_voice(
        request: Request,
        scenario: str = Query("weekend_closed"),
    ) -> PlainTextResponse:
        body = (await request.body()).decode("utf-8", errors="replace")
        form = {key: values[-1] for key, values in parse_qs(body).items() if values}
        if require_twilio_auth:
            _validate_twilio_request(request, form, public_base_url)
            target = form.get("To") or form.get("Called")
            if target:
                assert_allowed_target(str(target))
            try:
                call_sid = _require_call_sid(form.get("CallSid"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            call_sid = str(form.get("CallSid") or "")
        scenario_id = str(form.get("scenario") or scenario)
        try:
            scenario_obj = find_scenario(scenario_id)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario_id}") from exc
        token = (
            create_stream_token(
                scenario_id=scenario_obj.id,
                mode=mode,
                call_sid=call_sid,
            )
            if require_twilio_auth
            else None
        )
        body = build_voice_twiml(public_base_url, scenario_obj.id, mode=mode, token=token)
        return PlainTextResponse(body, media_type="application/xml")

    @app.websocket("/twilio/media")
    async def twilio_media(
        websocket: WebSocket,
        scenario: str = Query("weekend_closed"),
    ) -> None:
        await websocket.accept()
        session = MediaSession(
            websocket=websocket,
            scenario_id=scenario,
            mode=mode,
            output_root=artifacts_root,
            require_stream_token=require_twilio_auth,
            bridge_factory=bridge_factory,
        )
        await session.run()

    return app


class MediaSession:
    def __init__(
        self,
        *,
        websocket: WebSocket,
        scenario_id: str,
        mode: str,
        output_root: Path,
        require_stream_token: bool,
        bridge_factory: BridgeFactory,
    ) -> None:
        self.websocket = websocket
        self.scenario_id = scenario_id
        self.mode = mode
        self.output_root = output_root
        self.require_stream_token = require_stream_token
        self.bridge_factory = bridge_factory
        self.call_sid = f"local_{int(time.time() * 1000)}"
        self.stream_sid = "unknown"
        self.events_path: Path | None = None
        self.openai_ws: Any | None = None
        self.openai_reader_task: asyncio.Task | None = None
        self.twilio_to_openai_converter = StreamingAudioConverter()

    async def run(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        try:
            while True:
                message = await self.websocket.receive_text()
                data = json.loads(message)
                await self.handle_event(data)
                if data.get("event") == "stop":
                    break
        except WebSocketDisconnect:
            self.write_event({"event": "disconnect"})
        except ValueError as exc:
            self.write_event({"event": "rejected", "reason": str(exc)})
            await self.websocket.close(code=1008)
        finally:
            await self.close_openai()

    async def handle_event(self, data: dict[str, Any]) -> None:
        event = data.get("event")
        if event == "start":
            start = data.get("start") or {}
            self.call_sid = str(start.get("callSid") or self.call_sid)
            self.stream_sid = str(start.get("streamSid") or data.get("streamSid") or self.stream_sid)
            custom = start.get("customParameters") or {}
            self.scenario_id = str(custom.get("scenario_id") or self.scenario_id)
            if self.require_stream_token:
                self.call_sid = _require_call_sid(self.call_sid)
                token = str(custom.get("token") or "")
                validate_stream_token(token, self.scenario_id, self.mode, self.call_sid)
            self.events_path = self._events_path()
            self.write_event({"event": "start", "call_sid": self.call_sid, "stream_sid": self.stream_sid})
            await self.start_media()
        elif event == "media":
            media = data.get("media") or {}
            self.write_event({"event": "media", "track": media.get("track"), "chunk": media.get("chunk")})
            if self.mode == "openai" and self.openai_ws is not None and media.get("payload"):
                await self.openai_ws.send(
                    json.dumps(append_twilio_media_event_streaming(media["payload"], self.twilio_to_openai_converter))
                )
        elif event == "mark":
            self.write_event({"event": "mark", "mark": data.get("mark")})
        elif event == "stop":
            self.write_event({"event": "stop"})
            await self.close_openai()
        else:
            self.write_event({"event": "unknown", "raw_event": event})

    async def start_media(self) -> None:
        if self.mode == "mock":
            await self.websocket.send_json(
                {"event": "media", "streamSid": self.stream_sid, "media": {"payload": silence_twilio_payload(20)}}
            )
            await self.websocket.send_json({"event": "mark", "streamSid": self.stream_sid, "mark": {"name": "mock-ready"}})
            return
        if self.mode != "openai":
            raise ValueError(f"Unsupported media mode: {self.mode}")
        scenario_obj = find_scenario(self.scenario_id)
        bridge = self.bridge_factory(scenario_obj)
        self.openai_ws = await bridge.connect()
        self.openai_reader_task = asyncio.create_task(self.forward_openai_to_twilio(bridge))

    async def forward_openai_to_twilio(self, bridge: RealtimeBridge) -> None:
        if self.openai_ws is None:
            return

        async def events() -> Any:
            async for raw in self.openai_ws:
                yield json.loads(raw) if isinstance(raw, str) else raw

        async for outbound in bridge.iter_twilio_messages(events(), self.stream_sid):
            self.write_event({"event": "openai_outbound", "twilio_event": outbound.get("event")})
            await self.websocket.send_json(outbound)

    async def close_openai(self) -> None:
        if self.openai_reader_task and not self.openai_reader_task.done():
            self.openai_reader_task.cancel()
            try:
                await self.openai_reader_task
            except asyncio.CancelledError:
                pass
        if self.openai_ws is not None:
            close = getattr(self.openai_ws, "close", None)
            if close:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self.openai_ws = None

    def write_event(self, event: dict[str, Any]) -> None:
        path = self.events_path or self._events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        enriched = {"ts": time.time(), "scenario_id": self.scenario_id, **event}
        with path.open("a") as handle:
            handle.write(json.dumps(enriched, sort_keys=True) + "\n")

    def _events_path(self) -> Path:
        safe_call_sid = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in self.call_sid)
        return self.output_root / safe_call_sid / "events.jsonl"


def twilio_media_openai_message(stream_sid: str) -> dict[str, Any]:
    return twilio_media_message(stream_sid, silence_openai_pcm24(20))


def _validate_twilio_request(request: Request, form: dict[str, str], public_base_url: str) -> None:
    auth_token = get_secret("twilio_auth_token")
    if not auth_token:
        raise HTTPException(status_code=403, detail="Twilio auth token is required.")
    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        raise HTTPException(status_code=403, detail="Missing Twilio signature.")
    url = public_base_url.rstrip("/") + request.url.path
    if request.url.query:
        url += f"?{request.url.query}"
    if not RequestValidator(auth_token).validate(url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")


def _require_call_sid(call_sid: str | None) -> str:
    value = str(call_sid or "")
    if not CALL_SID_RE.fullmatch(value):
        raise ValueError("Valid Twilio CallSid is required.")
    return value


def _stream_secret() -> bytes:
    token = get_secret("twilio_auth_token") or get_secret("openai_api_key")
    if not token:
        raise RuntimeError("A local secret is required to sign Twilio stream tokens.")
    return token.encode("utf-8")


def create_stream_token(*, scenario_id: str, mode: str, call_sid: str, ttl_seconds: int = 600) -> str:
    if not CALL_SID_RE.fullmatch(call_sid):
        raise ValueError("Valid Twilio CallSid is required for stream token signing.")
    expires = int(time.time()) + ttl_seconds
    payload = json.dumps(
        {"scenario_id": scenario_id, "mode": mode, "call_sid": call_sid, "expires": expires},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(_stream_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def validate_stream_token(token: str, scenario_id: str, mode: str, call_sid: str) -> None:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid Twilio stream token.") from exc
    expected = hmac.new(_stream_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Invalid Twilio stream token signature.")
    padded = body + "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    if int(payload.get("expires", 0)) < int(time.time()):
        raise ValueError("Expired Twilio stream token.")
    if payload.get("scenario_id") != scenario_id or payload.get("mode") != mode:
        raise ValueError("Twilio stream token does not match this call.")
    token_call_sid = payload.get("call_sid")
    if not CALL_SID_RE.fullmatch(str(call_sid or "")):
        raise ValueError("Valid Twilio CallSid is required.")
    if token_call_sid != call_sid:
        raise ValueError("Twilio stream token call SID mismatch.")
