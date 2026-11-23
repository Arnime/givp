# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Tests for the synthetic-hydropower GIVP tuning helpers."""

from __future__ import annotations

import csv
import json
from dataclasses import fields
from pathlib import Path
from time import sleep
from types import SimpleNamespace

import optuna
import pytest

from benchmarks.tuning.hydropower import multiscenario, trials
from benchmarks.tuning.hydropower.config import (
    _config_from_params,
    _suggest_config,
    _suggest_global_config,
)
from benchmarks.tuning.hydropower.reference import (
    _load_de_reference,
    _load_reference,
    _load_seed_configs,
)
from benchmarks.tuning.hydropower.trials import (
    PRIORITY_SCENARIOS,
    PROTECTED_SCENARIOS,
    TrialExecutionError,
    _passes_non_regression,
    _robust_score,
    _run_multi_trial,
    _run_process,
    _scenario_score,
)
from benchmarks.tuning.hydropower.validation import analyze_validation


def test_multiscenario_cli_passes_reference_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run_tuning(benchmark_root: Path, **kwargs: object) -> dict[str, object]:
        captured["benchmark_root"] = benchmark_root
        captured.update(kwargs)
        return {"metadata": {"best_value": 1.0}}

    monkeypatch.setattr(multiscenario, "run_tuning", fake_run_tuning)
    output = tmp_path / "best.json"
    benchmark_root = tmp_path / "benchmark"
    de_reference = tmp_path / "de.csv"
    reference_run = tmp_path / "runs.csv"
    seed_config = tmp_path / "seed.json"

    exit_code = multiscenario.main(
        [
            "--benchmark-root",
            str(benchmark_root),
            "--scenarios",
            "typical",
            "flood",
            "--study-name",
            "test-study",
            "--de-reference",
            str(de_reference),
            "--reference-runs",
            str(reference_run),
            "--reference-algorithms",
            "DE",
            "UPSO",
            "--eval-seed-start",
            "1",
            "--seed-config",
            str(seed_config),
            "--seed-config",
            str(seed_config),
            "--seed-config",
            str(seed_config),
            "--seed-config",
            str(seed_config),
            "--validation-profile-template",
            str(tmp_path / "template.json"),
            "--validation-profile-output",
            str(tmp_path / "validation.json"),
            "--output",
            str(output),
        ]
    )

    settings = captured["reference_settings"]
    assert isinstance(settings, multiscenario._ReferenceSettings)
    assert settings.de_reference_path == de_reference
    assert settings.seed_config_paths == [seed_config] * 4
    assert settings.reference_paths == [reference_run]
    assert settings.reference_algorithms == ["DE", "UPSO"]
    assert captured["eval_seed_start"] == 1
    assert len(settings.seed_config_paths) == 4
    assert captured["benchmark_root"] == benchmark_root
    assert exit_code == 0
    assert output.exists()


def test_prepared_global_search_cli_fixes_scenarios_seeds_and_budgets() -> None:
    scenarios = [
        "downstream_dominant",
        "dry_stable",
        "dry_variable",
        "flood",
        "typical",
        "upstream_peak",
        "wet_rising",
    ]
    args = multiscenario._build_parser().parse_args(
        [
            "--benchmark-root",
            "benchmark",
            "--scenarios",
            *scenarios,
            "--n-trials",
            "16",
            "--n-eval-seeds",
            "3",
            "--eval-seed-start",
            "1",
            "--max-iter",
            "80",
            "--time-limit",
            "300",
            "--study-name",
            "global-search",
            "--seed-config",
            "incumbent.json",
            "--seed-config",
            "warm1.json",
            "--seed-config",
            "warm2.json",
            "--seed-config",
            "warm3.json",
            "--reference-algorithms",
            "DE",
            "PSO",
            "UPSO",
            "--validation-profile-template",
            "template.json",
            "--validation-profile-output",
            "validation.json",
            "--output",
            "result.json",
        ]
    )

    assert args.scenarios == scenarios
    assert args.n_trials == 16
    assert args.n_eval_seeds == 3
    assert args.eval_seed_start == 1
    assert args.max_iter == 80
    assert args.time_limit == 300.0
    assert args.validation_seeds == list(range(49, 59))
    assert args.reference_algorithms == ["DE", "PSO", "UPSO"]


