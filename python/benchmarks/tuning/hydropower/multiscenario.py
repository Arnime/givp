# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Optuna tuning for one global configuration across hydropower scenarios."""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import optuna
import optuna.logging as optuna_logging

from benchmarks.comparison.hydropower.campaign import (
    _load_benchmark,
    _optimization_definition,
)
from benchmarks.tuning.hydropower.config import _config_from_params
from benchmarks.tuning.hydropower.reference import (
    _load_reference,
    _load_seed_configs,
)
from benchmarks.tuning.hydropower.trials import (
    TrialExecutionError,
    _passes_non_regression,
    _robust_score,
    _run_multi_trial,
)

_log = logging.getLogger(__name__)
_SEARCH_PROTOCOL = "givp-global-robust-v1"
_SCREEN_SEED_START = 1
_SCREEN_SEED_COUNT = 3
_EXTENSION_SEED_START = 4
_EXTENSION_SEED_COUNT = 4
_FINAL_VALIDATION_SEEDS = tuple(range(49, 59))


@dataclasses.dataclass(frozen=True)
class _ReferenceSettings:
    de_reference_path: Path | None
    seed_config_paths: Sequence[Path]
    reference_paths: Sequence[Path] = ()
    reference_algorithms: Sequence[str] = ("DE",)


