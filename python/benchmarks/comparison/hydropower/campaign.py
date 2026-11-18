# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Execute a resumable historical-profile comparison on synthetic hydropower."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.comparison.hydropower.budget import number
from benchmarks.comparison.hydropower.execution import (
    ALGORITHMS,
    OptimizerOutcome,
    run_optimizer,
    zero_baseline,
)
from givp.examples.synthetic_hydropower.benchmark.definition import (
    DeterministicDefinition,
    FrozenScenario,
    load_deterministic_definition,
)
from givp.examples.synthetic_hydropower.model import CascadeConfig
from givp.examples.synthetic_hydropower.optimization import OptimizationDefinition
from givp.examples.synthetic_hydropower.scenarios import generate_inflows

_ALGORITHMS = ALGORITHMS
_RUNS_CSV_NAME = "runs.csv"
_METADATA_NAME = "campaign_metadata.json"
_SCHEMA_VERSIONS = (
    "synthetic-hydropower/sog-comparison-v1",
    "synthetic-hydropower/sog-comparison-v2",
)
# Source revisions audited for SOG_ALGORITHM_MAPPING.md. No SOG code is imported.
_SOG_REFERENCE = {
    "notebook_repository_commit": "9194f6351ae0adccff0f83c7ddc7c01c5f7d46b2",
    "backend_repository_commit": "280c876930d6eaef555c9236a8eab0562681e9b6",
    "wrappers": "app/internal/modules/algoritmo/otimizacao/{de,pso,utils}.py",
}
_RUN_FIELDS = (
    "profile_kind",
    "scenario",
    "scenario_seed",
    "replication",
    "optimizer_seed",
    "algorithm",
    "objective",
    "optimizer_best_objective",
    "energy_mwh",
    "level_penalty",
    "unit_switch_penalty",
    "early_switch_penalty",
    "power_deficit_mwh",
    "spill_hm3",
    "final_level_a_m",
    "final_level_b_m",
    "iterations",
    "evaluations",
    "elapsed_seconds",
    "termination",
    "baseline_objective",
    "baseline_energy_mwh",
)


def main() -> None:
    """Run selected campaign tasks and append completed results atomically by row."""
    args = _build_parser().parse_args()
    benchmark_root = args.benchmark_root.resolve(strict=True)
    profile_payload = _load_profile(args.profile.resolve(strict=True))
    _apply_campaign_overrides(
        profile_payload,
        givp_variant=args.givp_variant,
        max_evaluations=args.max_evaluations,
    )
    deterministic = _load_benchmark(benchmark_root)
    output_dir = args.output_dir.resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = _profiles(profile_payload)
    seeds = _select_seeds(profile_payload, args.replications)
    scenarios = _select_scenarios(deterministic, args.scenarios)
    algorithms = _select_algorithms(args.algorithms, profiles)
    _write_metadata(
        output_dir,
        benchmark_root,
        args.profile,
        profile_payload,
        deterministic,
    )
    _check_runs_header(output_dir / _RUNS_CSV_NAME)
    profile_kind = _profile_kind(profile_payload)
    completed = _completed_tasks(output_dir / _RUNS_CSV_NAME)
    tasks = _tasks(scenarios, algorithms, seeds, completed, args.replications)
    if args.limit is not None:
        tasks = tasks[: args.limit]
    print(f"scheduled {len(tasks)} unfinished optimizer run(s)")
    for index, (scenario, algorithm, replication, seed) in enumerate(tasks, start=1):
        definition = _optimization_definition(
            deterministic.cascade, scenario, profiles[algorithm]
        )
        baseline = zero_baseline(definition)
        print(
            f"[{index}/{len(tasks)}] {scenario.definition.name} {algorithm} "
            f"replication={replication} seed={seed}",
            flush=True,
        )
        outcome = run_optimizer(algorithm, definition, profiles[algorithm], seed)
        _append_run(
            output_dir / _RUNS_CSV_NAME,
            _run_row(
                scenario,
                algorithm,
                replication,
                seed,
                outcome,
                baseline,
                profile_kind=profile_kind,
                flow_to_volume_hm3=deterministic.cascade.flow_to_volume_hm3,
            ),
        )
        _append_solution(
            output_dir / "best_solutions.jsonl",
            scenario,
            algorithm,
            replication,
            seed,
            outcome,
        )
        print(
            f"  objective={outcome.objective:.6f} energy={outcome.diagnostics['energy_mwh']:.6f} "
            f"evaluations={outcome.evaluations} termination={outcome.termination} "
            f"elapsed={outcome.elapsed_seconds:.1f}s",
            flush=True,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--algorithms", nargs="+", choices=_ALGORITHMS)
    parser.add_argument("--scenarios", nargs="+")
    parser.add_argument(
        "--givp-variant",
        choices=("current", "groups", "repair", "multiscale", "combined"),
        help="override the GIVP structural variant for an ablation campaign",
    )
    parser.add_argument(
        "--max-evaluations",
        type=int,
        help="override the shared physical-evaluation budget",
    )
    parser.add_argument(
        "--replications",
        type=int,
        default=5,
        help="number of paired, frozen optimizer seeds to execute (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="run at most this many unfinished tasks; useful for a smoke test",
    )
    return parser


def _apply_campaign_overrides(
    payload: dict[str, object],
    *,
    givp_variant: str | None,
    max_evaluations: int | None,
) -> None:
    """Apply explicit CLI overrides while retaining them in campaign metadata."""
    if max_evaluations is not None:
        if max_evaluations < 1:
            raise ValueError("max_evaluations must be positive")
        payload["max_evaluations"] = max_evaluations
    if givp_variant is None:
        return
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, dict):
        raise ValueError("comparison profile must contain profiles")
    givp_profile = raw_profiles.get("GIVP")
    if not isinstance(givp_profile, dict):
        raise ValueError("comparison profile has no GIVP settings")
    givp_profile["ablation_variant"] = givp_variant


