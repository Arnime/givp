# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Focused tests for the resumable synthetic-hydropower comparison tooling."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.comparison.hydropower.campaign import (
    _RUN_FIELDS,
    _apply_campaign_overrides,
    _load_benchmark,
    _load_profile,
    _optimization_definition,
    _profiles,
    _run_row,
    _seeds,
    _select_seeds,
    _tasks,
    _write_metadata,
)
from benchmarks.comparison.hydropower.execution import run_optimizer, zero_baseline
from benchmarks.comparison.hydropower.reporting import render_reports
from givp.examples.synthetic_hydropower.optimization import project_power_vector
from givp.examples.synthetic_hydropower.paths import project_root


def test_campaign_uses_all_frozen_scenarios_and_paired_seeds() -> None:
    """The campaign expands to seven scenarios times the selected seeds."""
    benchmark = _load_benchmark(_benchmark_root())
    profile = {"max_iterations": 1}
    definitions = [
        _optimization_definition(benchmark.cascade, scenario, profile)
        for scenario in benchmark.scenarios
    ]
    tasks = _tasks(benchmark.scenarios, ("DE",), range(10), set())

    assert len(definitions) == 7
    assert all(
        definition.incremental_inflow_m3s.shape == (2, 24) for definition in definitions
    )
    assert len(tasks) == 70


@pytest.mark.parametrize("name", ["sog_reproduction.json", "budget_matched.json"])
def test_versioned_profiles_preserve_the_sog_controls(name: str) -> None:
    """Both v2 profiles carry the SOG wrapper controls for every algorithm."""
    payload = _load_profile(_interop() / name)
    profiles = _profiles(payload)

    assert _seeds(payload) == (44, 45, 46, 47, 48)
    assert profiles["DE"]["strategy"] == "best1bin"
    assert profiles["DE"]["population_multiplier"] == 20
    assert profiles["DE"]["max_iterations"] == 100
    assert profiles["DE"]["tolerance"] == 0.09
    for algorithm in ("PSO", "UPSO"):
        assert profiles[algorithm]["population_size"] == 200
        assert profiles[algorithm]["max_generations"] == 250
        assert profiles[algorithm]["inertia"] == 0.5
    assert (profiles["PSO"]["c1"], profiles["PSO"]["c2"]) == (1.0, 1.0)
    assert (profiles["UPSO"]["c1"], profiles["UPSO"]["c2"]) == (0.6, 0.4)
    assert "unification_factor" not in profiles["UPSO"]
    assert profiles["GIVP"]["max_iterations"] == 40
    assert all(
        profile["time_limit_seconds"] == profiles["GIVP"]["time_limit_seconds"]
        for profile in profiles.values()
    )


def test_budget_matched_profile_caps_every_algorithm() -> None:
    profiles = _profiles(_load_profile(_interop() / "budget_matched.json"))

    assert all(profile["max_evaluations"] == 15000 for profile in profiles.values())
    assert all(
        profile["time_limit_seconds"] == profiles["GIVP"]["time_limit_seconds"]
        for profile in profiles.values()
    )


def test_balanced_profile_applies_its_300_second_limit_to_every_algorithm() -> None:
    profiles = _profiles(_load_profile(_interop() / "balanced_hyperparameters.json"))

    assert all(profile["time_limit_seconds"] == 300 for profile in profiles.values())


def test_sog_budget_matched_300s_profile_is_valid_and_shared() -> None:
    profiles = _profiles(_load_profile(_interop() / "budget_matched_300s.json"))

    assert all(profile["max_evaluations"] == 15000 for profile in profiles.values())
    assert all(profile["time_limit_seconds"] == 300 for profile in profiles.values())
    assert (profiles["UPSO"]["c1"], profiles["UPSO"]["c2"]) == (0.6, 0.4)


def test_true_upso_profile_uses_shared_budget_and_unification_controls() -> None:
    profiles = _profiles(
        _load_profile(_interop() / "budget_matched_300s_true_upso.json")
    )

    assert all(profile["max_evaluations"] == 15000 for profile in profiles.values())
    assert all(profile["time_limit_seconds"] == 300 for profile in profiles.values())
    assert profiles["UPSO"]["engine"] == "pyswarm 0.6 unified pso"
    assert profiles["UPSO"]["unification_factor"] == 0.3
    assert profiles["UPSO"]["neighborhood_size"] == 3
    assert (profiles["UPSO"]["w_min"], profiles["UPSO"]["w_max"]) == (0.6, 0.9)
    assert (profiles["UPSO"]["c1"], profiles["UPSO"]["c2"]) == (0.6, 0.4)


def test_givp_80_profile_changes_only_givp_iteration_budget() -> None:
    baseline = _profiles(_load_profile(_interop() / "budget_matched_300s.json"))
    increased = _profiles(
        _load_profile(_interop() / "budget_matched_300s_givp_80.json")
    )

    assert increased["GIVP"]["max_iterations"] == 80
    assert all(
        increased[algorithm] == baseline[algorithm]
        for algorithm in ("DE", "PSO", "UPSO")
    )
    assert all(
        increased["GIVP"][field] == baseline["GIVP"][field]
        for field in baseline["GIVP"]
        if field != "max_iterations"
    )


