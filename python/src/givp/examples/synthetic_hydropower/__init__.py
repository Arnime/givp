"""Fictional and reproducible two-plant hydropower cascade example."""

from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    PowerScheduleResult,
    SimulationResult,
    simulate_cascade,
    simulate_power_schedule,
)

__all__ = [
    "CascadeConfig",
    "PlantConfig",
    "PowerScheduleResult",
    "SimulationResult",
    "simulate_cascade",
    "simulate_power_schedule",
]
