"""Public façade for the synthetic hydropower physical model."""

from givp.examples.synthetic_hydropower.model.config import (
    CascadeConfig,
    PlantConfig,
    SimulationResult,
)
from givp.examples.synthetic_hydropower.model.simulator import simulate_cascade

__all__ = ["CascadeConfig", "PlantConfig", "SimulationResult", "simulate_cascade"]
