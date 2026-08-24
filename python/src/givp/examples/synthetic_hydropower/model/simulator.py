"""Two-plant cascade simulators sharing one hourly hydraulic transition."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.model.config import (
    CascadeConfig,
    PowerScheduleResult,
    SimulationResult,
)
from givp.examples.synthetic_hydropower.model.curves import upstream_level
from givp.examples.synthetic_hydropower.model.transition import (
    HydraulicTransition,
    hydraulic_transition,
    solve_power_transition,
)

Dispatch = Callable[[int, int, float, float, float], tuple[HydraulicTransition, str]]


def simulate_cascade(
    config: CascadeConfig,
    incremental_inflow_m3s: NDArray[np.float64],
    requested_flow_m3s: NDArray[np.float64],
) -> SimulationResult:
    """Simulate the cascade from turbine-flow requests."""
    _validate_inputs(config, incremental_inflow_m3s, requested_flow_m3s, "requested flow")

    def dispatch(
        plant_index: int,
        time_index: int,
        volume_hm3: float,
        level_m: float,
        inflow_m3s: float,
    ) -> tuple[HydraulicTransition, str]:
        transition = hydraulic_transition(
            config,
            config.plants[plant_index],
            volume_hm3,
            level_m,
            inflow_m3s,
            requested_flow_m3s[plant_index, time_index],
            enforce_operating_range=True,
        )
        return transition, "flow_dispatch"

    result, _ = _simulate(config, incremental_inflow_m3s, dispatch)
    return result


def simulate_power_schedule(
    config: CascadeConfig,
    incremental_inflow_m3s: NDArray[np.float64],
    target_power_mw: NDArray[np.float64],
) -> PowerScheduleResult:
    """Simulate the cascade while deterministically tracking hourly power targets."""
    _validate_inputs(config, incremental_inflow_m3s, target_power_mw, "target power")

    def dispatch(
        plant_index: int,
        time_index: int,
        volume_hm3: float,
        level_m: float,
        inflow_m3s: float,
    ) -> tuple[HydraulicTransition, str]:
        return solve_power_transition(
            config,
            config.plants[plant_index],
            volume_hm3,
            level_m,
            inflow_m3s,
            float(target_power_mw[plant_index, time_index]),
        )

    simulation, statuses = _simulate(config, incremental_inflow_m3s, dispatch)
    deficit = np.maximum(0.0, target_power_mw - simulation.power_mw)
    return PowerScheduleResult(
        simulation=simulation,
        target_power_mw=target_power_mw.copy(),
        delivered_power_mw=simulation.power_mw.copy(),
        power_deficit_mw=np.asarray(deficit, dtype=np.float64),
        dispatch_status=statuses,
    )


def _simulate(
    config: CascadeConfig,
    incremental_inflow_m3s: NDArray[np.float64],
    dispatch: Dispatch,
) -> tuple[SimulationResult, NDArray[np.str_]]:
    arrays = _SimulationArrays(config)
    arrays.initialize(config)
    statuses = np.full((2, config.periods), "", dtype="U32")
    for time_index in range(config.periods):
        delayed_index = time_index - config.travel_time_steps
        if delayed_index >= 0:
            arrays.arrivals[1, time_index] = arrays.defluents[0, delayed_index]
        for plant_index in range(2):
            total_inflow = (
                incremental_inflow_m3s[plant_index, time_index]
                + arrays.arrivals[plant_index, time_index]
            )
            transition, status = dispatch(
                plant_index,
                time_index,
                arrays.volumes[plant_index, time_index],
                arrays.levels[plant_index, time_index],
                total_inflow,
            )
            arrays.record(config, plant_index, time_index, total_inflow, transition)
            statuses[plant_index, time_index] = status
    return arrays.result(config, incremental_inflow_m3s), statuses


class _SimulationArrays:
    """Mutable arrays used only while assembling an immutable simulation result."""

    def __init__(self, config: CascadeConfig) -> None:
        shape = (2, config.periods)
        self.requested, self.turbine, self.spill, self.sanitary, self.capacity = (
            np.zeros(shape, dtype=float) for _ in range(5)
        )
        self.level_spill, self.arrivals, self.inflows, self.downstream = (
            np.zeros(shape, dtype=float) for _ in range(4)
        )
        self.heads, self.defluents, self.power = (
            np.zeros(shape, dtype=float) for _ in range(3)
        )
        self.unit_on = np.zeros(shape, dtype=bool)
        self.duration = np.zeros(shape, dtype=int)
        self.switch = np.zeros(shape, dtype=float)
        self.early_switch = np.zeros(shape, dtype=float)
        self.minimum_penalty = np.zeros(shape, dtype=float)
        self.maximum_penalty = np.zeros(shape, dtype=float)
        self.volumes = np.zeros((2, config.periods + 1), dtype=float)
        self.levels = np.zeros((2, config.periods + 1), dtype=float)

    def initialize(self, config: CascadeConfig) -> None:
        """Set initial storage and upstream level for both plants."""
        self.volumes[:, 0] = [plant.initial_volume_hm3 for plant in config.plants]
        self.levels[:, 0] = [
            upstream_level(plant, self.volumes[index, 0])
            for index, plant in enumerate(config.plants)
        ]

    def record(
        self,
        config: CascadeConfig,
        plant_index: int,
        time_index: int,
        total_inflow_m3s: float,
        transition: HydraulicTransition,
    ) -> None:
        """Record one transition and its objective penalties."""
        plant = config.plants[plant_index]
        previous_index = max(0, time_index - 1)
        duration, switch, early = _next_unit_state(
            config,
            time_index,
            transition.turbine_flow_m3s > 0.0,
            bool(self.unit_on[plant_index, previous_index]),
            int(self.duration[plant_index, previous_index]),
        )
        self.requested[plant_index, time_index] = transition.requested_flow_m3s
        self.turbine[plant_index, time_index] = transition.turbine_flow_m3s
        self.spill[plant_index, time_index] = transition.spill_flow_m3s
        self.sanitary[plant_index, time_index] = transition.sanitary_spill_flow_m3s
        self.capacity[plant_index, time_index] = transition.capacity_spill_flow_m3s
        self.level_spill[plant_index, time_index] = transition.level_control_spill_flow_m3s
        self.inflows[plant_index, time_index] = total_inflow_m3s
        self.volumes[plant_index, time_index + 1] = transition.final_volume_hm3
        self.levels[plant_index, time_index + 1] = transition.final_level_m
        self.downstream[plant_index, time_index] = transition.downstream_level_m
        self.heads[plant_index, time_index] = transition.net_head_m
        self.defluents[plant_index, time_index] = transition.defluent_flow_m3s
        self.power[plant_index, time_index] = transition.power_mw
        self.unit_on[plant_index, time_index] = transition.turbine_flow_m3s > 0.0
        self.duration[plant_index, time_index] = duration
        self.switch[plant_index, time_index] = switch
        self.early_switch[plant_index, time_index] = early
        self.minimum_penalty[plant_index, time_index] = (
            config.level_penalty_weight
            * max(0.0, plant.min_level_m - transition.final_level_m) ** 2
        )
        self.maximum_penalty[plant_index, time_index] = (
            config.level_penalty_weight
            * max(0.0, transition.final_level_m - plant.max_level_m) ** 2
        )

    def result(
        self,
        config: CascadeConfig,
        incremental_inflow_m3s: NDArray[np.float64],
    ) -> SimulationResult:
        """Build the immutable public result and objective decomposition."""
        energy = float(np.sum(self.power) * config.period_hours)
        switch = float(np.sum(self.switch))
        early = float(np.sum(self.early_switch))
        minimum = float(np.sum(self.minimum_penalty))
        maximum = float(np.sum(self.maximum_penalty))
        level = minimum + maximum
        return SimulationResult(
            requested_flow_m3s=self.requested,
            turbine_flow_m3s=self.turbine,
            spill_flow_m3s=self.spill,
            sanitary_spill_flow_m3s=self.sanitary,
            capacity_spill_flow_m3s=self.capacity,
            level_control_spill_flow_m3s=self.level_spill,
            inflow_m3s=incremental_inflow_m3s.copy(),
            total_inflow_m3s=self.inflows,
            upstream_arrival_m3s=self.arrivals,
            volume_hm3=self.volumes,
            level_m=self.levels,
            downstream_level_m=self.downstream,
            net_head_m=self.heads,
            defluent_flow_m3s=self.defluents,
            power_mw=self.power,
            energy_mwh=energy,
            unit_on=self.unit_on,
            state_duration_hours=self.duration,
            unit_switch_penalty_by_period=self.switch,
            unit_switch_penalty=switch,
            early_switch_penalty_by_period=self.early_switch,
            early_switch_penalty=early,
            minimum_level_penalty_by_period=self.minimum_penalty,
            maximum_level_penalty_by_period=self.maximum_penalty,
            minimum_level_penalty=minimum,
            maximum_level_penalty=maximum,
            level_penalty=level,
            objective=float(-energy + level + switch + early),
        )


def _next_unit_state(
    config: CascadeConfig,
    time_index: int,
    is_on: bool,
    previous_is_on: bool,
    previous_duration: int,
) -> tuple[int, float, float]:
    if time_index == 0:
        return 1, 0.0, 0.0
    if is_on == previous_is_on:
        return previous_duration + 1, 0.0, 0.0
    early_duration = max(0, config.minimum_state_duration_hours - previous_duration)
    return 1, config.unit_switch_penalty_weight, (
        config.early_switch_penalty_weight * early_duration
    )


def _validate_inputs(
    config: CascadeConfig,
    inflow: NDArray[np.float64],
    schedule: NDArray[np.float64],
    schedule_name: str,
) -> None:
    shape = (2, config.periods)
    if inflow.shape != shape or schedule.shape != shape:
        raise ValueError(f"inflow and {schedule_name} must have shape (2, periods)")
    if np.any(inflow < 0):
        raise ValueError("incremental inflow must be non-negative")
