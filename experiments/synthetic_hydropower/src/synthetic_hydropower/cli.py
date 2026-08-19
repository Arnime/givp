"""Command-line interface for the standalone synthetic experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from synthetic_hydropower.runner import load_experiment_config, optimize_scenario


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main() -> None:
    """Run configured scenarios and write CSV/JSON results to an explicit directory."""
    args = _build_parser().parse_args()
    experiment = load_experiment_config(args.config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, float | str]] = []
    for scenario_index, scenario_name in enumerate(experiment.scenarios):
        result = optimize_scenario(
            experiment, scenario_name, args.seed + scenario_index
        )
        rows = [
            {
                "period": time_index,
                "inflow_a_m3s": result.inflow_m3s[0, time_index],
                "inflow_b_m3s": result.inflow_m3s[1, time_index],
                "total_inflow_b_m3s": result.total_inflow_m3s[1, time_index],
                "arrival_at_b_m3s": result.upstream_arrival_m3s[1, time_index],
                "power_a_mw": result.power_mw[0, time_index],
                "power_b_mw": result.power_mw[1, time_index],
                "turbine_a_m3s": result.turbine_flow_m3s[0, time_index],
                "turbine_b_m3s": result.turbine_flow_m3s[1, time_index],
                "spill_a_m3s": result.spill_flow_m3s[0, time_index],
                "spill_b_m3s": result.spill_flow_m3s[1, time_index],
                "sanitary_spill_a_m3s": result.sanitary_spill_flow_m3s[0, time_index],
                "sanitary_spill_b_m3s": result.sanitary_spill_flow_m3s[1, time_index],
                "capacity_spill_a_m3s": result.capacity_spill_flow_m3s[0, time_index],
                "capacity_spill_b_m3s": result.capacity_spill_flow_m3s[1, time_index],
                "level_control_spill_a_m3s": result.level_control_spill_flow_m3s[
                    0, time_index
                ],
                "level_control_spill_b_m3s": result.level_control_spill_flow_m3s[
                    1, time_index
                ],
                "defluence_a_m3s": result.defluent_flow_m3s[0, time_index],
                "defluence_b_m3s": result.defluent_flow_m3s[1, time_index],
                "upstream_level_a_m": result.level_m[0, time_index + 1],
                "upstream_level_b_m": result.level_m[1, time_index + 1],
                "downstream_level_a_m": result.downstream_level_m[0, time_index],
                "downstream_level_b_m": result.downstream_level_m[1, time_index],
                "net_head_a_m": result.net_head_m[0, time_index],
                "net_head_b_m": result.net_head_m[1, time_index],
            }
            for time_index in range(experiment.cascade.periods)
        ]
        pd.DataFrame(rows).to_csv(args.output_dir / f"{scenario_name}.csv", index=False)
        summaries.append(
            {
                "scenario": scenario_name,
                "energy_mwh": result.energy_mwh,
                "level_penalty": result.level_penalty,
                "objective": result.objective,
            }
        )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
