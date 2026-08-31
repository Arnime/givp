"""Command-line interface for the synthetic hydropower GIVP example."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from givp.examples.synthetic_hydropower.interop import evaluate_batch, run_worker
from givp.examples.synthetic_hydropower.paths import (
    default_config_path,
    default_definition_path,
    default_output_dir,
    validate_balance_paths,
    validate_cli_paths,
)
from givp.examples.synthetic_hydropower.runner import (
    load_experiment_config,
    optimize_scenario,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    optimize = subparsers.add_parser("optimize", help="reproduce GIVP scenarios")
    optimize.add_argument("--config", type=Path, required=True)
    optimize.add_argument("--definition", type=Path, required=True)
    optimize.add_argument("--output-dir", type=Path, required=True)
    optimize.add_argument("--seed", type=int, default=42)
    balance = subparsers.add_parser("balance", help="evaluate JSON power schedules")
    balance.add_argument("--request", type=Path, required=True)
    balance.add_argument("--output", type=Path, required=True)
    subparsers.add_parser("worker", help="serve newline-delimited JSON requests")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run optimization, batch balance, or persistent balance-worker commands."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0].startswith("--"):
        arguments.insert(0, "optimize")
    args = _build_parser().parse_args(arguments)
    if args.command == "optimize":
        _run_optimization(args)
    elif args.command == "balance":
        _run_balance(args.request, args.output)
    else:
        run_worker(input_stream=sys.stdin, output_stream=sys.stdout)


def _run_balance(request_path: Path, output_path: Path) -> None:
    """Evaluate one protocol batch and atomically persist its JSON response."""
    request, output = validate_balance_paths(request_path, output_path)
    payload = json.loads(request.read_text(encoding="utf-8"))
    response = evaluate_batch(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(response, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def _run_optimization(args: argparse.Namespace) -> None:
    """Run configured scenarios and write the legacy GIVP CSV/JSON artifacts."""
    validate_cli_paths(args.config, args.definition, args.output_dir)
    config_path = default_config_path().resolve(strict=True)
    definition_path = default_definition_path().resolve(strict=True)
    output_dir = default_output_dir().resolve(strict=False)
    experiment = load_experiment_config(config_path, definition_path)
    output_dir.mkdir(parents=True, exist_ok=True)
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
        pd.DataFrame(rows).to_csv(output_dir / f"{scenario_name}.csv", index=False)
        summaries.append(
            {
                "scenario": scenario_name,
                "energy_mwh": result.energy_mwh,
                "level_penalty": result.level_penalty,
                "objective": result.objective,
            }
        )
    (output_dir / "summary.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
