# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Optuna trial objectives for single- and multi-scenario studies."""

from __future__ import annotations

import multiprocessing
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any

import numpy as np
import optuna

from benchmarks.tuning.hydropower.config import _suggest_config, _suggest_global_config
from givp import GIVPConfig, givp
from givp.examples.synthetic_hydropower.optimization import (
    OptimizationDefinition,
    evaluate_power_vector,
    project_power_vector,
)

PRIORITY_SCENARIOS = frozenset({"downstream_dominant", "dry_variable", "wet_rising"})
PROTECTED_SCENARIOS = frozenset({"dry_stable", "typical", "upstream_peak", "flood"})
_GLOBAL_WEIGHT = 0.75
_TAIL_WEIGHT = 0.25
_NON_REGRESSION_MARGIN = 0.05


class TrialExecutionError(RuntimeError):
    """Raised when an isolated optimizer execution fails or times out."""


def _optimizer_worker(
    send_connection: Any,
    definition: OptimizationDefinition,
    config: GIVPConfig,
    seed: int,
) -> None:
    """Run one optimizer call in a child process and return primitive results."""
    started = perf_counter()
    try:
        result = givp(
            lambda values: _objective_value(values, definition),
            definition.bounds,
            config=config,
            repair=lambda values: project_power_vector(values, definition).reshape(-1),
            seed=seed,
        )
        send_connection.send(
            {
                "status": "ok",
                "objective": float(result.fun),
                "evaluations": int(result.nfev),
                "iterations": int(result.nit),
                "elapsed_seconds": perf_counter() - started,
                "termination": str(
                    getattr(
                        result.meta.get(
                            "termination_reason", result.message or "unknown"
                        ),
                        "value",
                        result.meta.get(
                            "termination_reason", result.message or "unknown"
                        ),
                    )
                ),
            }
        )
    except BaseException as error:  # The exception must cross the process boundary.
        send_connection.send(
            {
                "status": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "elapsed_seconds": perf_counter() - started,
            }
        )
    finally:
        send_connection.close()