def _load_profile(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("comparison profile must be a JSON object")
    if payload.get("schema_version") not in _SCHEMA_VERSIONS:
        raise ValueError("unsupported comparison profile schema_version")
    return payload


def _profile_kind(payload: Mapping[str, object]) -> str:
    kind = payload.get("profile_kind", "legacy-v1")
    if not isinstance(kind, str) or not kind:
        raise ValueError("comparison profile_kind must be a non-empty string")
    return kind


def _load_benchmark(root: Path) -> DeterministicDefinition:
    return load_deterministic_definition(
        root / "config" / "base.json",
        root / "protocols" / "deterministic_balance" / "definition.json",
    )


def _profiles(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, dict):
        raise ValueError("comparison profile must contain profiles")
    givp_profile = raw_profiles.get("GIVP")
    if not isinstance(givp_profile, dict):
        raise ValueError("comparison profile has no GIVP settings")
    time_limit_seconds = number(givp_profile, "time_limit_seconds")
    if not math.isfinite(time_limit_seconds) or time_limit_seconds < 0:
        raise ValueError(
            "comparison time_limit_seconds must be finite and non-negative"
        )
    # v1 profiles always carried a shared 15000 budget; v2 states it explicitly
    # (budget-matched) or omits it to keep each native stopping rule.
    default_budget = (
        15000
        if payload.get("schema_version") == "synthetic-hydropower/sog-comparison-v1"
        else None
    )
    shared_budget = payload.get("max_evaluations", default_budget)
    if shared_budget is not None and (
        not isinstance(shared_budget, int)
        or isinstance(shared_budget, bool)
        or shared_budget < 1
    ):
        raise ValueError("comparison max_evaluations must be a positive integer")
    profiles: dict[str, Mapping[str, object]] = {}
    for algorithm in _ALGORITHMS:
        profile = raw_profiles.get(algorithm)
        if not isinstance(profile, dict):
            raise ValueError(f"comparison profile has no {algorithm} settings")
        normalized = dict(profile)
        normalized["time_limit_seconds"] = time_limit_seconds
        if shared_budget is not None:
            normalized["max_evaluations"] = shared_budget
        profiles[algorithm] = normalized
    return profiles


def _seeds(payload: Mapping[str, object]) -> tuple[int, ...]:
    """Return the optional fixed optimizer seed list, if one was explicitly set."""
    raw_seeds = payload.get("optimizer_seeds")
    if raw_seeds is None:
        return ()
    if not isinstance(raw_seeds, list):
        raise ValueError(
            "comparison profile optimizer_seeds must be a list when present"
        )
    if len(raw_seeds) == 0:
        return ()
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in raw_seeds):
        raise ValueError("optimizer seeds must be integers")
    return tuple(raw_seeds)


