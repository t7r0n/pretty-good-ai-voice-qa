from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["Critical", "High", "Medium", "Low", "None"]


class Persona(BaseModel):
    name: str
    dob: str
    phone: str
    style: str = "polite, realistic, concise"


class Scenario(BaseModel):
    id: str
    title: str
    category: str
    persona: Persona
    objective: str
    opening: str
    patient_facts: dict[str, str] = Field(default_factory=dict)
    steering_ladder: list[str]
    expected_behavior: list[str]
    bug_probe: str
    expected_bug: str | None = None
    expected_severity: Severity = "None"
    stop_condition: str = "Agent gives a clear next step or call reaches 3 minutes."


@dataclass(frozen=True)
class Turn:
    speaker: Literal["patient", "agent"]
    text: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class SimulatedCall:
    call_id: str
    scenario: Scenario
    turns: list[Turn]
    suspected_bug: str | None
    severity: Severity

    @property
    def duration_seconds(self) -> float:
        return self.turns[-1].end_seconds if self.turns else 0.0


@dataclass(frozen=True)
class ArtifactPaths:
    call_dir: Path
    transcript: Path
    events: Path
    metadata: Path
    bug: Path
