"""Turbine dispatch and spill-control rules."""

from __future__ import annotations

import numpy as np

from givp.examples.synthetic_hydropower.model.config import (
    WATER_POWER_FACTOR_MW,
    PlantConfig,
)
from givp.examples.synthetic_hydropower.model.curves import (
    downstream_level,
    power_from_flow,
)

POWER_TOLERANCE_MW = 1e-6


def project_operating_flow(plant: PlantConfig, requested_flow_m3s: float) -> float:
    """Project a request onto the off-or-minimum-to-maximum flow interval."""
    bounded_flow = float(np.clip(requested_flow_m3s, 0.0, plant.max_flow_m3s))
    if np.isclose(bounded_flow, 0.0) or bounded_flow >= plant.min_flow_m3s:
        return bounded_flow
    return 0.0 if bounded_flow < plant.min_flow_m3s / 2.0 else plant.min_flow_m3s


def enforce_power_limits(
    plant: PlantConfig,
    upstream_level_m: float,
    requested_flow_m3s: float,
    spill_flow_m3s: float,
    maximum_available_flow_m3s: float,
) -> float:
    """Return an on/off turbine flow whose effective power respects both bounds."""
    candidate_flow = project_operating_flow(plant, requested_flow_m3s)
    maximum_flow = min(plant.max_flow_m3s, maximum_available_flow_m3s)
    if np.isclose(candidate_flow, 0.0) or np.isclose(maximum_flow, 0.0):
        return 0.0
    applied_flow = min(candidate_flow, maximum_flow)
    for _ in range(6):
        generated_power = power_from_flow(
            plant, upstream_level_m, applied_flow, spill_flow_m3s
        )
        target_power = (
            plant.min_power_mw
            if generated_power < plant.min_power_mw - POWER_TOLERANCE_MW
            else plant.max_power_mw
        )
        if (
            plant.min_power_mw - POWER_TOLERANCE_MW
            <= generated_power
            <= plant.max_power_mw + POWER_TOLERANCE_MW
        ):
            return applied_flow
        net_head_m = upstream_level_m - downstream_level(
            plant, applied_flow + spill_flow_m3s
        )
        if net_head_m <= 0.0:
            return 0.0
        applied_flow = min(
            maximum_flow,
            target_power / (WATER_POWER_FACTOR_MW * plant.efficiency * net_head_m),
        )
    generated_power = power_from_flow(
        plant, upstream_level_m, applied_flow, spill_flow_m3s
    )
    return (
        applied_flow
        if plant.min_power_mw - POWER_TOLERANCE_MW
        <= generated_power
        <= plant.max_power_mw + POWER_TOLERANCE_MW
        else 0.0
    )


def level_control_spill(
    plant: PlantConfig, upstream_level_before_control_m: float
) -> float:
    """Return spillway discharge from the level between normal and maximorum."""
    excess_level = max(0.0, upstream_level_before_control_m - plant.max_level_m)
    if np.isclose(excess_level, 0.0):
        return 0.0
    level_band = plant.maximorum_level_m - plant.max_level_m
    ratio = excess_level / level_band
    spillway_capacity = plant.spill_response * plant.max_flow_m3s
    gradual = spillway_capacity * min(1.0, ratio) ** plant.spill_response_exponent
    emergency = spillway_capacity * max(0.0, ratio - 1.0) ** 2
    return float(gradual + emergency)