def test_screen_trial_budget_does_not_subtract_waiting_warm_starts() -> None:
    study = optuna.create_study()
    for _ in range(4):
        study.enqueue_trial({}, user_attrs={"campaign_phase": "screen"})

    assert multiscenario._remaining_screen_trial_budget(study.trials, 16) == 16

    for _ in range(12):
        trial = study.ask()
        trial.set_user_attr("campaign_phase", "screen")
        study.tell(trial, 0.0)
    study.enqueue_trial({}, user_attrs={"campaign_phase": "extension"})

    assert multiscenario._remaining_screen_trial_budget(study.trials, 16) == 4


def _write_runs(path: Path, rows: list[tuple[str, str, float]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["scenario", "algorithm", "objective"])
        writer.writerows(rows)
    return path


def test_reference_is_best_competitor_mean_per_scenario(tmp_path: Path) -> None:
    first = _write_runs(
        tmp_path / "a.csv",
        [("typical", "DE", 10.0), ("typical", "DE", 20.0), ("flood", "DE", 5.0)],
    )
    second = _write_runs(
        tmp_path / "b.csv",
        [
            ("typical", "UPSO", 12.0),
            ("typical", "UPSO", 14.0),
            ("flood", "PSO", 9.0),
            ("typical", "GIVP", -100.0),
        ],
    )

    reference, winners = _load_reference(
        [first, second], ["typical", "flood"], ["DE", "PSO", "UPSO"]
    )

    assert reference == {"typical": 13.0, "flood": 5.0}
    assert winners == {"typical": "UPSO", "flood": "DE"}


def test_reference_requires_rows_and_keeps_de_compatibility(tmp_path: Path) -> None:
    runs = _write_runs(tmp_path / "runs.csv", [("typical", "DE", 4.0)])

    assert _load_de_reference(runs, ["typical"]) == {"typical": 4.0}
    assert _load_de_reference(None, ["typical"]) == {"typical": 0.0}
    with pytest.raises(ValueError, match="flood"):
        _load_reference([runs], ["flood"], ["DE"])


def test_seed_configs_load_archived_profile_without_changing_parameters(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(
        """
        {
          "profiles": {
            "GIVP": {
              "alpha": 0.24,
              "adaptive_alpha": true,
              "alpha_min": 0.18,
              "alpha_max": 0.41,
              "vnd_iterations": 67,
              "ils_iterations": 9,
              "perturbation_strength": 17,
              "use_elite_pool": false,
              "elite_size": 5,
              "path_relink_frequency": 10,
              "num_candidates_per_step": 13,
              "early_stop_threshold": 80,
              "use_convergence_monitor": false,
              "max_iterations": 80,
              "time_limit_seconds": 300
            }
          }
        }
        """,
        encoding="utf-8",
    )

    [params] = _load_seed_configs([profile])

    assert params["alpha_min"] == 0.18
    assert params["alpha_max"] == 0.41
    assert params["alpha"] == 0.24
    assert "max_iterations" not in params
    assert "time_limit_seconds" not in params
    assert "elite_size" not in params
    assert "path_relink_frequency" not in params


def test_multi_trial_uses_explicit_seed_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    study = optuna.create_study()
    trial = study.ask()
    seen_seeds: list[int] = []
    monkeypatch.setattr(
        trials, "_suggest_global_config", lambda *args, **kwargs: object()
    )

    def fake_run_isolated(definition, config, seed, *, timeout_seconds):
        seen_seeds.append(seed)
        return {
            "objective": 90.0,
            "evaluations": 100,
            "iterations": 2,
            "elapsed_seconds": 1.0,
            "termination": "evaluation_limit",
        }

    monkeypatch.setattr(trials, "_run_isolated", fake_run_isolated)
    definitions = [
        SimpleNamespace(scenario=name, bounds=[])
        for name in sorted(PRIORITY_SCENARIOS | PROTECTED_SCENARIOS)
    ]
    references = {definition.scenario: 100.0 for definition in definitions}

    score = trials._run_multi_trial(
        trial,
        definitions,
        references,
        n_eval_seeds=1,
        max_iter=80,
        time_limit=300.0,
        eval_seed_start=1,
    )

    assert seen_seeds == [1] * len(definitions)
    assert trial.user_attrs["evaluation_seeds"] == [1]
    assert score == pytest.approx(-0.1)
    assert len(trial.user_attrs["run_records"]) == len(definitions)
    assert trial.user_attrs["run_records"][0]["termination"] == "evaluation_limit"


def test_scenario_score_is_relative_gap() -> None:
    assert _scenario_score(90.0, 100.0) == pytest.approx(-0.1)
    assert _scenario_score(-110.0, -100.0) == pytest.approx(-0.1)
    assert _scenario_score(0.5, 0.0) == pytest.approx(0.5)


def test_global_config_respects_bounded_ranges_and_alpha_ordering() -> None:
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=7))
    trial = study.ask()

    config = _suggest_global_config(trial, time_limit=300.0)

    assert 0.14 <= config.alpha <= 0.32
    assert config.alpha_min <= config.alpha <= config.alpha_max
    assert 40 <= config.vnd_iterations <= 80
    assert 5 <= config.ils_iterations <= 12
    assert 6 <= config.perturbation_strength <= 20
    assert 6 <= config.num_candidates_per_step <= 18
    assert config.max_iterations == 80
    assert config.early_stop_threshold == 80
    assert config.use_convergence_monitor is False
    assert config.max_evaluations == 15000
    assert config.time_limit == 300.0
    if config.use_elite_pool:
        assert 3 <= config.elite_size <= 8
        assert 5 <= config.path_relink_frequency <= 12