def run_tuning(
    benchmark_root: Path,
    *,
    scenarios: Sequence[str],
    n_trials: int,
    n_eval_seeds: int,
    sampler_seed: int,
    max_iter: int,
    time_limit: float,
    study_name: str,
    storage: str | None,
    reference_settings: _ReferenceSettings,
    verbose: bool,
    max_iter_min: int | None = None,
    trials_csv: Path | None = None,
    eval_seed_start: int = _SCREEN_SEED_START,
    validation_profile_template: Path | None = None,
    validation_profile_output: Path | None = None,
    validation_seeds: Sequence[int] = _FINAL_VALIDATION_SEEDS,
) -> dict[str, object]:
    """Run screening and finalist extension, without executing holdout validation."""
    if not scenarios:
        raise ValueError("at least one scenario is required")
    if n_eval_seeds < 1:
        raise ValueError("n_eval_seeds must be positive")
    if n_eval_seeds != _SCREEN_SEED_COUNT:
        raise ValueError("global screening requires exactly three optimizer seeds")
    if eval_seed_start != _SCREEN_SEED_START:
        raise ValueError(
            f"global search screening seeds must start at {_SCREEN_SEED_START}"
        )
    if n_trials != 16:
        raise ValueError(
            "the prepared global search requires exactly 16 screening trials"
        )
    if len(reference_settings.seed_config_paths) != 4:
        raise ValueError(
            "provide the incumbent followed by exactly three warm-start profiles"
        )
    if validation_profile_template is None or validation_profile_output is None:
        raise ValueError("validation profile template and output paths are required")
    if tuple(validation_seeds) != _FINAL_VALIDATION_SEEDS:
        raise ValueError("the final holdout seeds are fixed at 49 through 58")
    if time_limit != 300.0 or max_iter != 80 or max_iter_min is not None:
        raise ValueError(
            "the prepared search fixes time_limit=300 and max_iterations=80"
        )
    if set(reference_settings.reference_algorithms) != {"DE", "PSO", "UPSO"}:
        raise ValueError("the global tuning reference must include DE, PSO, and UPSO")
    required_scenarios = {
        "dry_stable",
        "dry_variable",
        "typical",
        "upstream_peak",
        "downstream_dominant",
        "wet_rising",
        "flood",
    }
    if set(scenarios) != required_scenarios:
        raise ValueError("the global search must include all seven frozen scenarios")
    if not verbose:
        optuna_logging.set_verbosity(optuna_logging.WARNING)

    deterministic = _load_benchmark(benchmark_root)
    selected = {item.definition.name: item for item in deterministic.scenarios}
    missing = sorted(set(scenarios) - selected.keys())
    if missing:
        raise ValueError(f"unknown benchmark scenarios: {', '.join(missing)}")
    profile = {
        "max_iterations": max_iter,
        "alpha": 0.17,
        "vnd_iterations": 25,
        "ils_iterations": 5,
        "perturbation_strength": 10,
        "use_elite_pool": True,
        "elite_size": 5,
        "path_relink_frequency": 8,
        "num_candidates_per_step": 20,
        "use_cache": True,
        "cache_size": 12000,
        "early_stop_threshold": 48,
        "use_convergence_monitor": True,
        "n_workers": 1,
    }
    definitions = [
        _optimization_definition(deterministic.cascade, selected[name], profile)
        for name in scenarios
    ]
    all_reference_paths = list(reference_settings.reference_paths)
    if reference_settings.de_reference_path is not None:
        all_reference_paths.append(reference_settings.de_reference_path)
    de_reference, reference_winners = _load_reference(
        all_reference_paths, scenarios, reference_settings.reference_algorithms
    )
    seed_configs = _load_seed_configs(reference_settings.seed_config_paths)
    # Validate the frozen holdout template and all output destinations before
    # spending compute on screening.
    incumbent_config = _config_from_params(
        dict(seed_configs[0]), max_iter=max_iter, time_limit=time_limit
    )
    incumbent_params = {
        field.name: getattr(incumbent_config, field.name)
        for field in dataclasses.fields(incumbent_config)
    }
    _build_validation_profile(
        validation_profile_template, validation_seeds, incumbent_params
    )
    if trials_csv is not None:
        trials_csv.parent.mkdir(parents=True, exist_ok=True)
    validation_profile_output.parent.mkdir(parents=True, exist_ok=True)
    n_startup_trials = len(seed_configs)
    _ensure_storage_parent(storage)
    study = optuna.create_study(
        study_name=study_name,
        direction="minimize",
        sampler=optuna.samplers.TPESampler(
            seed=sampler_seed,
            constant_liar=True,
            n_startup_trials=n_startup_trials,
        ),
        storage=storage,
        load_if_exists=True,
    )
    protocol = {
        "name": _SEARCH_PROTOCOL,
        "screen_seeds": list(
            range(_SCREEN_SEED_START, _SCREEN_SEED_START + _SCREEN_SEED_COUNT)
        ),
        "extension_seeds": list(
            range(_EXTENSION_SEED_START, _EXTENSION_SEED_START + _EXTENSION_SEED_COUNT)
        ),
        "seed_config_paths": [
            str(path.resolve()) for path in reference_settings.seed_config_paths
        ],
        "scenarios": list(scenarios),
        "max_evaluations": 15000,
        "time_limit_seconds": time_limit,
    }
    if study.trials:
        if study.user_attrs.get("search_protocol") != protocol:
            raise ValueError(
                "study name already contains trials from a different protocol"
            )
        if any(
            trial.state == optuna.trial.TrialState.RUNNING for trial in study.trials
        ):
            raise RuntimeError(
                "study contains RUNNING trials; recover abandoned trials before resuming"
            )
    else:
        study.set_user_attr("search_protocol", protocol)
        for index, params in enumerate(seed_configs):
            study.enqueue_trial(
                params,
                user_attrs={
                    "campaign_phase": "screen",
                    "warm_start_index": index,
                    "is_incumbent": index == 0,
                },
            )

    def objective(trial: optuna.trial.Trial) -> float:
        phase = trial.user_attrs.get("campaign_phase", "screen")
        trial.set_user_attr("campaign_phase", phase)
        if phase == "extension":
            seed_start = _EXTENSION_SEED_START
            seed_count = _EXTENSION_SEED_COUNT
        else:
            seed_start = _SCREEN_SEED_START
            seed_count = _SCREEN_SEED_COUNT
        return _run_multi_trial(
            trial,
            definitions,
            de_reference,
            n_eval_seeds=seed_count,
            max_iter=max_iter,
            time_limit=time_limit,
            max_iter_min=None,
            eval_seed_start=seed_start,
        )

    def persist_trial(
        current_study: optuna.study.Study, _: optuna.trial.FrozenTrial
    ) -> None:
        if trials_csv is not None:
            trials_csv.parent.mkdir(parents=True, exist_ok=True)
            current_study.trials_dataframe().to_csv(trials_csv, index=False)

    remaining_screen_trials = _remaining_screen_trial_budget(study.trials, n_trials)
    if remaining_screen_trials:
        study.optimize(
            objective,
            n_trials=remaining_screen_trials,
            show_progress_bar=verbose,
            callbacks=[persist_trial],
            catch=(TrialExecutionError,),
        )

    screen_trials = [
        trial
        for trial in study.trials
        if trial.user_attrs.get("campaign_phase") == "screen"
        and trial.state == optuna.trial.TrialState.COMPLETE
    ]
    incumbent = next(
        (trial for trial in screen_trials if trial.user_attrs.get("is_incumbent")),
        None,
    )
    extension_sources: list[int] = []
    if incumbent is not None:
        incumbent_scores = cast(
            dict[str, float], incumbent.user_attrs["scenario_scores"]
        )
        eligible = [
            trial
            for trial in screen_trials
            if trial.number != incumbent.number
            and _passes_non_regression(
                cast(dict[str, float], trial.user_attrs["scenario_scores"]),
                incumbent_scores,
            )
        ]
        eligible.sort(key=lambda trial: cast(float, trial.value))
        extension_sources = [
            incumbent.number,
            *(trial.number for trial in eligible[:2]),
        ]
    study.set_user_attr("extension_source_trials", extension_sources)

    existing_extensions = {
        int(trial.user_attrs["source_trial_number"]): trial
        for trial in study.trials
        if trial.user_attrs.get("campaign_phase") == "extension"
        and trial.user_attrs.get("source_trial_number") is not None
    }
    pending_extensions = []
    for source in extension_sources:
        existing = existing_extensions.get(source)
        if existing is not None and existing.state == optuna.trial.TrialState.COMPLETE:
            continue
        if existing is not None and existing.state == optuna.trial.TrialState.WAITING:
            pending_extensions.append(source)
            continue
        source_trial = study.trials[source]
        study.enqueue_trial(
            source_trial.params,
            user_attrs={
                "campaign_phase": "extension",
                "source_trial_number": source,
            },
        )
        pending_extensions.append(source)
    if pending_extensions:
        study.optimize(
            objective,
            n_trials=len(pending_extensions),
            show_progress_bar=verbose,
            callbacks=[persist_trial],
            catch=(TrialExecutionError,),
        )
    if trials_csv is not None:
        trials_csv.parent.mkdir(parents=True, exist_ok=True)
        study.trials_dataframe().to_csv(trials_csv, index=False)
    complete_screens = {
        trial.number: trial
        for trial in study.trials
        if trial.user_attrs.get("campaign_phase") == "screen"
        and trial.state == optuna.trial.TrialState.COMPLETE
    }
    extension_by_source = {
        int(trial.user_attrs["source_trial_number"]): trial
        for trial in study.trials
        if trial.user_attrs.get("campaign_phase") == "extension"
        and trial.state == optuna.trial.TrialState.COMPLETE
        and trial.user_attrs.get("source_trial_number") is not None
    }
    selected_trial = None
    selected_score = float("inf")
    incumbent_trial = (
        complete_screens.get(extension_sources[0]) if extension_sources else None
    )
    if incumbent_trial is not None:
        incumbent_full_scores = _combined_scenario_scores(
            incumbent_trial,
            extension_by_source.get(incumbent_trial.number),
        )
        for source in extension_sources:
            candidate = complete_screens.get(source)
            extension = extension_by_source.get(source)
            if candidate is None or extension is None:
                continue
            scores = _combined_scenario_scores(candidate, extension)
            if not _passes_non_regression(scores, incumbent_full_scores):
                continue
            score = _robust_score(scores)
            if score < selected_score:
                selected_trial = candidate
                selected_score = score
    if selected_trial is None:
        selected_trial = incumbent_trial
        if selected_trial is not None:
            selected_score = _robust_score(incumbent_full_scores)
    if selected_trial is None:
        best_trial_params = seed_configs[0]
        best_value = None
        best_trial_number = None
        final_scores: dict[str, float] = {}
        selected_config = _config_from_params(
            dict(seed_configs[0]), max_iter=max_iter, time_limit=time_limit
        )
    else:
        best_trial_params = dict(selected_trial.params)
        best_value = selected_score
        best_trial_number = selected_trial.number
        final_scores = _combined_scenario_scores(
            selected_trial,
            extension_by_source.get(selected_trial.number),
        )
        selected_config = _config_from_params(
            best_trial_params, max_iter=max_iter, time_limit=time_limit
        )
    best_params = {
        field.name: getattr(selected_config, field.name)
        for field in dataclasses.fields(selected_config)
    }
    validation_profile = _build_validation_profile(
        validation_profile_template,
        validation_seeds,
        best_params,
    )
    validation_profile_output.parent.mkdir(parents=True, exist_ok=True)
    validation_profile_output.write_text(
        json.dumps(validation_profile, indent=2), encoding="utf-8"
    )
    return {
        "metadata": {
            "scenarios": list(scenarios),
            "n_trials": n_trials,
            "n_completed_trials": sum(
                trial.state == optuna.trial.TrialState.COMPLETE
                for trial in study.trials
            ),
            "n_eval_seeds_per_screening_trial": _SCREEN_SEED_COUNT,
            "screening_seeds": list(
                range(_SCREEN_SEED_START, _SCREEN_SEED_START + _SCREEN_SEED_COUNT)
            ),
            "extension_seeds": list(
                range(
                    _EXTENSION_SEED_START, _EXTENSION_SEED_START + _EXTENSION_SEED_COUNT
                )
            ),
            "validation_seeds": list(validation_seeds),
            "sampler": "TPESampler",
            "sampler_seed": sampler_seed,
            "n_startup_trials": n_startup_trials,
            "max_iter": max_iter,
            "time_limit": time_limit,
            "per_execution_timeout_seconds": time_limit + 30.0,
            "max_evaluations": 15000,
            "score_weights": {
                "balanced_priority_protected": 0.75,
                "mean_two_worst_scenarios": 0.25,
                "priority_scenario_group": 0.5,
                "protected_scenario_group": 0.5,
            },
            "non_regression_margin_normalized": 0.05,
            "best_trial_number": best_trial_number,
            "best_value": best_value,
            "selected_scenario_scores": final_scores,
            "extension_source_trials": extension_sources,
            "validation_profile_output": str(validation_profile_output),
            "de_reference": de_reference,
            "reference": de_reference,
            "reference_algorithms": list(reference_settings.reference_algorithms),
            "reference_winners": reference_winners,
            "reference_runs": [str(path) for path in all_reference_paths],
            "max_iter_min": max_iter_min,
            "param_importances": _param_importances(study, phase="screen"),
            "seed_configs": [
                str(path) for path in reference_settings.seed_config_paths
            ],
            "benchmark_root": str(benchmark_root),
        },
        "best_trial_params": best_trial_params,
        "best_params": best_params,
        "validation_profile": validation_profile,
    }


