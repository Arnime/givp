"""Tabular representations of synthetic hydropower benchmark results."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pandas as pd

from givp.examples.synthetic_hydropower.model import CascadeConfig, SimulationResult


def _summary_frame(
    results: Mapping[str, SimulationResult],
    cascade: CascadeConfig,
    scenario_seeds: Mapping[str, int],
) -> pd.DataFrame:
    """Build one reproducible aggregate row for each scenario."""
    rows: list[dict[str, float | int | str]] = []
    for scenario_name, result in results.items():
        row: dict[str, float | int | str] = {
            "scenario": scenario_name,
            "seed": scenario_seeds[scenario_name],
            "energy_mwh": result.energy_mwh,
            "unit_switch_penalty": result.unit_switch_penalty,
            "early_switch_penalty": result.early_switch_penalty,
            "minimum_level_penalty": result.minimum_level_penalty,
            "maximum_level_penalty": result.maximum_level_penalty,
            "level_penalty": result.level_penalty,
            "objective": result.objective,
        }
        for plant_index, plant in enumerate(cascade.plants):
            plant_name = plant.name.lower()
            row[f"initial_level_{plant_name}_m"] = result.level_m[plant_index, 0]
            row[f"final_level_{plant_name}_m"] = result.level_m[plant_index, -1]
        rows.append(row)
    return cast(pd.DataFrame, pd.DataFrame(rows))


def _time_series_frame(
    results: Mapping[str, SimulationResult],
    cascade: CascadeConfig,
    scenario_seeds: Mapping[str, int],
) -> pd.DataFrame:
    """Build a long, tidy time-series table for all plants and scenarios."""
    rows: list[dict[str, float | int | str]] = []
    for scenario_name, result in results.items():
        for plant_index, plant in enumerate(cascade.plants):
            for period in range(cascade.periods):
                rows.append(
                    {
                        "scenario": scenario_name,
                        "seed": scenario_seeds[scenario_name],
                        "plant": plant.name,
                        "period": period,
                        "incremental_inflow_m3s": result.inflow_m3s[
                            plant_index, period
                        ],
                        "total_inflow_m3s": result.total_inflow_m3s[
                            plant_index, period
                        ],
                        "upstream_arrival_m3s": result.upstream_arrival_m3s[
                            plant_index, period
                        ],
                        "requested_flow_m3s": result.requested_flow_m3s[
                            plant_index, period
                        ],
                        "turbine_flow_m3s": result.turbine_flow_m3s[
                            plant_index, period
                        ],
                        "spill_flow_m3s": result.spill_flow_m3s[plant_index, period],
                        "sanitary_spill_flow_m3s": result.sanitary_spill_flow_m3s[
                            plant_index, period
                        ],
                        "capacity_spill_flow_m3s": result.capacity_spill_flow_m3s[
                            plant_index, period
                        ],
                        "level_control_spill_flow_m3s": result.level_control_spill_flow_m3s[
                            plant_index, period
                        ],
                        "defluent_flow_m3s": result.defluent_flow_m3s[
                            plant_index, period
                        ],
                        "initial_volume_hm3": result.volume_hm3[plant_index, period],
                        "final_volume_hm3": result.volume_hm3[plant_index, period + 1],
                        "initial_upstream_level_m": result.level_m[plant_index, period],
                        "final_upstream_level_m": result.level_m[
                            plant_index, period + 1
                        ],
                        "downstream_level_m": result.downstream_level_m[
                            plant_index, period
                        ],
                        "net_head_m": result.net_head_m[plant_index, period],
                        "power_mw": result.power_mw[plant_index, period],
                        "unit_on": result.unit_on[plant_index, period],
                        "state_duration_hours": result.state_duration_hours[
                            plant_index, period
                        ],
                        "unit_switch_penalty": result.unit_switch_penalty_by_period[
                            plant_index, period
                        ],
                        "early_switch_penalty": result.early_switch_penalty_by_period[
                            plant_index, period
                        ],
                        "minimum_level_penalty": result.minimum_level_penalty_by_period[
                            plant_index, period
                        ],
                        "maximum_level_penalty": result.maximum_level_penalty_by_period[
                            plant_index, period
                        ],
                    }
                )
    return cast(pd.DataFrame, pd.DataFrame(rows))
