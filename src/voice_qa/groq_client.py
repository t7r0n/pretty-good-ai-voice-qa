from __future__ import annotations

from pathlib import Path

from .config import get_secret, validate_transcription_input


def transcribe_audio(audio_path: Path, root: Path | None = None, model: str = "whisper-large-v3-turbo") -> str:
    api_key = get_secret("groq_api_key", root)
    if not api_key:
        raise RuntimeError("Missing Groq API key. Set GROQ_API_KEY or groq_api_key in .env.")
    audio_path = validate_transcription_input(audio_path, root)

    from groq import Groq

    client = Groq(api_key=api_key)
    with audio_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            file=audio_file,
            model=model,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json(indent=2)
    return str(result)
