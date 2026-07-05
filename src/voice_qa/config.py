from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ALLOWED_TARGET_NUMBER = "+18054398008"
MAX_GROQ_FREE_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".ogg", ".wav", ".webm"}

SECRET_ALIASES = {
    "groq_api_key": ("GROQ_API_KEY", "groq_api_key", "GROQ_API_KEY".lower()),
    "hf_token": ("HF_TOKEN", "HF_token", "HUGGING_FACE_HUB_TOKEN", "hf_token"),
    "openai_api_key": ("OPENAI_API_KEY", "openai_api_key"),
    "twilio_account_sid": ("TWILIO_ACCOUNT_SID", "twilio_account_sid", "twilio_SID"),
    "twilio_auth_token": ("TWILIO_AUTH_TOKEN", "twilio_auth_token", "twilio_ClientSecret"),
    "twilio_api_key_sid": ("TWILIO_API_KEY_SID", "twilio_api_key_sid", "twilio_ClientID"),
    "twilio_from_number": (
        "TWILIO_FROM_NUMBER",
        "twilio_from_number",
        "twilio_FromNumber",
        "twilio_number",
        "twilio_trial_number",
        "twilio_trail_number",
    ),
}


@dataclass(frozen=True)
class EnvStatus:
    key: str
    present: bool


def load_env(root: Path | None = None, include_process_env: bool = False) -> dict[str, str]:
    project_root = (root or Path.cwd()).resolve()
    values: dict[str, str] = {}
    env_path = project_root / ".env"
    if env_path.exists():
        for key, value in dotenv_values(env_path).items():
            if value is not None:
                values[key] = value
    if include_process_env:
        values.update({key: value for key, value in os.environ.items() if value})
    return values


def get_secret(canonical_name: str, root: Path | None = None, include_process_env: bool = False) -> str | None:
    values = load_env(root, include_process_env=include_process_env)
    for alias in SECRET_ALIASES[canonical_name]:
        value = values.get(alias)
        if value:
            return value
    return None


def secret_status(root: Path | None = None, include_process_env: bool = False) -> list[EnvStatus]:
    values = load_env(root, include_process_env=include_process_env)
    statuses: list[EnvStatus] = []
    for canonical, aliases in SECRET_ALIASES.items():
        value = next((values.get(alias) for alias in aliases if values.get(alias)), "")
        statuses.append(EnvStatus(canonical, bool(value)))
    return statuses


def normalize_phone(number: str) -> str:
    stripped = "".join(ch for ch in number if ch.isdigit() or ch == "+")
    if stripped.startswith("+"):
        return "+" + "".join(ch for ch in stripped[1:] if ch.isdigit())
    digits = "".join(ch for ch in stripped if ch.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}" if digits else ""


def assert_allowed_target(number: str) -> str:
    normalized = normalize_phone(number)
    if normalized != ALLOWED_TARGET_NUMBER:
        raise ValueError(f"Refusing to call {normalized or '<empty>'}; only {ALLOWED_TARGET_NUMBER} is allowed.")
    return normalized


def resolve_workspace_path(path: Path, root: Path | None = None, *, must_exist: bool = False) -> Path:
    project_root = (root or Path.cwd()).resolve()
    candidate = path if path.is_absolute() else project_root / path
    resolved = candidate.resolve(strict=must_exist)
    if not is_relative_to(resolved, project_root):
        raise ValueError(f"Path must stay inside workspace: {path}")
    return resolved


def resolve_output_path(path: Path, root: Path | None = None) -> Path:
    return resolve_workspace_path(path, root, must_exist=False)


def resolve_artifact_output_path(path: Path, root: Path | None = None) -> Path:
    project_root = (root or Path.cwd()).resolve()
    resolved = resolve_workspace_path(path, project_root, must_exist=False)
    artifacts_root = (project_root / "artifacts").resolve()
    if resolved == project_root:
        raise ValueError("Output path may not be the workspace root.")
    if not is_relative_to(resolved, artifacts_root):
        raise ValueError("Output path must stay under artifacts/ in this workspace.")
    if resolved.name in {".env", ".env.local"}:
        raise ValueError("Output path may not overwrite environment files.")
    return resolved


def validate_transcription_input(path: Path, root: Path | None = None) -> Path:
    project_root = (root or Path.cwd()).resolve()
    resolved = resolve_workspace_path(path, project_root, must_exist=True)
    allowed_roots = [project_root / "artifacts", project_root / "recordings"]
    if not any(is_relative_to(resolved, allowed.resolve()) for allowed in allowed_roots if allowed.exists()):
        raise ValueError("Transcription input must be under artifacts/ or recordings/ in this workspace.")
    if resolved.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio extension: {resolved.suffix}")
    size = resolved.stat().st_size
    if size <= 0:
        raise ValueError("Audio file is empty.")
    if size > MAX_GROQ_FREE_UPLOAD_BYTES:
        raise ValueError("Audio file exceeds Groq free-tier upload guardrail of 25 MB.")
    return resolved


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
