"""Two-plant cascade mass-balance simulator."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from synthetic_hydropower.model.config import (
    WATER_POWER_FACTOR_MW,
    CascadeConfig,
    SimulationResult,
)
from synthetic_hydropower.model.curves import downstream_level, upstream_level
from synthetic_hydropower.model.dispatch import (
    enforce_power_limits,
    level_control_spill,
)


def _next_unit_state(
    config: CascadeConfig,
    time_index: int,
    is_on: bool,
    previous_is_on: bool,
    previous_duration: int,
) -> tuple[int, float, float]:
    """Return duration and penalties after one aggregated-unit state transition."""
    if time_index == 0:
        return 1, 0.0, 0.0
    if is_on == previous_is_on:
        return previous_duration + 1, 0.0, 0.0
    early_duration = max(0, config.minimum_state_duration_hours - previous_duration)
    return (
        1,
        config.unit_switch_penalty_weight,
        config.early_switch_penalty_weight * early_duration,
    )


def simulate_cascade(
    config: CascadeConfig,
    incremental_inflow_m3s: NDArray[np.float64],
    requested_flow_m3s: NDArray[np.float64],
) -> SimulationResult:
    """Simulate conservation of mass, levels, spill and generation in a cascade."""
    shape = (2, config.periods)
    if incremental_inflow_m3s.shape != shape or requested_flow_m3s.shape != shape:
        raise ValueError("inflow and requested flow must have shape (2, periods)")
    if np.any(incremental_inflow_m3s < 0):
        raise ValueError("incremental inflow must be non-negative")
    turbine, spill, sanitary, capacity, level_spill = (
        np.zeros(shape, dtype=float) for _ in range(5)
    )
    arrivals, inflows, downstream, heads, defluents, power = (
        np.zeros(shape, dtype=float) for _ in range(6)
    )
    unit_on = np.zeros(shape, dtype=bool)
    state_duration = np.zeros(shape, dtype=int)
    unit_switch_penalty = np.zeros(shape, dtype=float)
    early_switch_penalty = np.zeros(shape, dtype=float)
    volumes = np.zeros((2, config.periods + 1), dtype=float)
    levels = np.zeros((2, config.periods + 1), dtype=float)
    volumes[:, 0] = [plant.initial_volume_hm3 for plant in config.plants]
    levels[:, 0] = [
        upstream_level(plant, volumes[index, 0])
        for index, plant in enumerate(config.plants)
    ]
    minimum_penalty = np.zeros(shape, dtype=float)
    maximum_penalty = np.zeros(shape, dtype=float)
    for time_index in range(config.periods):
        delayed_index = time_index - config.travel_time_steps
        if delayed_index >= 0:
            arrivals[1, time_index] = (
                turbine[0, delayed_index] + spill[0, delayed_index]
            )
        for plant_index, plant in enumerate(config.plants):
            inflow = (
                incremental_inflow_m3s[plant_index, time_index]
                + arrivals[plant_index, time_index]
            )
            available = max(
                0.0,
                volumes[plant_index, time_index] / config.flow_to_volume_hm3 + inflow,
            )
            applied = enforce_power_limits(
                plant,
                levels[plant_index, time_index],
                requested_flow_m3s[plant_index, time_index],
                0.0,
                available,
            )
            provisional_volume = volumes[
                plant_index, time_index
            ] + config.flow_to_volume_hm3 * (inflow - applied)
            provisional_level = upstream_level(plant, provisional_volume)
            sanitary_release = 0.0
            capacity_release = 0.0
            controlled_release = 0.0
            if provisional_level > plant.max_level_m:
                sanitary_release = plant.sanitary_spill_flow_m3s
                capacity_release = max(0.0, inflow - plant.max_flow_m3s)
                fixed_spill = sanitary_release + capacity_release
                applied = enforce_power_limits(
                    plant,
                    levels[plant_index, time_index],
                    requested_flow_m3s[plant_index, time_index],
                    fixed_spill,
                    max(0.0, available - fixed_spill),
                )
                provisional_volume = volumes[
                    plant_index, time_index
                ] + config.flow_to_volume_hm3 * (inflow - applied - fixed_spill)
                provisional_level = upstream_level(plant, provisional_volume)
                controlled_release = level_control_spill(
                    plant, provisional_level
                )
            total_spill = sanitary_release + capacity_release + controlled_release
            total_defluence = applied + total_spill
            final_volume = volumes[
                plant_index, time_index
            ] + config.flow_to_volume_hm3 * (inflow - total_defluence)
            final_level = upstream_level(plant, final_volume)
            tailwater = downstream_level(plant, total_defluence)
            head = max(0.0, levels[plant_index, time_index] - tailwater)
            is_on = applied > 0.0
            previous_index = max(0, time_index - 1)
            duration, switch_cost, early_switch_cost = _next_unit_state(
                config,
                time_index,
                is_on,
                bool(unit_on[plant_index, previous_index]),
                int(state_duration[plant_index, previous_index]),
            )
            state_duration[plant_index, time_index] = duration
            unit_switch_penalty[plant_index, time_index] = switch_cost
            early_switch_penalty[plant_index, time_index] = early_switch_cost
            minimum_penalty[plant_index, time_index] = (
                config.level_penalty_weight
                * max(0.0, plant.min_level_m - final_level) ** 2
            )
            maximum_penalty[plant_index, time_index] = (
                config.level_penalty_weight
                * max(0.0, final_level - plant.max_level_m) ** 2
            )
            turbine[plant_index, time_index] = applied
            spill[plant_index, time_index] = total_spill
            sanitary[plant_index, time_index] = sanitary_release
            capacity[plant_index, time_index] = capacity_release
            level_spill[plant_index, time_index] = controlled_release
            inflows[plant_index, time_index] = inflow
            volumes[plant_index, time_index + 1] = final_volume
            levels[plant_index, time_index + 1] = final_level
            downstream[plant_index, time_index] = tailwater
            heads[plant_index, time_index] = head
            defluents[plant_index, time_index] = total_defluence
            power[plant_index, time_index] = (
                WATER_POWER_FACTOR_MW * plant.efficiency * head * applied
            )
            unit_on[plant_index, time_index] = is_on
    energy = float(np.sum(power) * config.period_hours)
    total_unit_switch_penalty = float(np.sum(unit_switch_penalty))
    total_early_switch_penalty = float(np.sum(early_switch_penalty))
    total_minimum_penalty = float(np.sum(minimum_penalty))
    total_maximum_penalty = float(np.sum(maximum_penalty))
    total_level_penalty = total_minimum_penalty + total_maximum_penalty
    return SimulationResult(
        requested_flow_m3s.copy(),
        turbine,
        spill,
        sanitary,
        capacity,
        level_spill,
        incremental_inflow_m3s.copy(),
        inflows,
        arrivals,
        volumes,
        levels,
        downstream,
        heads,
        defluents,
        power,
        energy,
        unit_on,
        state_duration,
        unit_switch_penalty,
        total_unit_switch_penalty,
        early_switch_penalty,
        total_early_switch_penalty,
        minimum_penalty,
        maximum_penalty,
        total_minimum_penalty,
        total_maximum_penalty,
        total_level_penalty,
        float(
            -energy
            + total_level_penalty
            + total_unit_switch_penalty
            + total_early_switch_penalty
        ),
    )
