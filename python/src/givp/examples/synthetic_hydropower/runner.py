"""Configuration loading and GIVP execution for the synthetic experiment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from givp import GIVPConfig, givp
from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    SimulationResult,
    simulate_cascade,
)
from givp.examples.synthetic_hydropower.scenarios import (
    ScenarioDefinition,
    generate_inflows,
)


@dataclass(frozen=True)
class ExperimentConfig:
    """Parsed configuration for the standalone reproducibility experiment."""

    cascade: CascadeConfig
    scenarios: dict[str, ScenarioDefinition]
    optimizer: dict[str, int]


def load_experiment_config(config_path: Path) -> ExperimentConfig:
    """Load a fictional experiment configuration from an explicit JSON path."""
    payload: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    plants = tuple(PlantConfig(**plant) for plant in payload["plants"])
    if len(plants) != 2:
        raise ValueError("exactly two plants are required")
    cascade = CascadeConfig(
        plants=(plants[0], plants[1]),
        periods=payload["periods"],
        period_hours=payload["period_hours"],
        travel_time_steps=payload["travel_time_steps"],
        level_penalty_weight=payload["level_penalty_weight"],
    )
    scenarios = {
        name: ScenarioDefinition(name=name, **values)
        for name, values in payload["scenarios"].items()
    }
    return ExperimentConfig(
        cascade=cascade, scenarios=scenarios, optimizer=payload["optimizer"]
    )


def optimize_scenario(
    config: ExperimentConfig, scenario_name: str, seed: int
) -> SimulationResult:
    """Optimize fictional turbine requests for a named seeded scenario."""
    try:
        scenario = config.scenarios[scenario_name]
    except KeyError as error:
        raise ValueError(f"unknown scenario: {scenario_name}") from error
    inflows = generate_inflows(scenario, config.cascade.periods, seed)
    bounds = [
        (0.0, plant.max_flow_m3s)
        for plant in config.cascade.plants
        for _ in range(config.cascade.periods)
    ]

    def objective(vector: np.ndarray) -> float:
        requested = vector.reshape(2, config.cascade.periods)
        return simulate_cascade(config.cascade, inflows, requested).objective

    optimizer_config = GIVPConfig(
        max_iterations=config.optimizer["max_iterations"],
        vnd_iterations=config.optimizer["vnd_iterations"],
        ils_iterations=config.optimizer["ils_iterations"],
        use_elite_pool=False,
        use_convergence_monitor=False,
        direction="minimize",
    )
    result = givp(objective, bounds=bounds, config=optimizer_config, seed=seed)
    requested = np.asarray(result.x, dtype=float).reshape(2, config.cascade.periods)
    return simulate_cascade(config.cascade, inflows, requested)
