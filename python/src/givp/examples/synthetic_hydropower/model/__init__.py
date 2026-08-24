"""Public façade for the synthetic hydropower physical model."""

from givp.examples.synthetic_hydropower.model.config import (
    CascadeConfig,
    PlantConfig,
    PowerScheduleResult,
    SimulationResult,
)
from givp.examples.synthetic_hydropower.model.simulator import (
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
