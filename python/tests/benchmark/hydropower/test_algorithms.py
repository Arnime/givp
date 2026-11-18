# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Tests for the SOG-reproduction DE, PSO and UPSO adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from benchmarks.comparison.hydropower import budget as budget_module
from benchmarks.comparison.hydropower import de as de_module
from benchmarks.comparison.hydropower import pso as pso_module
from benchmarks.comparison.hydropower import upso as upso_module
from benchmarks.comparison.hydropower.budget import (
    CountingObjective,
    EvaluationBudgetExhaustedError,
    TimeLimitExceededError,
    seeded_global_numpy,
)
from benchmarks.comparison.hydropower.campaign import (
    _load_benchmark,
    _load_profile,
    _optimization_definition,
    _profiles,
)
from benchmarks.comparison.hydropower.de import run_de
from benchmarks.comparison.hydropower.execution import run_optimizer
from benchmarks.comparison.hydropower.pso import run_pso
from benchmarks.comparison.hydropower.upso import run_upso
from givp.examples.synthetic_hydropower.optimization import (
    OptimizationDefinition,
    project_power_vector,
)
from givp.examples.synthetic_hydropower.paths import project_root

_DE_PROFILE: dict[str, object] = {
    "strategy": "best1bin",
    "max_iterations": 1,
    "population_multiplier": 1,
    "tolerance": 0.09,
    "mutation": [0.5, 1.0],
    "recombination": 0.9,
    "initialization": "latinhypercube",
    "updating": "deferred",
    "polish": False,
    "execution_workers": 1,
}
_PSO_PROFILE: dict[str, object] = {
    "population_size": 4,
    "max_generations": 2,
    "inertia": 0.5,
    "c1": 1.0,
    "c2": 1.0,
}
_UPSO_PROFILE: dict[str, object] = {
    "engine": "pyswarm 0.6 unified pso",
    "population_size": 4,
    "max_generations": 2,
    "neighborhood_size": 3,
    "unification_factor": 0.3,
    "w_min": 0.6,
    "w_max": 0.9,
    "c1": 0.6,
    "c2": 0.4,
}


@pytest.fixture(scope="module")
def definition() -> OptimizationDefinition:
    benchmark = _load_benchmark(project_root() / "benchmarks" / "v1.0.0")
    return _optimization_definition(benchmark.cascade, benchmark.scenarios[2], {})


def _sphere(vector: NDArray[np.float64]) -> float:
    return float(np.sum((vector - 1.0) ** 2))


_BOUNDS = [(-5.0, 5.0)] * 4


# --- CountingObjective -------------------------------------------------------


def test_counting_objective_enforces_exact_cap_and_keeps_best() -> None:
    counted = CountingObjective(_sphere, max_evaluations=2)
    counted(np.full(4, 3.0))
    counted(np.full(4, 1.0))

    with pytest.raises(EvaluationBudgetExhaustedError):
        counted(np.zeros(4))
    vector, value = counted.best()
    assert counted.evaluations == 2
    assert value == 0.0
    np.testing.assert_array_equal(vector, np.ones(4))


def test_counting_objective_without_cap_and_without_calls() -> None:
    counted = CountingObjective(_sphere, max_evaluations=None)
    with pytest.raises(RuntimeError, match="no physical evaluation"):
        counted.best()
    with pytest.raises(ValueError, match="positive"):
        CountingObjective(_sphere, max_evaluations=0)


def test_counting_objective_stops_after_an_in_progress_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    monkeypatch.setattr(budget_module, "perf_counter", lambda: now[0])

    def objective(vector: NDArray[np.float64]) -> float:
        return _sphere(vector)

    counted = CountingObjective(objective, max_evaluations=None, time_limit_seconds=5.0)
    now[0] = 5.0
    with pytest.raises(TimeLimitExceededError):
        counted(np.zeros(4))

    vector, value = counted.best()
    assert counted.evaluations == 1
    assert value == _sphere(np.zeros(4))
    np.testing.assert_array_equal(vector, np.zeros(4))