def test_global_robust_score_weights_focus_and_tail() -> None:
    scenario_scores = {name: 0.0 for name in PRIORITY_SCENARIOS | PROTECTED_SCENARIOS}
    scenario_scores["downstream_dominant"] = 1.0
    scenario_scores["dry_variable"] = 0.5

    assert _robust_score(scenario_scores) == pytest.approx(0.375)


def test_non_regression_guardrail_only_checks_protected_scenarios() -> None:
    incumbent = {name: 0.0 for name in PRIORITY_SCENARIOS | PROTECTED_SCENARIOS}
    candidate = dict(incumbent)
    candidate["dry_stable"] = 0.05
    candidate["downstream_dominant"] = 20.0
    assert _passes_non_regression(candidate, incumbent)
    candidate["typical"] = 0.0501
    assert not _passes_non_regression(candidate, incumbent)


def _slow_worker(send_connection, delay: float) -> None:
    sleep(delay)
    send_connection.send({"status": "ok"})
    send_connection.close()


def test_isolated_worker_timeout_terminates_process() -> None:
    with pytest.raises(TrialExecutionError, match="timed out"):
        _run_process(_slow_worker, (2.0,), timeout_seconds=0.1)


def test_multi_trial_records_failed_execution_and_fails_entire_trial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    study = optuna.create_study()
    trial = study.ask()
    monkeypatch.setattr(
        trials, "_suggest_global_config", lambda *args, **kwargs: object()
    )

    def timeout(*args, **kwargs):
        raise TrialExecutionError("run timed out after 330 seconds")

    monkeypatch.setattr(trials, "_run_isolated", timeout)
    definition = SimpleNamespace(scenario="dry_stable", bounds=[])

    with pytest.raises(TrialExecutionError):
        _run_multi_trial(
            trial,
            [definition],
            {"dry_stable": 100.0},
            n_eval_seeds=1,
            max_iter=80,
            time_limit=300.0,
            eval_seed_start=1,
        )

    assert trial.user_attrs["run_records"][0]["status"] == "failed"
    assert trial.user_attrs["run_records"][0]["optimizer_seed"] == 1


