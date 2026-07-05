from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from twilio.twiml.voice_response import Connect, Parameter, Stream, VoiceResponse

from .scenarios import find_scenario


def build_stream_url(public_base_url: str) -> str:
    parsed = urlparse(public_base_url)
    if parsed.scheme not in {"https", "wss"} or not parsed.netloc:
        raise ValueError("Twilio stream URL must use https:// or wss:// with a public host.")
    if parsed.query or parsed.fragment:
        raise ValueError("Twilio public base URL may not contain query or fragment.")
    scheme = "wss" if parsed.scheme == "https" else parsed.scheme
    return urlunparse((scheme, parsed.netloc, "/twilio/media", "", "", ""))


def build_voice_twiml(
    public_base_url: str,
    scenario_id: str,
    *,
    mode: str = "mock",
    token: str | None = None,
) -> str:
    scenario = find_scenario(scenario_id)
    stream_url = build_stream_url(public_base_url)
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=stream_url)
    stream.append(Parameter(name="scenario_id", value=scenario.id))
    stream.append(Parameter(name="mode", value=mode))
    stream.append(Parameter(name="scenario_title", value=scenario.title[:500]))
    if token:
        stream.append(Parameter(name="token", value=token))
    connect.append(stream)
    response.append(connect)
    return str(response)