def _select_seeds(payload: Mapping[str, object], replications: int) -> tuple[int, ...]:
    """Select a reproducible prefix of the mandatory paired seed list."""
    seeds = _seeds(payload)
    if not seeds:
        raise ValueError("comparison profile must define optimizer_seeds")
    if not 1 <= replications <= len(seeds):
        raise ValueError(
            f"replications must be between 1 and {len(seeds)}, got {replications}"
        )
    return seeds[:replications]


def _select_scenarios(
    deterministic: DeterministicDefinition, requested: list[str] | None
) -> tuple[FrozenScenario, ...]:
    if requested is None:
        return deterministic.scenarios
    selected = tuple(
        scenario
        for scenario in deterministic.scenarios
        if scenario.definition.name in requested
    )
    missing = set(requested) - {scenario.definition.name for scenario in selected}
    if missing:
        raise ValueError(f"unknown benchmark scenarios: {', '.join(sorted(missing))}")
    return selected


def _select_algorithms(
    requested: list[str] | None, profiles: Mapping[str, Mapping[str, object]]
) -> tuple[str, ...]:
    selected = tuple(requested) if requested is not None else _ALGORITHMS
    missing = set(selected) - profiles.keys()
    if missing:
        raise ValueError(f"comparison profile has no selected algorithms: {missing}")
    return selected


def _optimization_definition(
    cascade: CascadeConfig,
    scenario: FrozenScenario,
    profile: Mapping[str, object],
) -> OptimizationDefinition:
    inflows = generate_inflows(scenario.definition, cascade.periods, scenario.seed)
    return OptimizationDefinition(
        scenario=scenario.definition.name,
        seed=scenario.seed,
        periods=cascade.periods,
        minimum_power_mw=np.asarray(
            [plant.min_power_mw for plant in cascade.plants], dtype=np.float64
        ),
        maximum_power_mw=np.asarray(
            [plant.max_power_mw for plant in cascade.plants], dtype=np.float64
        ),
        incremental_inflow_m3s=inflows,
        optimizer=profile,
    )


def _tasks(
    scenarios: Iterable[FrozenScenario],
    algorithms: Iterable[str],
    seeds: Iterable[int | None],
    completed: set[tuple[str, str, int]],
    replications: int | None = None,
) -> list[tuple[FrozenScenario, str, int, int | None]]:
    seed_values = tuple(seeds)
    if not seed_values:
        raise ValueError("campaign tasks require at least one optimizer seed")
    return [
        (scenario, algorithm, replication, seed)
        for scenario in scenarios
        for algorithm in algorithms
        for replication, seed in enumerate(seed_values, start=1)
        if (scenario.definition.name, algorithm, replication) not in completed
    ]


def _completed_tasks(path: Path) -> set[tuple[str, str, int]]:
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as stream:
        return {
            (row["scenario"], row["algorithm"], int(row["replication"]))
            for row in csv.DictReader(stream)
        }