@pytest.mark.parametrize("algorithm", ["DE", "PSO", "UPSO"])
def test_adapters_return_best_point_when_time_limit_expires(
    monkeypatch: pytest.MonkeyPatch, algorithm: str
) -> None:
    now = [0.0]
    monkeypatch.setattr(budget_module, "perf_counter", lambda: now[0])

    def slow_objective(vector: NDArray[np.float64]) -> float:
        now[0] = 5.0
        return _sphere(vector)

    if algorithm == "DE":

        def fake_de(objective: Callable[..., float], bounds: Any, **kwargs: Any) -> Any:
            return objective(np.zeros(len(bounds)))

        monkeypatch.setattr(de_module, "differential_evolution", fake_de)
        profile = {**_DE_PROFILE, "time_limit_seconds": 5.0}
        result = run_de(slow_objective, _BOUNDS, profile, seed=44)
    elif algorithm == "PSO":

        def fake_pso(
            objective: Callable[..., float], lower: Any, upper: Any, **kwargs: Any
        ) -> Any:
            return objective(np.zeros(len(lower)))

        monkeypatch.setattr(pso_module, "pso", fake_pso)
        profile = {**_PSO_PROFILE, "time_limit_seconds": 5.0}
        result = run_pso(slow_objective, _BOUNDS, profile, seed=44)
    else:
        profile = {**_UPSO_PROFILE, "time_limit_seconds": 5.0}
        result = run_upso(slow_objective, _BOUNDS, profile, seed=44)

    assert result.termination == "time_limit"
    assert result.evaluations == 1
    expected_objective = (
        _sphere(result.vector) if algorithm == "UPSO" else _sphere(np.zeros(4))
    )
    assert result.best_objective == expected_objective


def test_global_seed_is_applied_and_restored() -> None:
    np.random.seed(123)
    expected_next = np.random.random()
    np.random.seed(123)
    with seeded_global_numpy(7):
        inside = np.random.random()
    after = np.random.random()

    np.random.seed(7)
    assert inside == np.random.random()
    assert after == expected_next


# --- Library calls match the SOG wrappers -----------------------------------


def test_de_calls_scipy_with_the_sog_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake(func: Callable[..., float], bounds: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        func(np.zeros(len(bounds)))
        kwargs["callback"](None)
        return type(
            "R",
            (),
            {
                "x": np.zeros(len(bounds)),
                "fun": 1.0,
                "nit": 1,
                "message": "Maximum number of iterations has been exceeded.",
            },
        )()

    monkeypatch.setattr(de_module, "differential_evolution", fake)
    profile = {**_DE_PROFILE, "population_multiplier": 20, "max_iterations": 100}
    result = run_de(_sphere, _BOUNDS, profile, seed=44)

    assert {key: captured[key] for key in captured if key != "callback"} == {
        "strategy": "best1bin",
        "maxiter": 100,
        "popsize": 20,
        "tol": 0.09,
        "mutation": (0.5, 1.0),
        "recombination": 0.9,
        "init": "latinhypercube",
        "updating": "deferred",
        "polish": False,
        "workers": 1,
    }
    assert "seed" not in captured
    assert "rng" not in captured
    assert result.termination == "max_iterations"
    assert result.evaluations == 1


def test_de_rejects_parallel_workers() -> None:
    with pytest.raises(ValueError, match="execution_workers"):
        run_de(_sphere, _BOUNDS, {**_DE_PROFILE, "execution_workers": -1}, 1)


def test_pso_calls_pyswarm_with_profile_coefficients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake(func: Callable[..., float], lb: Any, ub: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        func(np.zeros(len(lb)))
        print("Stopping search: maximum iterations reached --> 2")
        return np.zeros(len(lb)), 1.0

    monkeypatch.setattr(pso_module, "pso", fake)
    result = run_pso(_sphere, _BOUNDS, _PSO_PROFILE, 44)

    assert captured == {
        "swarmsize": 4,
        "omega": 0.5,
        "phip": 1.0,
        "phig": 1.0,
        "maxiter": 2,
    }
    assert result.termination == "max_iterations"


def test_upso_blends_global_and_ring_local_velocities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[NDArray[np.float64]] = []
    initial_positions = np.array([[0.0], [0.2], [0.5], [0.9]])

    def fake_rand(*shape: int) -> NDArray[np.float64]:
        if shape == (4, 1):
            return initial_positions.copy()
        return np.full(shape, 0.5, dtype=np.float64)

    random_values = iter(
        [
            np.full((4, 1), 0.5),
            np.full((4, 1), 0.5),
            np.full((4, 1), 0.25),
        ]
    )

    def fake_uniform(*, size: tuple[int, ...]) -> NDArray[np.float64]:
        return next(random_values)

    def objective(vector: NDArray[np.float64]) -> float:
        calls.append(vector.copy())
        return float((vector[0] - 5.0) ** 2)

    monkeypatch.setattr(upso_module.np.random, "rand", fake_rand)
    monkeypatch.setattr(upso_module.np.random, "uniform", fake_uniform)
    profile = {
        **_UPSO_PROFILE,
        "population_size": 4,
        "max_generations": 1,
        "w_min": 0.6,
        "w_max": 0.9,
    }

    run_upso(objective, [(0.0, 10.0)], profile, seed=44)

    assert len(calls) == 8
    assert calls[4][0] == pytest.approx(0.44)


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("Stopping search: maximum iterations reached --> 250", "max_iterations"),
        (
            "Stopping search: Swarm best objective change less than 1e-08",
            "converged_minfunc",
        ),
        (
            "Stopping search: Swarm best position change less than 1e-08",
            "converged_minstep",
        ),
        ("", "pyswarm_returned"),
    ],
)
def test_pyswarm_stop_reason_is_recorded(output: str, expected: str) -> None:
    assert pso_module._termination(output) == expected


