"""Canonical factorial power cases for the deterministic benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.model import CascadeConfig, PlantConfig

POWER_LEVEL_FRACTIONS: tuple[tuple[str, float | None], ...] = (
    ("off", None),
    ("minimum", 0.0),
    ("quarter", 0.25),
    ("half", 0.50),
    ("three_quarters", 0.75),
    ("maximum", 1.0),
)


@dataclass(frozen=True)
class PowerCase:
    """One 24-hour constant-power combination for both plants."""

    case_id: str
    scenario: str
    level_a: str
    level_b: str
    target_power_mw: NDArray[np.float64]


def power_levels(plant: PlantConfig) -> dict[str, float]:
    """Return the six canonical target levels for one plant."""
    span = plant.max_power_mw - plant.min_power_mw
    return {
        name: 0.0 if fraction is None else plant.min_power_mw + fraction * span
        for name, fraction in POWER_LEVEL_FRACTIONS
    }


def build_power_cases(cascade: CascadeConfig, scenario: str) -> tuple[PowerCase, ...]:
    """Build the full 6-by-6 factorial matrix for one inflow scenario."""
    levels_a = power_levels(cascade.plants[0])
    levels_b = power_levels(cascade.plants[1])
    cases = []
    for (label_a, power_a), (label_b, power_b) in product(
        levels_a.items(), levels_b.items()
    ):
        target = np.vstack(
            (
                np.full(cascade.periods, power_a, dtype=np.float64),
                np.full(cascade.periods, power_b, dtype=np.float64),
            )
        )
        cases.append(
            PowerCase(
                case_id=f"{scenario}__a_{label_a}__b_{label_b}",
                scenario=scenario,
                level_a=label_a,
                level_b=label_b,
                target_power_mw=target,
            )
        )
    return tuple(cases)
