from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Iterable

import yaml

from .models import Scenario


def default_scenarios_dir(root: Path | None = None) -> Path | None:
    project_root = (root or Path.cwd()).resolve()
    cwd_scenarios = project_root / "scenarios"
    if cwd_scenarios.exists():
        return cwd_scenarios
    source_scenarios = Path(__file__).resolve().parents[2] / "scenarios"
    if source_scenarios.exists():
        return source_scenarios
    return None


def load_scenarios(path: Path | None = None) -> list[Scenario]:
    scenarios_dir = path or default_scenarios_dir()
    scenarios: list[Scenario] = []
    for name, text in _scenario_sources(scenarios_dir):
        data = yaml.safe_load(text) or {}
        scenarios.append(Scenario.model_validate(data))
    if not scenarios:
        location = str(scenarios_dir) if scenarios_dir else "packaged voice_qa/scenario_data"
        raise FileNotFoundError(f"No scenarios found in {location}")
    return scenarios


def find_scenario(scenario_id: str, path: Path | None = None) -> Scenario:
    for scenario in load_scenarios(path):
        if scenario.id == scenario_id:
            return scenario
    raise KeyError(f"Unknown scenario: {scenario_id}")


def _scenario_sources(path: Path | None) -> Iterable[tuple[str, str]]:
    if path is not None:
        for item in sorted(path.glob("*.yaml")):
            yield item.name, item.read_text()
        return
    try:
        scenario_root = resources.files("voice_qa").joinpath("scenario_data")
        for item in sorted(scenario_root.iterdir(), key=lambda value: value.name):
            if item.name.endswith(".yaml"):
                yield item.name, item.read_text()
    except (FileNotFoundError, ModuleNotFoundError):
        return