def _write_metadata(
    output_dir: Path,
    benchmark_root: Path,
    profile_path: Path,
    profile: Mapping[str, object],
    deterministic: DeterministicDefinition,
) -> None:
    """Write metadata once; refuse to resume a directory made by another setup.

    The profile (including its paired seed list and any CLI override) must match
    exactly. ``--replications`` may still grow, since replication ``k`` always
    maps to the ``k``-th seed of that list.
    """
    destination = output_dir / _METADATA_NAME
    effective_profile = dict(profile)
    effective_profile["profiles"] = {
        algorithm: dict(settings) for algorithm, settings in _profiles(profile).items()
    }
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing.get("profile") != effective_profile:
            raise ValueError(
                f"{destination} was produced with a different profile or "
                "override; use a new --output-dir instead of mixing campaigns"
            )
        return
    payload = {
        "benchmark_id": deterministic.benchmark_id,
        "benchmark_root": str(benchmark_root),
        "profile_path": str(profile_path.resolve(strict=True)),
        "profile_kind": _profile_kind(profile),
        "profile": effective_profile,
        "optimizer_seeds": list(_seeds(profile)),
        "scenarios": [asdict(scenario) for scenario in deterministic.scenarios],
        "evaluation_accounting": (
            "evaluations counts physical objective calls made by the optimizer; "
            "GIVP cache hits and the final projected re-evaluation are excluded"
        ),
        "software": _software_versions(),
        "givp_git_commit": _git_commit(benchmark_root),
        "sog_reference": _SOG_REFERENCE,
        "result_files": {"runs": "runs.csv", "solutions": "best_solutions.jsonl"},
    }
    destination.write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )


def _software_versions() -> dict[str, str]:
    packages = ("givp", "numpy", "scipy", "pyswarm")
    return {
        "python": platform.python_version(),
        **{package: _package_version(package) for package in packages},
    }


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not installed"


def _git_commit(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _check_runs_header(path: Path) -> None:
    if not path.is_file():
        return
    with path.open(encoding="utf-8", newline="") as stream:
        header = next(csv.reader(stream), None)
    if header is not None and tuple(header) != _RUN_FIELDS:
        raise ValueError(f"{path} uses an older column layout; use a new --output-dir")


def _run_row(
    scenario: FrozenScenario,
    algorithm: str,
    replication: int,
    seed: int | None,
    outcome: OptimizerOutcome,
    baseline: Mapping[str, float],
    *,
    profile_kind: str,
    flow_to_volume_hm3: float,
) -> dict[str, Any]:
    simulation = outcome.physical_result["simulation"]
    if not isinstance(simulation, dict):
        raise RuntimeError("optimizer outcome has no simulation payload")
    final_levels = np.asarray(simulation["level_m"], dtype=float)[:, -1]
    spill_hm3 = float(
        np.sum(np.asarray(simulation["spill_flow_m3s"], dtype=float))
        * flow_to_volume_hm3
    )
    row: dict[str, Any] = {
        "profile_kind": profile_kind,
        "scenario": scenario.definition.name,
        "scenario_seed": scenario.seed,
        "replication": replication,
        "optimizer_seed": seed,
        "algorithm": algorithm,
        "objective": outcome.objective,
        "optimizer_best_objective": outcome.optimizer_best_objective,
        "energy_mwh": outcome.diagnostics["energy_mwh"],
        "level_penalty": outcome.diagnostics["level_penalty"],
        "unit_switch_penalty": outcome.diagnostics["unit_switch_penalty"],
        "early_switch_penalty": outcome.diagnostics["early_switch_penalty"],
        "power_deficit_mwh": outcome.diagnostics["power_deficit_mwh"],
        "spill_hm3": spill_hm3,
        "final_level_a_m": float(final_levels[0]),
        "final_level_b_m": float(final_levels[1]),
        "iterations": outcome.iterations,
        "evaluations": outcome.evaluations,
        "elapsed_seconds": outcome.elapsed_seconds,
        "termination": outcome.termination,
        "baseline_objective": baseline["objective"],
        "baseline_energy_mwh": baseline["energy_mwh"],
    }
    return row


def _append_run(path: Path, row: dict[str, Any]) -> None:
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=_RUN_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)  # type: ignore[arg-type]


def _append_solution(
    path: Path,
    scenario: FrozenScenario,
    algorithm: str,
    replication: int,
    seed: int | None,
    outcome: OptimizerOutcome,
) -> None:
    payload = {
        "scenario": scenario.definition.name,
        "scenario_seed": scenario.seed,
        "replication": replication,
        "optimizer_seed": seed,
        "algorithm": algorithm,
        "raw_vector": outcome.vector.tolist(),
        "summary": outcome.diagnostics,
        "simulation": outcome.physical_result,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