def _run_isolated(
    definition: OptimizationDefinition,
    config: GIVPConfig,
    seed: int,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    """Run a single optimizer call in a killable process with a hard timeout."""
    return _run_process(
        _optimizer_worker,
        (definition, config, seed),
        timeout_seconds=timeout_seconds,
    )


def _run_process(
    target: Any,
    args: tuple[object, ...],
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    """Execute a pipe-based worker in a spawned process with a hard deadline."""
    context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=target,
        args=(send_connection, *args),
    )
    started = perf_counter()
    try:
        process.start()
        send_connection.close()
        if not receive_connection.poll(timeout_seconds):
            process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():
                process.kill()
                process.join()
            raise TrialExecutionError(
                f"run timed out after {perf_counter() - started:.3f} seconds"
            )
        try:
            payload = receive_connection.recv()
        except EOFError as error:
            raise TrialExecutionError(
                f"optimizer worker exited without a result (exit code {process.exitcode})"
            ) from error
        if not isinstance(payload, dict):
            raise TrialExecutionError("optimizer worker returned an invalid payload")
        process.join(timeout=5.0)
        if process.is_alive():
            process.terminate()
            process.join()
        if payload.get("status") != "ok":
            raise TrialExecutionError(
                f"optimizer worker failed: {payload.get('error_type')}: "
                f"{payload.get('error_message')}"
            )
        return payload
    except TrialExecutionError:
        raise
    except Exception as error:
        raise TrialExecutionError(
            f"could not execute optimizer worker: {error}"
        ) from error
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():
                process.kill()
                process.join()
        if process.pid is not None:
            process.close()
        send_connection.close()
        receive_connection.close()


def _objective_value(values: np.ndarray, definition: OptimizationDefinition) -> float:
    """Compute the hydropower objective for a candidate optimization vector."""
    return float(evaluate_power_vector(values, definition)[0])


def _run_single_trial(
    trial: optuna.trial.Trial,
    definition: OptimizationDefinition,
    *,
    n_eval_seeds: int,
    max_iter: int,
    time_limit: float,
) -> float:
    """Average one scenario's objective across the configured seeds."""
    config = _suggest_config(trial, max_iter=max_iter, time_limit=time_limit)
    scores: list[float] = []
    for seed in range(n_eval_seeds):
        result = givp(
            lambda values: _objective_value(values, definition),
            definition.bounds,
            config=config,
            repair=lambda values: project_power_vector(values, definition).reshape(-1),
            seed=seed,
        )
        scores.append(float(result.fun))
    return float(np.mean(scores))


def _scenario_score(value: float, reference: float) -> float:
    """Return the signed objective gap relative to a scaled reference."""
    return (value - reference) / max(abs(reference), 1.0)


def _robust_score(scenario_scores: Mapping[str, float]) -> float:
    """Combine balanced scenario regret with the mean of the two worst cases."""
    missing = (PRIORITY_SCENARIOS | PROTECTED_SCENARIOS) - scenario_scores.keys()
    if missing:
        raise ValueError(f"missing scenario scores: {', '.join(sorted(missing))}")
    priority_mean = float(
        np.mean([scenario_scores[name] for name in PRIORITY_SCENARIOS])
    )
    protected_mean = float(
        np.mean([scenario_scores[name] for name in PROTECTED_SCENARIOS])
    )
    weighted_mean = 0.5 * (priority_mean + protected_mean)
    tail_mean = float(np.mean(sorted(scenario_scores.values(), reverse=True)[:2]))
    return _GLOBAL_WEIGHT * weighted_mean + _TAIL_WEIGHT * tail_mean


def _passes_non_regression(
    candidate_scores: Mapping[str, float],
    incumbent_scores: Mapping[str, float],
    *,
    margin: float = _NON_REGRESSION_MARGIN,
) -> bool:
    """Return whether protected-scenario regret stays within the fixed margin."""
    return all(
        candidate_scores[name] - incumbent_scores[name] <= margin
        for name in PROTECTED_SCENARIOS
    )


def _run_multi_trial(
    trial: optuna.trial.Trial,
    definitions: Sequence[OptimizationDefinition],
    references: Mapping[str, float],
    *,
    n_eval_seeds: int,
    max_iter: int,
    time_limit: float,
    max_iter_min: int | None = None,
    eval_seed_start: int = 0,
    timeout_grace_seconds: float = 30.0,
) -> float:
    """Evaluate one shared configuration across the selected scenarios."""
    del max_iter_min, max_iter
    config = _suggest_global_config(trial, time_limit=time_limit)
    evaluation_seeds = range(eval_seed_start, eval_seed_start + n_eval_seeds)
    trial.set_user_attr("evaluation_seeds", list(evaluation_seeds))
    scenario_scores: list[float] = []
    records: list[dict[str, object]] = []
    timeout_seconds = time_limit + timeout_grace_seconds
    for definition in definitions:
        seed_scores: list[float] = []
        seed_objectives: list[float] = []
        seed_evaluations: list[int] = []
        for seed in evaluation_seeds:
            started = perf_counter()
            try:
                result = _run_isolated(
                    definition,
                    config,
                    seed,
                    timeout_seconds=timeout_seconds,
                )
            except TrialExecutionError as error:
                records.append(
                    {
                        "scenario": definition.scenario,
                        "optimizer_seed": seed,
                        "status": "failed",
                        "objective": None,
                        "evaluations": None,
                        "iterations": None,
                        "elapsed_seconds": perf_counter() - started,
                        "termination": str(error),
                    }
                )
                trial.set_user_attr("run_records", records)
                raise
            raw_objective = result["objective"]
            raw_evaluations = result["evaluations"]
            raw_iterations = result["iterations"]
            raw_elapsed = result["elapsed_seconds"]
            if (
                isinstance(raw_objective, bool)
                or not isinstance(raw_objective, (int, float))
                or isinstance(raw_evaluations, bool)
                or not isinstance(raw_evaluations, int)
                or isinstance(raw_iterations, bool)
                or not isinstance(raw_iterations, int)
                or isinstance(raw_elapsed, bool)
                or not isinstance(raw_elapsed, (int, float))
            ):
                raise TrialExecutionError("optimizer worker returned invalid metrics")
            objective_value = float(raw_objective)
            evaluations = raw_evaluations
            iterations = raw_iterations
            elapsed_seconds = float(raw_elapsed)
            scenario_gap = _scenario_score(
                objective_value, references.get(definition.scenario, 0.0)
            )
            seed_objectives.append(objective_value)
            seed_evaluations.append(evaluations)
            seed_scores.append(scenario_gap)
            records.append(
                {
                    "scenario": definition.scenario,
                    "optimizer_seed": seed,
                    "status": "complete",
                    "objective": objective_value,
                    "normalized_gap": scenario_gap,
                    "evaluations": evaluations,
                    "iterations": iterations,
                    "elapsed_seconds": elapsed_seconds,
                    "termination": str(result["termination"]),
                }
            )
            trial.set_user_attr("run_records", records)
        scenario_scores.append(float(np.mean(seed_scores)))
        trial.set_user_attr(
            f"{definition.scenario}_objective_mean", float(np.mean(seed_objectives))
        )
        trial.set_user_attr(
            f"{definition.scenario}_evaluations_mean",
            float(np.mean(seed_evaluations)),
        )
        trial.set_user_attr(f"{definition.scenario}_score", scenario_scores[-1])
    scenario_score_map = dict(
        zip((item.scenario for item in definitions), scenario_scores, strict=True)
    )
    trial.set_user_attr("scenario_scores", scenario_score_map)
    return _robust_score(scenario_score_map)
