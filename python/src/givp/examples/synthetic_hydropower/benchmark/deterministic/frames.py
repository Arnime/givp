"""Canonical tabular schemas for deterministic power-balance cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.benchmark.cases import PowerCase
from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PowerScheduleResult,
)


def inflow_frame(inflows: Mapping[str, NDArray[np.float64]]) -> pd.DataFrame:
    """Create the frozen long-format inflow input table."""
    rows = [
        {
            "scenario": scenario,
            "plant": plant,
            "period": period,
            "incremental_inflow_m3s": values[plant_index, period],
        }
        for scenario, values in inflows.items()
        for plant_index, plant in enumerate(("A", "B"))
        for period in range(values.shape[1])
    ]
    return cast(pd.DataFrame, pd.DataFrame(rows))


def schedule_frame(cases: Sequence[PowerCase]) -> pd.DataFrame:
    """Create the explicit constant hourly power schedule table."""
    rows = [
        {
            "case_id": case.case_id,
            "scenario": case.scenario,
            "level_a": case.level_a,
            "level_b": case.level_b,
            "plant": plant,
            "period": period,
            "target_power_mw": case.target_power_mw[plant_index, period],
        }
        for case in cases
        for plant_index, plant in enumerate(("A", "B"))
        for period in range(case.target_power_mw.shape[1])
    ]
    return cast(pd.DataFrame, pd.DataFrame(rows))


def balance_time_series_frame(
    cases: Sequence[PowerCase],
    results: Mapping[str, PowerScheduleResult],
    cascade: CascadeConfig,
) -> pd.DataFrame:
    """Create the canonical hourly physical-result table."""
    rows: list[dict[str, float | int | str | bool]] = []
    for case in cases:
        result = results[case.case_id]
        simulation = result.simulation
        for plant_index, plant in enumerate(cascade.plants):
            for period in range(cascade.periods):
                volume_change = (
                    simulation.volume_hm3[plant_index, period + 1]
                    - simulation.volume_hm3[plant_index, period]
                )
                expected_change = cascade.flow_to_volume_hm3 * (
                    simulation.total_inflow_m3s[plant_index, period]
                    - simulation.defluent_flow_m3s[plant_index, period]
                )
                rows.append(
                    {
                        "case_id": case.case_id,
                        "scenario": case.scenario,
                        "level_a": case.level_a,
                        "level_b": case.level_b,
                        "plant": plant.name,
                        "period": period,
                        "target_power_mw": result.target_power_mw[plant_index, period],
                        "delivered_power_mw": result.delivered_power_mw[
                            plant_index, period
                        ],
                        "power_deficit_mw": result.power_deficit_mw[
                            plant_index, period
                        ],
                        "dispatch_status": result.dispatch_status[plant_index, period],
                        "incremental_inflow_m3s": simulation.inflow_m3s[
                            plant_index, period
                        ],
                        "upstream_arrival_m3s": simulation.upstream_arrival_m3s[
                            plant_index, period
                        ],
                        "total_inflow_m3s": simulation.total_inflow_m3s[
                            plant_index, period
                        ],
                        "requested_flow_m3s": simulation.requested_flow_m3s[
                            plant_index, period
                        ],
                        "turbine_flow_m3s": simulation.turbine_flow_m3s[
                            plant_index, period
                        ],
                        "sanitary_spill_flow_m3s": simulation.sanitary_spill_flow_m3s[
                            plant_index, period
                        ],
                        "capacity_spill_flow_m3s": simulation.capacity_spill_flow_m3s[
                            plant_index, period
                        ],
                        "level_control_spill_flow_m3s": simulation.level_control_spill_flow_m3s[
                            plant_index, period
                        ],
                        "spill_flow_m3s": simulation.spill_flow_m3s[
                            plant_index, period
                        ],
                        "defluent_flow_m3s": simulation.defluent_flow_m3s[
                            plant_index, period
                        ],
                        "initial_volume_hm3": simulation.volume_hm3[
                            plant_index, period
                        ],
                        "final_volume_hm3": simulation.volume_hm3[
                            plant_index, period + 1
                        ],
                        "initial_upstream_level_m": simulation.level_m[
                            plant_index, period
                        ],
                        "final_upstream_level_m": simulation.level_m[
                            plant_index, period + 1
                        ],
                        "downstream_level_m": simulation.downstream_level_m[
                            plant_index, period
                        ],
                        "net_head_m": simulation.net_head_m[plant_index, period],
                        "minimum_level_penalty": simulation.minimum_level_penalty_by_period[
                            plant_index, period
                        ],
                        "maximum_level_penalty": simulation.maximum_level_penalty_by_period[
                            plant_index, period
                        ],
                        "mass_balance_residual_hm3": volume_change - expected_change,
                    }
                )
    return cast(pd.DataFrame, pd.DataFrame(rows))


def balance_summary_frame(
    cases: Sequence[PowerCase],
    results: Mapping[str, PowerScheduleResult],
    cascade: CascadeConfig,
) -> pd.DataFrame:
    """Create one aggregate row per scenario and factorial power case."""
    rows: list[dict[str, float | int | str]] = []
    for case in cases:
        result = results[case.case_id]
        simulation = result.simulation
        target_energy = float(np.sum(result.target_power_mw) * cascade.period_hours)
        delivered_energy = float(
            np.sum(result.delivered_power_mw) * cascade.period_hours
        )
        row: dict[str, float | int | str] = {
            "case_id": case.case_id,
            "scenario": case.scenario,
            "level_a": case.level_a,
            "level_b": case.level_b,
            "target_energy_mwh": target_energy,
            "delivered_energy_mwh": delivered_energy,
            "delivered_percent": (
                100.0
                if np.isclose(target_energy, 0.0, rtol=0.0, atol=1e-12)
                else 100.0 * delivered_energy / target_energy
            ),
            "power_deficit_mwh": float(
                np.sum(result.power_deficit_mw) * cascade.period_hours
            ),
            "minimum_level_penalty": simulation.minimum_level_penalty,
            "maximum_level_penalty": simulation.maximum_level_penalty,
            "level_penalty": simulation.level_penalty,
        }
        for plant_index, plant in enumerate(cascade.plants):
            prefix = f"plant_{plant.name.lower()}"
            levels = simulation.level_m[plant_index, 1:]
            residual = np.diff(simulation.volume_hm3[plant_index]) - (
                cascade.flow_to_volume_hm3
                * (
                    simulation.total_inflow_m3s[plant_index]
                    - simulation.defluent_flow_m3s[plant_index]
                )
            )
            row.update(
                {
                    f"{prefix}_minimum_level_m": float(np.min(levels)),
                    f"{prefix}_maximum_level_m": float(np.max(levels)),
                    f"{prefix}_final_level_m": float(levels[-1]),
                    f"{prefix}_final_volume_hm3": float(
                        simulation.volume_hm3[plant_index, -1]
                    ),
                    f"{prefix}_hours_below_minimum": int(
                        np.count_nonzero(levels < plant.min_level_m)
                    ),
                    f"{prefix}_hours_above_maximum": int(
                        np.count_nonzero(levels > plant.max_level_m)
                    ),
                    f"{prefix}_spill_volume_hm3": float(
                        np.sum(simulation.spill_flow_m3s[plant_index])
                        * cascade.flow_to_volume_hm3
                    ),
                    f"{prefix}_maximum_mass_balance_residual_hm3": float(
                        np.max(np.abs(residual))
                    ),
                }
            )
        rows.append(row)
    return cast(pd.DataFrame, pd.DataFrame(rows))
