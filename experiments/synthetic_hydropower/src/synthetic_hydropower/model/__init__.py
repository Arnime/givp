"""Public façade for the synthetic hydropower physical model."""

from synthetic_hydropower.model.config import (
    CascadeConfig,
    PlantConfig,
    SimulationResult,
)
from synthetic_hydropower.model.simulator import simulate_cascade

__all__ = ["CascadeConfig", "PlantConfig", "SimulationResult", "simulate_cascade"]
