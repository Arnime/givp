"""Synthetic polynomial level and power curves."""

from __future__ import annotations

import numpy as np

from givp.examples.synthetic_hydropower.model.config import (
    WATER_POWER_FACTOR_MW,
    PlantConfig,
)


def upstream_level(plant: PlantConfig, volume_hm3: float) -> float:
    """Return upstream level from a normalized full-range quartic polynomial."""
    normalized_volume = (volume_hm3 - plant.min_volume_hm3) / (
        plant.maximorum_volume_hm3 - plant.min_volume_hm3
    )
    normalized_level = float(
        np.polynomial.polynomial.polyval(
            normalized_volume, plant.upstream_level_coefficients
        )
    )
    return float(
        plant.min_level_m
        + normalized_level * (plant.maximorum_level_m - plant.min_level_m)
    )


def downstream_level(plant: PlantConfig, defluent_flow_m3s: float) -> float:
    """Return downstream level from normalized-defluence quartic coefficients."""
    normalized_defluence = max(0.0, defluent_flow_m3s / plant.max_flow_m3s)
    normalized_level = float(
        np.polynomial.polynomial.polyval(
            normalized_defluence, plant.downstream_level_coefficients
        )
    )
    return float(
        plant.downstream_base_level_m
        + plant.downstream_level_range_m * normalized_level
    )


def power_from_flow(
    plant: PlantConfig,
    upstream_level_m: float,
    turbine_flow_m3s: float,
    spill_flow_m3s: float,
) -> float:
    """Calculate power for one feasible turbine flow and total spill."""
    net_head_m = max(
        0.0,
        upstream_level_m - downstream_level(plant, turbine_flow_m3s + spill_flow_m3s),
    )
    return float(
        WATER_POWER_FACTOR_MW * plant.efficiency * net_head_m * turbine_flow_m3s
    )
