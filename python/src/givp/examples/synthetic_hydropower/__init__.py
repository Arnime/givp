"""Fictional and reproducible two-plant hydropower cascade example."""

from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    PowerScheduleResult,
    SimulationResult,
    simulate_cascade,
    simulate_power_schedule,
)
from givp.examples.synthetic_hydropower.optimization import (
    OptimizationDefinition,
    evaluate_power_vector,
    load_optimization_definition,
    project_power_vector,
)

__all__ = [
    "CascadeConfig",
    "OptimizationDefinition",
    "PlantConfig",
    "PowerScheduleResult",
    "SimulationResult",
    "evaluate_power_vector",
    "load_optimization_definition",
    "project_power_vector",
    "simulate_cascade",
    "simulate_power_schedule",
]