def test_sog_reproduction_profile_keeps_native_stopping() -> None:
    payload = _load_profile(_interop() / "sog_reproduction.json")

    assert payload["profile_kind"] == "sog-reproduction"
    assert all("max_evaluations" not in p for p in _profiles(payload).values())


def test_campaign_can_select_a_reproducible_subset_of_frozen_seeds() -> None:
    """Timing runs use a prefix without changing the published seed list."""
    payload = _load_profile(_interop() / "budget_matched.json")

    assert _select_seeds(payload, 1) == (44,)
    assert _select_seeds(payload, 5) == (44, 45, 46, 47, 48)


def test_campaign_overrides_persist_ablation_variant_and_budget() -> None:
    payload = _load_profile(_interop() / "sog_reproduction.json")
    _apply_campaign_overrides(payload, givp_variant="groups", max_evaluations=120)
    assert payload["max_evaluations"] == 120
    assert _profiles(payload)["GIVP"]["ablation_variant"] == "groups"
    assert all(
        profile["max_evaluations"] == 120 for profile in _profiles(payload).values()
    )


def test_campaign_rejects_missing_seeds() -> None:
    """Scientific campaigns must never silently use unrecorded random seeds."""
    payload = {
        "schema_version": "synthetic-hydropower/sog-comparison-v2",
        "profiles": {
            "DE": {"max_iterations": 1},
            "PSO": {"population_size": 1, "max_generations": 1},
            "UPSO": {"population_size": 1, "max_generations": 1},
            "GIVP": {"max_iterations": 1},
        },
    }

    with pytest.raises(ValueError, match="optimizer_seeds"):
        _select_seeds(payload, 3)


def test_campaign_refuses_to_mix_profiles_in_one_directory(tmp_path: Path) -> None:
    """Resuming with another profile would silently mix incomparable runs."""
    benchmark = _load_benchmark(_benchmark_root())
    first = _load_profile(_interop() / "budget_matched.json")
    second = _load_profile(_interop() / "sog_reproduction.json")
    _write_metadata(
        tmp_path,
        _benchmark_root(),
        _interop() / "budget_matched.json",
        first,
        benchmark,
    )
    metadata = json.loads((tmp_path / "campaign_metadata.json").read_text("utf-8"))

    assert metadata["profile_kind"] == "budget-matched"
    assert metadata["optimizer_seeds"] == [44, 45, 46, 47, 48]
    assert "scipy" in metadata["software"]
    assert metadata["sog_reference"]["notebook_repository_commit"].startswith("9194f63")
    # Resuming the same profile (e.g. with more replications) is allowed.
    _write_metadata(
        tmp_path,
        _benchmark_root(),
        _interop() / "budget_matched.json",
        first,
        benchmark,
    )
    with pytest.raises(ValueError, match="different profile"):
        _write_metadata(
            tmp_path,
            _benchmark_root(),
            _interop() / "sog_reproduction.json",
            second,
            benchmark,
        )
    overridden = _load_profile(_interop() / "budget_matched.json")
    _apply_campaign_overrides(overridden, givp_variant="current", max_evaluations=None)
    with pytest.raises(ValueError, match="different profile"):
        _write_metadata(
            tmp_path,
            _benchmark_root(),
            _interop() / "budget_matched.json",
            overridden,
            benchmark,
        )


def test_campaign_rejects_metadata_without_propagated_time_limits(
    tmp_path: Path,
) -> None:
    benchmark = _load_benchmark(_benchmark_root())
    profile = _load_profile(_interop() / "balanced_hyperparameters.json")
    _write_metadata(
        tmp_path,
        _benchmark_root(),
        _interop() / "balanced_hyperparameters.json",
        profile,
        benchmark,
    )
    metadata_path = tmp_path / "campaign_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for algorithm in ("DE", "PSO", "UPSO"):
        metadata["profile"]["profiles"][algorithm].pop("time_limit_seconds")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ValueError, match="different profile"):
        _write_metadata(
            tmp_path,
            _benchmark_root(),
            _interop() / "balanced_hyperparameters.json",
            profile,
            benchmark,
        )


def test_small_de_run_returns_canonical_physical_diagnostics() -> None:
    """One reduced DE smoke run is evaluated by the canonical Python physics."""
    benchmark = _load_benchmark(_benchmark_root())
    definition = _optimization_definition(benchmark.cascade, benchmark.scenarios[2], {})
    profile = {
        "strategy": "best1bin",
        "max_iterations": 1,
        "population_multiplier": 2,
        "tolerance": 0.09,
        "mutation": [0.5, 1.0],
        "recombination": 0.9,
        "execution_workers": 1,
        "polish": False,
        "initialization": "latinhypercube",
    }

    outcome = run_optimizer("DE", definition, profile, seed=44)

    assert np.isfinite(outcome.objective)
    assert outcome.vector.shape == (48,)
    assert outcome.diagnostics["energy_mwh"] >= 0.0
    assert outcome.evaluations > 0
    assert zero_baseline(definition)["objective"] >= outcome.objective


