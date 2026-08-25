"""Versioned protocol loading for the deterministic hydropower benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from givp.examples.synthetic_hydropower.model import CascadeConfig, PlantConfig
from givp.examples.synthetic_hydropower.scenarios import ScenarioDefinition


@dataclass(frozen=True)
class FrozenScenario:
    """A versioned synthetic inflow scenario and its generation seed."""

    definition: ScenarioDefinition
    seed: int


@dataclass(frozen=True)
class DeterministicDefinition:
    """Parsed v1.1 protocol, independent from optimizer configuration."""

    benchmark_id: str
    cascade: CascadeConfig
    scenarios: tuple[FrozenScenario, ...]
    decimal_places: int
    comparison_tolerance: float


def load_deterministic_definition(
    config_path: Path, definition_path: Path
) -> DeterministicDefinition:
    """Load plant data and the separately versioned deterministic protocol."""
    config_payload: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    definition: dict[str, Any] = json.loads(
        definition_path.read_text(encoding="utf-8")
    )
    plants = tuple(PlantConfig(**plant) for plant in config_payload["plants"])
    if len(plants) != 2:
        raise ValueError("exactly two plants are required")
    cascade_payload = definition["cascade"]
    cascade = CascadeConfig(plants=(plants[0], plants[1]), **cascade_payload)
    scenarios = tuple(
        FrozenScenario(
            definition=ScenarioDefinition(
                name=item["name"],
                inflow_a_m3s=item["upstream_base"],
                inflow_b_m3s=item["downstream_base"],
                variability=item["variability"],
                profile=item["profile"],
            ),
            seed=item["seed"],
        )
        for item in definition["scenarios"]
    )
    output = definition["canonical_output"]
    return DeterministicDefinition(
        benchmark_id=definition["benchmark_id"],
        cascade=cascade,
        scenarios=scenarios,
        decimal_places=output["decimal_places"],
        comparison_tolerance=output["comparison_tolerance"],
    )
