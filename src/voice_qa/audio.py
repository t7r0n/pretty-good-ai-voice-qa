from __future__ import annotations

import base64
import warnings
from dataclasses import dataclass

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning, message="'audioop' is deprecated.*")
    import audioop

TWILIO_SAMPLE_RATE = 8000
OPENAI_SAMPLE_RATE = 24000
SAMPLE_WIDTH_BYTES = 2


def twilio_payload_to_openai_pcm24(payload: str) -> str:
    """Convert Twilio base64 mu-law/8 kHz audio into base64 PCM16/24 kHz."""
    mulaw = base64.b64decode(payload)
    pcm8 = audioop.ulaw2lin(mulaw, SAMPLE_WIDTH_BYTES)
    pcm24, _ = audioop.ratecv(pcm8, SAMPLE_WIDTH_BYTES, 1, TWILIO_SAMPLE_RATE, OPENAI_SAMPLE_RATE, None)
    return base64.b64encode(pcm24).decode("ascii")


def openai_pcm24_to_twilio_payload(payload: str) -> str:
    """Convert OpenAI base64 PCM16/24 kHz audio into Twilio base64 mu-law/8 kHz."""
    pcm24 = base64.b64decode(payload)
    pcm8, _ = audioop.ratecv(pcm24, SAMPLE_WIDTH_BYTES, 1, OPENAI_SAMPLE_RATE, TWILIO_SAMPLE_RATE, None)
    mulaw = audioop.lin2ulaw(pcm8, SAMPLE_WIDTH_BYTES)
    return base64.b64encode(mulaw).decode("ascii")


@dataclass
class StreamingAudioConverter:
    twilio_to_openai_state: object | None = None
    openai_to_twilio_state: object | None = None

    def twilio_payload_to_openai_pcm24(self, payload: str) -> str:
        mulaw = base64.b64decode(payload)
        pcm8 = audioop.ulaw2lin(mulaw, SAMPLE_WIDTH_BYTES)
        pcm24, self.twilio_to_openai_state = audioop.ratecv(
            pcm8,
            SAMPLE_WIDTH_BYTES,
            1,
            TWILIO_SAMPLE_RATE,
            OPENAI_SAMPLE_RATE,
            self.twilio_to_openai_state,
        )
        return base64.b64encode(pcm24).decode("ascii")

    def openai_pcm24_to_twilio_payload(self, payload: str) -> str:
        pcm24 = base64.b64decode(payload)
        pcm8, self.openai_to_twilio_state = audioop.ratecv(
            pcm24,
            SAMPLE_WIDTH_BYTES,
            1,
            OPENAI_SAMPLE_RATE,
            TWILIO_SAMPLE_RATE,
            self.openai_to_twilio_state,
        )
        mulaw = audioop.lin2ulaw(pcm8, SAMPLE_WIDTH_BYTES)
        return base64.b64encode(mulaw).decode("ascii")


def silence_twilio_payload(milliseconds: int = 20) -> str:
    frame_count = max(1, int(TWILIO_SAMPLE_RATE * milliseconds / 1000))
    # 0xff is mu-law silence.
    return base64.b64encode(b"\xff" * frame_count).decode("ascii")


def silence_openai_pcm24(milliseconds: int = 20) -> str:
    frame_count = max(1, int(OPENAI_SAMPLE_RATE * milliseconds / 1000))
    return base64.b64encode(b"\x00\x00" * frame_count).decode("ascii")