# --- Real engines: reproducibility, diversity, bounds and budget ------------


@pytest.mark.parametrize(
    ("runner", "profile"),
    [
        (run_de, _DE_PROFILE),
        (run_pso, _PSO_PROFILE),
        (run_upso, _UPSO_PROFILE),
    ],
)
def test_same_seed_reproduces_and_other_seeds_diverge(
    runner: Callable[..., Any], profile: dict[str, object]
) -> None:
    first = runner(_sphere, _BOUNDS, profile, 44)
    again = runner(_sphere, _BOUNDS, profile, 44)
    other = runner(_sphere, _BOUNDS, profile, 45)

    np.testing.assert_array_equal(first.vector, again.vector)
    assert first.best_objective == again.best_objective
    assert first.evaluations == again.evaluations
    assert not np.array_equal(first.vector, other.vector)


@pytest.mark.parametrize(
    ("runner", "profile"),
    [
        (run_de, _DE_PROFILE),
        (run_pso, _PSO_PROFILE),
        (run_upso, _UPSO_PROFILE),
    ],
)
def test_vectors_stay_within_bounds(
    runner: Callable[..., Any], profile: dict[str, object]
) -> None:
    result = runner(_sphere, _BOUNDS, profile, 44)

    assert np.all(result.vector >= -5.0)
    assert np.all(result.vector <= 5.0)


@pytest.mark.parametrize(
    ("runner", "profile", "budget"),
    [
        (run_de, _DE_PROFILE, 7),
        (run_pso, _PSO_PROFILE, 7),
        (run_upso, _UPSO_PROFILE, 5),
    ],
)
def test_budget_is_exact_and_reported(
    runner: Callable[..., Any], profile: dict[str, object], budget: int
) -> None:
    result = runner(_sphere, _BOUNDS, {**profile, "max_evaluations": budget}, 44)

    assert result.evaluations == budget
    assert result.termination == "evaluation_limit"
    assert np.isfinite(result.best_objective)


def test_uncapped_pso_counts_iterations_and_stops_for_a_reason() -> None:
    result = run_pso(_sphere, _BOUNDS, _PSO_PROFILE, 44)

    assert result.evaluations <= 4 * 3
    assert 0 <= result.iterations <= 2
    assert result.termination in {
        "max_iterations",
        "converged_minfunc",
        "converged_minstep",
    }


def test_de_without_cap_reports_scipy_termination() -> None:
    result = run_de(_sphere, _BOUNDS, _DE_PROFILE, 44)

    assert result.termination in {"max_iterations", "converged_tolerance"}
    assert result.iterations >= 1


# --- Physical objective -----------------------------------------------------


@pytest.mark.parametrize("algorithm", ["DE", "PSO", "UPSO"])
def test_physical_runs_return_projected_vectors_and_exact_budget(
    definition: OptimizationDefinition, algorithm: str
) -> None:
    # Native limits exceed the cap, so the budget is what stops each run.
    if algorithm == "DE":
        profile = _DE_PROFILE
    elif algorithm == "UPSO":
        profile = {**_UPSO_PROFILE, "max_generations": 50}
    else:
        profile = {**_PSO_PROFILE, "max_generations": 50}
    outcome = run_optimizer(
        algorithm, definition, {**profile, "max_evaluations": 30}, seed=44
    )

    assert outcome.evaluations == 30
    assert outcome.termination == "evaluation_limit"
    assert outcome.vector.shape == (48,)
    assert np.allclose(
        outcome.vector, project_power_vector(outcome.vector, definition).reshape(-1)
    )
    upper = np.repeat(definition.maximum_power_mw, definition.periods)
    assert np.all(outcome.vector >= 0.0)
    assert np.all(outcome.vector <= upper)
    # The physical evaluator projects internally, so the optimizer's best equals
    # the re-evaluated objective of the returned vector.
    assert outcome.objective == pytest.approx(outcome.optimizer_best_objective)


def test_published_profiles_build_valid_runs(
    definition: OptimizationDefinition,
) -> None:
    """Every algorithm block of both v2 profiles is accepted by its adapter."""
    for name in (
        "sog_reproduction.json",
        "budget_matched.json",
        "budget_matched_300s_true_upso.json",
    ):
        profiles = _profiles(
            _load_profile(Path(project_root()) / "interop" / "v1" / name)
        )
        for algorithm in ("DE", "PSO", "UPSO"):
            tiny = {**profiles[algorithm], "max_evaluations": 3}
            outcome = run_optimizer(algorithm, definition, tiny, seed=44)
            assert outcome.evaluations == 3
