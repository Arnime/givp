"""Shared hourly hydraulic transition and deterministic power inversion."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from givp.examples.synthetic_hydropower.model.config import (
    WATER_POWER_FACTOR_MW,
    CascadeConfig,
    PlantConfig,
)
from givp.examples.synthetic_hydropower.model.curves import (
    downstream_level,
    upstream_level,
)
from givp.examples.synthetic_hydropower.model.dispatch import (
    enforce_power_limits,
    level_control_spill,
)

POWER_TOLERANCE_MW = 1e-6
BISECTION_MAX_ITERATIONS = 80
SPILL_COUPLING_MAX_ITERATIONS = 50


class PowerScheduleConvergenceError(RuntimeError):
    """Raised when deterministic power-to-flow inversion does not converge."""


@dataclass(frozen=True)
class HydraulicTransition:
    """Physical state produced by one plant during one time step."""

    requested_flow_m3s: float
    turbine_flow_m3s: float
    spill_flow_m3s: float
    sanitary_spill_flow_m3s: float
    capacity_spill_flow_m3s: float
    level_control_spill_flow_m3s: float
    final_volume_hm3: float
    final_level_m: float
    downstream_level_m: float
    net_head_m: float
    defluent_flow_m3s: float
    power_mw: float


def hydraulic_transition(
    config: CascadeConfig,
    plant: PlantConfig,
    initial_volume_hm3: float,
    initial_level_m: float,
    inflow_m3s: float,
    requested_flow_m3s: float,
    *,
    enforce_operating_range: bool,
) -> HydraulicTransition:
    """Apply the shared mass-balance, level, spill, tailwater and power equations."""
    available = max(0.0, initial_volume_hm3 / config.flow_to_volume_hm3 + inflow_m3s)
    applied = _bounded_turbine_flow(
        plant,
        initial_level_m,
        requested_flow_m3s,
        0.0,
        available,
        enforce_operating_range,
    )
    provisional_volume = initial_volume_hm3 + config.flow_to_volume_hm3 * (
        inflow_m3s - applied
    )
    provisional_level = upstream_level(plant, provisional_volume)
    sanitary = capacity = controlled = 0.0
    if provisional_level > plant.max_level_m:
        sanitary = plant.sanitary_spill_flow_m3s
        capacity = max(0.0, inflow_m3s - plant.max_flow_m3s)
        fixed_spill = sanitary + capacity
        applied = _bounded_turbine_flow(
            plant,
            initial_level_m,
            requested_flow_m3s,
            fixed_spill,
            max(0.0, available - fixed_spill),
            enforce_operating_range,
        )
        provisional_volume = initial_volume_hm3 + config.flow_to_volume_hm3 * (
            inflow_m3s - applied - fixed_spill
        )
        provisional_level = upstream_level(plant, provisional_volume)
        controlled = level_control_spill(plant, provisional_level)
    total_spill = sanitary + capacity + controlled
    defluence = applied + total_spill
    final_volume = initial_volume_hm3 + config.flow_to_volume_hm3 * (
        inflow_m3s - defluence
    )
    final_level = upstream_level(plant, final_volume)
    tailwater = downstream_level(plant, defluence)
    head = max(0.0, initial_level_m - tailwater)
    power = WATER_POWER_FACTOR_MW * plant.efficiency * head * applied
    return HydraulicTransition(
        requested_flow_m3s=float(requested_flow_m3s),
        turbine_flow_m3s=float(applied),
        spill_flow_m3s=float(total_spill),
        sanitary_spill_flow_m3s=float(sanitary),
        capacity_spill_flow_m3s=float(capacity),
        level_control_spill_flow_m3s=float(controlled),
        final_volume_hm3=float(final_volume),
        final_level_m=float(final_level),
        downstream_level_m=float(tailwater),
        net_head_m=float(head),
        defluent_flow_m3s=float(defluence),
        power_mw=float(power),
    )


def solve_power_transition(
    config: CascadeConfig,
    plant: PlantConfig,
    initial_volume_hm3: float,
    initial_level_m: float,
    inflow_m3s: float,
    target_power_mw: float,
) -> tuple[HydraulicTransition, str]:
    """Invert a feasible target power into turbine flow deterministically."""
    _validate_target_power(plant, target_power_mw)
    if np.isclose(target_power_mw, 0.0, atol=POWER_TOLERANCE_MW):
        return _raw_transition(
            config, plant, initial_volume_hm3, initial_level_m, inflow_m3s, 0.0
        ), "off"

    maximum = _raw_transition(
        config,
        plant,
        initial_volume_hm3,
        initial_level_m,
        inflow_m3s,
        plant.max_flow_m3s,
    )
    if maximum.power_mw < target_power_mw - POWER_TOLERANCE_MW:
        status = _limiting_status(plant, maximum)
        if maximum.power_mw < plant.min_power_mw - POWER_TOLERANCE_MW:
            return _raw_transition(
                config, plant, initial_volume_hm3, initial_level_m, inflow_m3s, 0.0
            ), status
        return maximum, status

    spill_estimate = maximum.spill_flow_m3s
    for _ in range(SPILL_COUPLING_MAX_ITERATIONS):
        request = _bisect_power_flow(
            plant,
            initial_level_m,
            target_power_mw,
            maximum.turbine_flow_m3s,
            spill_estimate,
        )
        transition = _raw_transition(
            config, plant, initial_volume_hm3, initial_level_m, inflow_m3s, request
        )
        if abs(transition.power_mw - target_power_mw) <= POWER_TOLERANCE_MW:
            return transition, "met"
        if np.isclose(transition.spill_flow_m3s, spill_estimate, atol=1e-12):
            break
        spill_estimate = transition.spill_flow_m3s
    transition = _search_coupled_transition(
        config,
        plant,
        initial_volume_hm3,
        initial_level_m,
        inflow_m3s,
        target_power_mw,
        maximum.turbine_flow_m3s,
    )
    if abs(transition.power_mw - target_power_mw) <= POWER_TOLERANCE_MW:
        return transition, "met"
    if np.isfinite(transition.power_mw) and np.isfinite(maximum.power_mw):
        return maximum, _limiting_status(plant, maximum)
    raise PowerScheduleConvergenceError(
        f"power inversion did not converge for plant {plant.name!r} "
        f"and target {target_power_mw:.6f} MW"
    )


def _bounded_turbine_flow(
    plant: PlantConfig,
    level_m: float,
    request_m3s: float,
    spill_m3s: float,
    available_m3s: float,
    enforce_operating_range: bool,
) -> float:
    if enforce_operating_range:
        return enforce_power_limits(
            plant, level_m, request_m3s, spill_m3s, available_m3s
        )
    return float(np.clip(request_m3s, 0.0, min(plant.max_flow_m3s, available_m3s)))


def _raw_transition(
    config: CascadeConfig,
    plant: PlantConfig,
    volume_hm3: float,
    level_m: float,
    inflow_m3s: float,
    request_m3s: float,
) -> HydraulicTransition:
    return hydraulic_transition(
        config,
        plant,
        volume_hm3,
        level_m,
        inflow_m3s,
        request_m3s,
        enforce_operating_range=False,
    )


def _bisect_power_flow(
    plant: PlantConfig,
    upstream_level_m: float,
    target_power_mw: float,
    maximum_flow_m3s: float,
    spill_flow_m3s: float,
) -> float:
    lower = 0.0
    upper = maximum_flow_m3s
    for _ in range(BISECTION_MAX_ITERATIONS):
        middle = (lower + upper) / 2.0
        tailwater = downstream_level(plant, middle + spill_flow_m3s)
        head = max(0.0, upstream_level_m - tailwater)
        power = WATER_POWER_FACTOR_MW * plant.efficiency * head * middle
        if abs(power - target_power_mw) <= POWER_TOLERANCE_MW:
            return middle
        if power < target_power_mw:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2.0


def _search_coupled_transition(
    config: CascadeConfig,
    plant: PlantConfig,
    volume_hm3: float,
    level_m: float,
    inflow_m3s: float,
    target_power_mw: float,
    maximum_flow_m3s: float,
) -> HydraulicTransition:
    """Locate and bisect a root of the fully coupled, potentially non-monotonic curve."""
    grid = np.linspace(0.0, maximum_flow_m3s, 257)
    transitions = [
        _raw_transition(config, plant, volume_hm3, level_m, inflow_m3s, flow)
        for flow in grid
    ]
    errors = [transition.power_mw - target_power_mw for transition in transitions]
    closest_index = int(np.argmin(np.abs(errors)))
    if abs(errors[closest_index]) <= POWER_TOLERANCE_MW:
        return transitions[closest_index]
    for index, (left_error, right_error) in enumerate(pairwise(errors)):
        if left_error * right_error <= 0.0:
            return _bisect_coupled_interval(
                config,
                plant,
                volume_hm3,
                level_m,
                inflow_m3s,
                target_power_mw,
                float(grid[index]),
                float(grid[index + 1]),
            )
    return transitions[closest_index]


def _bisect_coupled_interval(
    config: CascadeConfig,
    plant: PlantConfig,
    volume_hm3: float,
    level_m: float,
    inflow_m3s: float,
    target_power_mw: float,
    lower: float,
    upper: float,
) -> HydraulicTransition:
    transition = _raw_transition(
        config, plant, volume_hm3, level_m, inflow_m3s, lower
    )
    lower_error = transition.power_mw - target_power_mw
    for _ in range(BISECTION_MAX_ITERATIONS):
        middle = (lower + upper) / 2.0
        transition = _raw_transition(
            config, plant, volume_hm3, level_m, inflow_m3s, middle
        )
        error = transition.power_mw - target_power_mw
        if abs(error) <= POWER_TOLERANCE_MW:
            return transition
        if lower_error * error <= 0.0:
            upper = middle
        else:
            lower = middle
            lower_error = error
    return transition


def _validate_target_power(plant: PlantConfig, target_power_mw: float) -> None:
    valid = np.isclose(target_power_mw, 0.0, atol=POWER_TOLERANCE_MW) or (
        plant.min_power_mw <= target_power_mw <= plant.max_power_mw
    )
    if not valid:
        raise ValueError(
            f"target power for plant {plant.name!r} must be zero or lie within "
            f"[{plant.min_power_mw}, {plant.max_power_mw}] MW"
        )


def _limiting_status(plant: PlantConfig, maximum: HydraulicTransition) -> str:
    if maximum.net_head_m <= 0.0:
        return "head_limited"
    if maximum.turbine_flow_m3s < plant.max_flow_m3s - 1e-9:
        return "water_limited"
    return "turbine_capacity_limited"