@pytest.mark.parametrize(
    ("algorithm", "c1", "c2"), [("PSO", 1.0, 1.0), ("UPSO", 0.6, 0.4)]
)
def test_small_pyswarm_run_returns_canonical_physical_diagnostics(
    algorithm: str, c1: float, c2: float
) -> None:
    """PSO and UPSO both run the SOG pyswarm engine and record why they stop."""
    benchmark = _load_benchmark(_benchmark_root())
    definition = _optimization_definition(benchmark.cascade, benchmark.scenarios[2], {})
    profile = {
        "population_size": 4,
        "max_generations": 2,
        "inertia": 0.5,
        "c1": c1,
        "c2": c2,
    }
    if algorithm == "UPSO":
        profile["engine"] = "pyswarm 0.6 pso"

    outcome = run_optimizer(algorithm, definition, profile, seed=44)

    assert np.isfinite(outcome.objective)
    assert outcome.vector.shape == (48,)
    assert 4 <= outcome.evaluations <= 12
    assert outcome.termination in {
        "max_iterations",
        "converged_minfunc",
        "converged_minstep",
    }


def test_run_row_records_profile_and_hydraulic_metrics() -> None:
    benchmark = _load_benchmark(_benchmark_root())
    scenario = benchmark.scenarios[2]
    definition = _optimization_definition(benchmark.cascade, scenario, {})
    profile = {
        "population_size": 4,
        "max_generations": 1,
        "inertia": 0.5,
        "c1": 1.0,
        "c2": 1.0,
        "max_evaluations": 6,
    }
    outcome = run_optimizer("PSO", definition, profile, seed=44)

    row = _run_row(
        scenario,
        "PSO",
        1,
        44,
        outcome,
        zero_baseline(definition),
        profile_kind="budget-matched",
        flow_to_volume_hm3=benchmark.cascade.flow_to_volume_hm3,
    )

    assert set(row) == set(_RUN_FIELDS)
    assert row["profile_kind"] == "budget-matched"
    assert row["evaluations"] == 6
    assert row["termination"] == "evaluation_limit"
    assert row["spill_hm3"] >= 0.0
    assert np.isfinite(row["final_level_a_m"])


def test_small_givp_run_uses_repair_groups_and_exact_budget() -> None:
    benchmark = _load_benchmark(_benchmark_root())
    definition = _optimization_definition(benchmark.cascade, benchmark.scenarios[2], {})
    profile = {
        "max_iterations": 5,
        "alpha": 0.12,
        "vnd_iterations": 5,
        "ils_iterations": 2,
        "perturbation_strength": 2,
        "use_elite_pool": False,
        "elite_size": 3,
        "path_relink_frequency": 2,
        "adaptive_alpha": False,
        "alpha_min": 0.12,
        "alpha_max": 0.12,
        "num_candidates_per_step": 5,
        "use_cache": True,
        "cache_size": 100,
        "early_stop_threshold": 10,
        "use_convergence_monitor": False,
        "n_workers": 2,
        "time_limit_seconds": 30,
        "max_evaluations": 20,
        "ablation_variant": "combined",
    }

    outcome = run_optimizer("GIVP", definition, profile, seed=44)

    assert np.isfinite(outcome.objective)
    assert outcome.evaluations == 20
    assert outcome.termination == "evaluation_limit"
    assert np.allclose(
        outcome.vector, project_power_vector(outcome.vector, definition).reshape(-1)
    )


def test_report_renderer_writes_dissertation_artifacts(tmp_path: Path) -> None:
    """The renderer creates CSV, LaTex and figures from completed run rows."""
    rows = [
        {
            "scenario": scenario,
            "algorithm": algorithm,
            "replication": replication,
            "objective": 100.0 + replication + index,
            "energy_mwh": 1_000.0 + index,
            "level_penalty": 0.0,
            "power_deficit_mwh": 0.0,
            "spill_hm3": 0.5 * index,
            "evaluations": 10,
            "elapsed_seconds": 0.1,
        }
        for scenario in ("typical", "flood")
        for index, algorithm in enumerate(("DE", "PSO", "UPSO", "GIVP"))
        for replication in (1, 2)
    ]
    runs_path = tmp_path / "runs.csv"
    with runs_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    paths = render_reports(runs_path, tmp_path / "rendered")

    # 8 core artifacts plus deficit and spill box plots (no level columns given).
    assert len(paths) == 10
    assert all(path.is_file() for path in paths)
    assert "GIVP" in (tmp_path / "rendered" / "summary_by_scenario.tex").read_text(
        encoding="utf-8"
    )
    statistics = (tmp_path / "rendered" / "paired_statistics.csv").read_text(
        encoding="utf-8"
    )
    # Three competitors in two scopes, Holm-corrected together.
    assert statistics.count("GIVP < ") == 6
    assert "holm_p_value" in statistics


def _benchmark_root() -> Path:
    return project_root() / "benchmarks" / "v1.0.0"


def _interop() -> Path:
    return project_root() / "interop" / "v1"