def _combined_scenario_scores(
    screen_trial: optuna.trial.FrozenTrial,
    extension_trial: optuna.trial.FrozenTrial | None,
) -> dict[str, float]:
    """Average per-run normalized gaps from screening and extension seeds."""
    records = list(screen_trial.user_attrs.get("run_records", []))
    if extension_trial is not None:
        records.extend(extension_trial.user_attrs.get("run_records", []))
    grouped: dict[str, list[float]] = {}
    for record in records:
        if record.get("status") == "complete":
            grouped.setdefault(str(record["scenario"]), []).append(
                float(record["normalized_gap"])
            )
    return {name: float(sum(values) / len(values)) for name, values in grouped.items()}


def _remaining_screen_trial_budget(
    trials: Sequence[optuna.trial.FrozenTrial], target_trials: int
) -> int:
    """Count completed/started screening trials, excluding queued warm starts."""
    attempted = sum(
        trial.user_attrs.get("campaign_phase", "screen") == "screen"
        and trial.state != optuna.trial.TrialState.WAITING
        for trial in trials
    )
    return max(0, target_trials - attempted)


def _build_validation_profile(
    template_path: Path,
    seeds: Sequence[int],
    best_params: Mapping[str, object],
) -> dict[str, object]:
    """Clone the frozen competitor profile and insert the selected GIVP config."""
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or any(
        algorithm not in profiles for algorithm in ("DE", "PSO", "UPSO")
    ):
        raise ValueError("validation profile template must contain DE, PSO, and UPSO")
    givp_profile = {
        key: best_params[key]
        for key in (
            "max_iterations",
            "alpha",
            "vnd_iterations",
            "ils_iterations",
            "perturbation_strength",
            "use_elite_pool",
            "elite_size",
            "path_relink_frequency",
            "path_relink_strategy",
            "adaptive_alpha",
            "alpha_min",
            "alpha_max",
            "num_candidates_per_step",
            "use_cache",
            "cache_size",
            "early_stop_threshold",
            "use_convergence_monitor",
            "n_workers",
        )
    }
    givp_profile.update(
        {
            "source": "Selected from the paired-seed global robust tuning campaign",
            "ablation_variant": "combined",
            "time_limit_seconds": 300.0,
        }
    )
    profiles["GIVP"] = givp_profile
    payload["profile_kind"] = "givp-global-robust-final-validation"
    payload["optimizer_seeds"] = list(seeds)
    payload["max_evaluations"] = 15000
    return payload