def test_validation_profile_generator_and_paired_analysis(tmp_path: Path) -> None:
    from benchmarks.tuning.hydropower.multiscenario import _build_validation_profile
    from benchmarks.tuning.hydropower.validation import HOLDOUT_SEEDS, SCENARIOS

    template = tmp_path / "template.json"
    source = {
        "schema_version": "synthetic-hydropower/sog-comparison-v1",
        "max_evaluations": 15000,
        "profiles": {name: {} for name in ("DE", "PSO", "UPSO", "GIVP")},
    }
    template.write_text(json.dumps(source), encoding="utf-8")
    from givp import GIVPConfig

    params = {
        field.name: getattr(GIVPConfig(), field.name) for field in fields(GIVPConfig())
    }
    output_profile = _build_validation_profile(template, HOLDOUT_SEEDS, params)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(output_profile), encoding="utf-8")

    runs_path = tmp_path / "runs.csv"
    with runs_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["scenario", "optimizer_seed", "algorithm", "objective"],
        )
        writer.writeheader()
        for scenario in SCENARIOS:
            for seed in HOLDOUT_SEEDS:
                for algorithm in ("DE", "PSO", "UPSO"):
                    writer.writerow(
                        {
                            "scenario": scenario,
                            "optimizer_seed": seed,
                            "algorithm": algorithm,
                            "objective": 10.0,
                        }
                    )
                writer.writerow(
                    {
                        "scenario": scenario,
                        "optimizer_seed": seed,
                        "algorithm": "GIVP",
                        "objective": 0.0,
                    }
                )
    reference_path = tmp_path / "reference.csv"
    with reference_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["scenario", "algorithm", "objective"]
        )
        writer.writeheader()
        for scenario in SCENARIOS:
            for algorithm in ("DE", "PSO", "UPSO"):
                for _ in range(5):
                    writer.writerow(
                        {
                            "scenario": scenario,
                            "algorithm": algorithm,
                            "objective": 10.0,
                        }
                    )

    report = analyze_validation(runs_path, reference_path, profile_path)

    assert report["holdout_seeds"] == list(HOLDOUT_SEEDS)
    comparisons = report["comparisons"]
    assert all(
        comparisons[name]["superiority_supported"] for name in ("DE", "PSO", "UPSO")
    )


def test_validation_profile_rejects_mismatched_holdout_budget(tmp_path: Path) -> None:
    from benchmarks.tuning.hydropower.validation import _validate_profile

    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "optimizer_seeds": list(range(44, 54)),
                "max_evaluations": 15000,
                "profiles": {
                    **{name: {} for name in ("DE", "PSO", "UPSO")},
                    "GIVP": {"time_limit_seconds": 300.0},
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="49 through 58"):
        _validate_profile(profile)


def test_max_iterations_is_tuned_when_a_minimum_is_given() -> None:
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=1))
    trial = study.ask()

    config = _suggest_config(trial, max_iter=400, time_limit=300.0, max_iter_min=40)

    assert 40 <= config.max_iterations <= 400
    assert trial.params["max_iterations"] == config.max_iterations
    assert config.early_stop_threshold <= config.max_iterations
    assert config.max_evaluations == 15000
    assert config.time_limit == 300.0
    rebuilt = _config_from_params(dict(trial.params), max_iter=999, time_limit=300.0)
    assert rebuilt.max_iterations == config.max_iterations


def test_max_iterations_stays_fixed_without_a_minimum() -> None:
    study = optuna.create_study()
    trial = study.ask()

    config = _suggest_config(trial, max_iter=80, time_limit=300.0)

    assert config.max_iterations == 80
    assert "max_iterations" not in trial.params
    invalid_trial = optuna.create_study().ask()
    with pytest.raises(ValueError, match="max_iter_min"):
        _suggest_config(
            invalid_trial,
            max_iter=80,
            time_limit=300.0,
            max_iter_min=81,
        )


def test_rebuild_config_defaults_fixed_global_search_parameters() -> None:
    params = {
        "alpha": 0.2,
        "adaptive_alpha": True,
        "alpha_min": 0.1,
        "alpha_max": 0.3,
        "vnd_iterations": 60,
        "ils_iterations": 8,
        "perturbation_strength": 10,
        "use_elite_pool": False,
        "num_candidates_per_step": 12,
    }

    config = _config_from_params(params, max_iter=80, time_limit=300.0)

    assert config.early_stop_threshold == 80
    assert config.use_convergence_monitor is False
