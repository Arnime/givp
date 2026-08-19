"""Synthetic inflow scenario generation for the fictional cascade."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ScenarioDefinition:
    """Parameters controlling one entirely fictional inflow scenario."""

    name: str
    inflow_a_m3s: float
    inflow_b_m3s: float
    variability: float
    profile: str = "daily"


def generate_inflows(
    definition: ScenarioDefinition, periods: int, seed: int
) -> NDArray[np.float64]:
    """Generate non-negative, seeded hourly incremental inflows for plants A and B."""
    if periods < 1:
        raise ValueError("periods must be positive")
    if definition.inflow_a_m3s < 0 or definition.inflow_b_m3s < 0:
        raise ValueError("scenario inflows must be non-negative")
    if definition.variability < 0:
        raise ValueError("variability must be non-negative")

    generator = np.random.default_rng(seed)
    hours = np.arange(periods)
    normalized_hours = hours / max(1, periods - 1)
    profiles = {
        "stable": np.ones(periods),
        "daily": 1.0 + 0.15 * np.sin(2.0 * np.pi * hours / periods),
        "alternating": 1.0 + 0.18 * (-1.0) ** hours,
        "rising": 0.72 + 0.56 * normalized_hours,
        "peak": 0.75 + 0.55 * np.exp(-((normalized_hours - 0.55) / 0.18) ** 2),
    }
    try:
        profile = profiles[definition.profile]
    except KeyError as error:
        raise ValueError(f"unknown scenario profile: {definition.profile}") from error
    base = np.array([[definition.inflow_a_m3s], [definition.inflow_b_m3s]])
    noise = generator.normal(0.0, definition.variability, size=(2, periods))
    return np.asarray(np.maximum(0.0, base * profile * (1.0 + noise)), dtype=np.float64)