def _param_importances(
    study: optuna.study.Study, *, phase: str = "screen"
) -> dict[str, float]:
    """Return fANOVA importances from screening trials only."""
    completed = [
        trial
        for trial in study.trials
        if trial.state == optuna.trial.TrialState.COMPLETE
        and trial.user_attrs.get("campaign_phase") == phase
    ]
    if len(completed) < 2:
        return {}
    try:
        phase_study = optuna.create_study(direction=study.direction)
        phase_study.add_trials(completed)
        importances = optuna.importance.get_param_importances(phase_study)
    except (RuntimeError, ValueError):
        return {}
    return {name: float(value) for name, value in importances.items()}


def _ensure_storage_parent(storage: str | None) -> None:
    """Create the parent directory for a file-backed SQLite Optuna study."""
    if storage is None or not storage.startswith("sqlite:///"):
        return
    database_path = storage.removeprefix("sqlite:///").split("?", maxsplit=1)[0]
    path = Path(database_path)
    if path.name and path.name != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--scenarios", nargs="+", required=True)
    parser.add_argument("--n-trials", type=int, default=16)
    parser.add_argument("--n-eval-seeds", type=int, default=3)
    parser.add_argument(
        "--eval-seed-start",
        type=int,
        default=_SCREEN_SEED_START,
        help="Fixed screening start seed (1); extension uses seeds 4 through 7.",
    )
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--sampler-seed", type=int, default=42)
    parser.add_argument("--study-name", required=True)
    parser.add_argument("--storage")
    parser.add_argument("--de-reference", type=Path)
    parser.add_argument(
        "--reference-runs",
        type=Path,
        nargs="+",
        default=[],
        help="campaign runs.csv files holding the competitor reference rows",
    )
    parser.add_argument(
        "--reference-algorithms",
        nargs="+",
        default=["DE", "PSO", "UPSO"],
        help="score against the best mean objective among these algorithms",
    )
    parser.add_argument("--trials-csv", type=Path)
    parser.add_argument(
        "--seed-config",
        type=Path,
        action="append",
        required=True,
        help="Four paths in order: incumbent, then three historical warm starts.",
    )
    parser.add_argument("--validation-profile-template", type=Path, required=True)
    parser.add_argument("--validation-profile-output", type=Path, required=True)
    parser.add_argument(
        "--validation-seeds",
        type=int,
        nargs=10,
        default=list(_FINAL_VALIDATION_SEEDS),
        help="Fixed holdout seed list; must be 49 through 58.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for multi-scenario hydropower tuning."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    payload = run_tuning(
        args.benchmark_root,
        scenarios=args.scenarios,
        n_trials=args.n_trials,
        n_eval_seeds=args.n_eval_seeds,
        sampler_seed=args.sampler_seed,
        max_iter=args.max_iter,
        time_limit=args.time_limit,
        study_name=args.study_name,
        storage=args.storage,
        reference_settings=_ReferenceSettings(
            de_reference_path=args.de_reference,
            seed_config_paths=args.seed_config,
            reference_paths=args.reference_runs,
            reference_algorithms=args.reference_algorithms,
        ),
        verbose=args.verbose,
        max_iter_min=None,
        trials_csv=args.trials_csv,
        eval_seed_start=args.eval_seed_start,
        validation_profile_template=args.validation_profile_template,
        validation_profile_output=args.validation_profile_output,
        validation_seeds=args.validation_seeds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    metadata = cast(Mapping[str, object], payload["metadata"])
    _log.info("Best configuration written to %s", args.output)
    _log.info("Validation profile written to %s", args.validation_profile_output)
    best_value = metadata["best_value"]
    if best_value is not None:
        _log.info("Best global score: %.6f", cast(float, best_value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
