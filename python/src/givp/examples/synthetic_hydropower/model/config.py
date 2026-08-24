"""Configuration and result types for the synthetic hydropower model."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

GRAVITY_M_S2: float = 9.81
WATER_POWER_FACTOR_MW: float = GRAVITY_M_S2 * 1e-3


@dataclass(frozen=True)
class PlantConfig:
    """Fictional physical and operating parameters for one aggregated plant."""

    name: str
    initial_volume_hm3: float
    min_volume_hm3: float
    max_volume_hm3: float
    maximorum_volume_hm3: float
    min_level_m: float
    max_level_m: float
    head_m: float
    efficiency: float
    min_power_mw: float
    max_power_mw: float
    upstream_level_coefficients: Sequence[float]
    downstream_base_level_m: float
    downstream_level_range_m: float
    downstream_level_coefficients: Sequence[float]
    sanitary_spill_flow_m3s: float
    spill_response: float
    spill_response_exponent: float
    maximorum_level_m: float

    def __post_init__(self) -> None:
        if (
            not 0
            <= self.min_volume_hm3
            < self.max_volume_hm3
            < self.maximorum_volume_hm3
        ):
            raise ValueError("reservoir volumes must be strictly ordered")
        if not self.min_volume_hm3 <= self.initial_volume_hm3 <= self.max_volume_hm3:
            raise ValueError("initial volume must lie within reservoir bounds")
        if self.max_level_m <= self.min_level_m:
            raise ValueError("level bounds must be ordered")
        if self.maximorum_level_m <= self.max_level_m:
            raise ValueError("maximorum level must exceed the normal maximum level")
        if self.head_m <= 0 or not 0 < self.efficiency <= 1:
            raise ValueError("head and efficiency must be physically valid")
        if not 0 <= self.min_power_mw <= self.max_power_mw:
            raise ValueError("power bounds must be non-negative and ordered")
        if (
            len(self.upstream_level_coefficients) != 5
            or len(self.downstream_level_coefficients) != 5
        ):
            raise ValueError("level polynomials must have five coefficients")
        if self.downstream_level_range_m < 0 or self.sanitary_spill_flow_m3s < 0:
            raise ValueError("downstream range and sanitary spill must be non-negative")
        if not 0 < self.spill_response <= 1 or self.spill_response_exponent <= 0:
            raise ValueError("spill response parameters must be positive and bounded")

    @property
    def mw_per_m3s(self) -> float:
        """Return nominal power per unit turbine flow in MW/(m³/s)."""
        return WATER_POWER_FACTOR_MW * self.head_m * self.efficiency

    @property
    def min_flow_m3s(self) -> float:
        """Return the nominal minimum turbine flow derived from minimum power."""
        return self.min_power_mw / self.mw_per_m3s

    @property
    def max_flow_m3s(self) -> float:
        """Return the nominal maximum turbine flow derived from maximum power."""
        return self.max_power_mw / self.mw_per_m3s


@dataclass(frozen=True)
class CascadeConfig:
    """Configuration of the fictional two-plant cascade."""

    plants: tuple[PlantConfig, PlantConfig]
    periods: int
    period_hours: float
    travel_time_steps: int
    level_penalty_weight: float
    unit_switch_penalty_weight: float = 0.0
    minimum_state_duration_hours: int = 0
    early_switch_penalty_weight: float = 0.0

    def __post_init__(self) -> None:
        if self.periods < 1 or self.period_hours <= 0 or self.travel_time_steps < 1:
            raise ValueError("time configuration must be positive")
        if self.level_penalty_weight < 0:
            raise ValueError("level penalty weight must be non-negative")
        if self.unit_switch_penalty_weight < 0:
            raise ValueError("unit switch penalty weight must be non-negative")
        if self.minimum_state_duration_hours < 0:
            raise ValueError("minimum state duration must be non-negative")
        if self.early_switch_penalty_weight < 0:
            raise ValueError("early switch penalty weight must be non-negative")

    @property
    def flow_to_volume_hm3(self) -> float:
        """Convert a flow in m³/s to volume in hm³ for one time step."""
        return self.period_hours * 3600.0 / 1_000_000.0


@dataclass(frozen=True)
class SimulationResult:
    """Time series and objective decomposition produced by the simulator."""

    requested_flow_m3s: NDArray[np.float64]
    turbine_flow_m3s: NDArray[np.float64]
    spill_flow_m3s: NDArray[np.float64]
    sanitary_spill_flow_m3s: NDArray[np.float64]
    capacity_spill_flow_m3s: NDArray[np.float64]
    level_control_spill_flow_m3s: NDArray[np.float64]
    inflow_m3s: NDArray[np.float64]
    total_inflow_m3s: NDArray[np.float64]
    upstream_arrival_m3s: NDArray[np.float64]
    volume_hm3: NDArray[np.float64]
    level_m: NDArray[np.float64]
    downstream_level_m: NDArray[np.float64]
    net_head_m: NDArray[np.float64]
    defluent_flow_m3s: NDArray[np.float64]
    power_mw: NDArray[np.float64]
    energy_mwh: float
    unit_on: NDArray[np.bool_]
    state_duration_hours: NDArray[np.int_]
    unit_switch_penalty_by_period: NDArray[np.float64]
    unit_switch_penalty: float
    early_switch_penalty_by_period: NDArray[np.float64]
    early_switch_penalty: float
    minimum_level_penalty_by_period: NDArray[np.float64]
    maximum_level_penalty_by_period: NDArray[np.float64]
    minimum_level_penalty: float
    maximum_level_penalty: float
    level_penalty: float
    objective: float


@dataclass(frozen=True)
class PowerScheduleResult:
    """Hydraulic simulation and delivery diagnostics for a power schedule."""

    simulation: SimulationResult
    target_power_mw: NDArray[np.float64]
    delivered_power_mw: NDArray[np.float64]
    power_deficit_mw: NDArray[np.float64]
    dispatch_status: NDArray[np.str_]
