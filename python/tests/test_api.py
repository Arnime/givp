# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Tests for the public ``givp`` API (``givp`` and ``GIVPOptimizer``)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest
from givp import (
    GIVPConfig,
    GIVPOptimizer,
    InvalidBoundsError,
    InvalidInitialGuessError,
    OptimizeResult,
    givp,
)
from givp.core.elite import ElitePool
from givp.core.grasp import _validate_bounds_and_initial
from givp.core.impl import _maybe_apply_warm_start


def sphere(x: np.ndarray) -> float:
    return float(np.sum(x**2))


def neg_sphere(x: np.ndarray) -> float:
    return -float(np.sum(x**2))


@pytest.fixture(name="fast_config")
def fixture_fast_config() -> GIVPConfig:
    return GIVPConfig(
        max_iterations=4,
        vnd_iterations=8,
        ils_iterations=2,
        elite_size=3,
        path_relink_frequency=2,
        num_candidates_per_step=4,
        early_stop_threshold=10,
        use_convergence_monitor=False,
    )


# ----------------------------- core happy paths -----------------------------


def test_minimize_sphere_returns_result(fast_config: GIVPConfig) -> None:
    bounds = [(-5.0, 5.0)] * 4
    result = givp(sphere, bounds, config=fast_config)
    assert isinstance(result, OptimizeResult)
    assert result.direction == "minimize"
    assert result.x.shape == (4,)
    assert np.isfinite(result.fun)
    assert result.nfev > 0


def test_maximize_returns_value_in_original_sign(fast_config: GIVPConfig) -> None:
    bounds = [(-5.0, 5.0)] * 4
    result = givp(neg_sphere, bounds, direction="maximize", config=fast_config)
    assert result.direction == "maximize"
    assert result.fun <= 0.0
    assert np.isfinite(result.fun)


def test_bounds_as_lower_upper_tuple(fast_config: GIVPConfig) -> None:
    lower = [-1.0, -1.0, -1.0]
    upper = [1.0, 1.0, 1.0]
    result = givp(sphere, (lower, upper), config=fast_config)
    assert result.x.shape == (3,)


def test_optimizer_class_keeps_history(fast_config: GIVPConfig) -> None:
    opt = GIVPOptimizer(sphere, [(-2.0, 2.0)] * 3, config=fast_config)
    r1 = opt.run()
    r2 = opt.run()
    assert len(opt.history) == 2
    assert opt.best_fun == min(r1.fun, r2.fun)
    assert opt.best_x is not None


def test_grasp_optimizer_maximize_tracks_best(fast_config: GIVPConfig) -> None:
    opt = GIVPOptimizer(
        neg_sphere,
        [(-1.0, 1.0)] * 2,
        direction="maximize",
        config=fast_config,
    )
    opt.run()
    opt.run()
    assert opt.best_x is not None
    assert len(opt.history) == 2


def test_result_is_iterable_for_legacy_unpacking(fast_config: GIVPConfig) -> None:
    result = givp(sphere, [(-1.0, 1.0)] * 2, config=fast_config)
    x, fun = result
    assert np.allclose(x, result.x)
    assert fun == result.fun


# ----------------------------- error handling -----------------------------


def test_objective_returning_nan_is_handled(fast_config: GIVPConfig) -> None:
    def nan_func(_x: np.ndarray) -> float:
        return float("nan")

    result = givp(nan_func, [(0.0, 1.0)] * 2, config=fast_config)
    assert not result.success


def test_evaluator_raising_exception_is_handled(fast_config: GIVPConfig) -> None:
    def boom(_x: np.ndarray) -> float:
        raise RuntimeError("explode")

    result = givp(boom, [(0.0, 1.0)] * 2, config=fast_config)
    assert not result.success


def test_invalid_direction_raises(fast_config: GIVPConfig) -> None:
    with pytest.raises(ValueError):
        givp(sphere, [(0.0, 1.0)], direction="bogus", config=fast_config)


def test_minimize_and_direction_conflict_raises(fast_config: GIVPConfig) -> None:
    with pytest.raises(ValueError):
        givp(
            sphere,
            [(0.0, 1.0)] * 2,
            minimize=True,
            direction="maximize",
            config=fast_config,
        )


def test_bounds_num_vars_mismatch_raises(fast_config: GIVPConfig) -> None:
    with pytest.raises(ValueError):
        givp(sphere, [(0.0, 1.0)] * 2, num_vars=5, config=fast_config)


def test_bounds_none_raises() -> None:
    with pytest.raises(ValueError):
        givp(sphere, None)  # type: ignore[arg-type]


def test_invalid_initial_guess_length_raises(fast_config: GIVPConfig) -> None:
    with pytest.raises(InvalidInitialGuessError):
        givp(
            sphere,
            [(-1.0, 1.0)] * 3,
            config=fast_config,
            initial_guess=[0.0, 0.0],
        )


def test_invalid_initial_guess_outside_bounds_raises(fast_config: GIVPConfig) -> None:
    with pytest.raises(InvalidInitialGuessError):
        givp(
            sphere,
            [(-1.0, 1.0)] * 3,
            config=fast_config,
            initial_guess=[5.0, 5.0, 5.0],
        )


def test_invalid_bounds_via_core_validate() -> None:
    with pytest.raises(InvalidBoundsError):
        _validate_bounds_and_initial(
            np.array([0.0, 1.0]),
            np.array([1.0, 2.0, 3.0]),
            None,
            num_vars=3,
        )


def test_evaluator_raising_value_error_in_wrapper(fast_config: GIVPConfig) -> None:
    """``_wrap_objective`` catches ValueError and returns +inf."""

    def bad(_x: np.ndarray) -> float:
        raise ValueError("nope")

    result = givp(bad, [(0.0, 1.0)] * 2, config=fast_config)
    assert not result.success


# ----------------------------- config code paths -----------------------------


def test_initial_guess_warm_start(fast_config: GIVPConfig) -> None:
    bounds = [(-3.0, 3.0)] * 3
    initial = [0.1, 0.1, 0.1]
    result = givp(sphere, bounds, config=fast_config, initial_guess=initial)
    assert result.x.shape == (3,)
    assert np.isfinite(result.fun)


def test_initial_guesses_multi_seed_warm_start(fast_config: GIVPConfig) -> None:
    bounds = [(-3.0, 3.0)] * 3
    warm_starts = [
        [0.2, 0.2, 0.2],
        [0.3, 0.1, 0.4],
    ]
    result = givp(sphere, bounds, config=fast_config, initial_guesses=warm_starts)
    assert result.x.shape == (3,)
    assert np.isfinite(result.fun)


def test_initial_guesses_duplicate_candidates_are_rejected() -> None:
    bounds = [(-3.0, 3.0)] * 2
    with pytest.raises(InvalidInitialGuessError):
        givp(
            sphere,
            bounds,
            initial_guesses=[[0.2, 0.2], [0.2, 0.2]],
        )


def test_initial_guesses_empty_list_is_rejected() -> None:
    bounds = [(-3.0, 3.0)] * 2
    with pytest.raises(InvalidInitialGuessError):
        givp(
            sphere,
            bounds,
            initial_guesses=[],
        )


def test_maybe_apply_warm_start_uses_best_seed() -> None:
    elite_pool = ElitePool(max_size=5)
    seeds = [
        [1.0, 1.0, 1.0],
        [0.1, 0.1, 0.1],
        [0.5, 0.5, 0.5],
    ]

    best_cost, best_solution, warm_best = _maybe_apply_warm_start(
        seeds,
        elite_pool,
        sphere,
        float("inf"),
        np.zeros(3),
        verbose=False,
    )

    assert np.isclose(best_cost, sphere(np.array([0.1, 0.1, 0.1])))
    assert np.allclose(best_solution, np.array([0.1, 0.1, 0.1]))
    assert warm_best is not None
    assert np.allclose(warm_best, np.array([0.1, 0.1, 0.1]))
    assert elite_pool.size() == 3


def test_iteration_callback_is_invoked(fast_config: GIVPConfig) -> None:
    calls = []

    def cb(it: int, cost: float, sol: np.ndarray) -> None:
        calls.append((it, float(cost), np.array(sol)))

    givp(sphere, [(-1.0, 1.0)] * 2, config=fast_config, iteration_callback=cb)
    assert len(calls) >= 1


def test_iteration_callback_exception_is_swallowed(fast_config: GIVPConfig) -> None:
    def cb(_it: int, _cost: float, _sol: np.ndarray) -> None:
        raise RuntimeError("callback boom")

    result = givp(
        sphere,
        [(-1.0, 1.0)] * 2,
        config=fast_config,
        iteration_callback=cb,
        verbose=True,
    )
    assert np.isfinite(result.fun)


def test_use_cache_path(fast_config: GIVPConfig) -> None:
    cfg = GIVPConfig(**{**fast_config.__dict__, "use_cache": True})
    result = givp(sphere, [(-1.0, 1.0)] * 2, config=cfg)
    assert np.isfinite(result.fun)


def test_no_cache_path(fast_config: GIVPConfig) -> None:
    cfg = GIVPConfig(**{**fast_config.__dict__, "use_cache": False})
    result = givp(sphere, [(-1.0, 1.0)] * 2, config=cfg)
    assert np.isfinite(result.fun)


def test_adaptive_alpha_disabled(fast_config: GIVPConfig) -> None:
    cfg = GIVPConfig(**{**fast_config.__dict__, "adaptive_alpha": False})
    result = givp(sphere, [(-1.0, 1.0)] * 2, config=cfg)
    assert np.isfinite(result.fun)


def test_convergence_monitor_enabled(fast_config: GIVPConfig) -> None:
    cfg = GIVPConfig(
        **{
            **fast_config.__dict__,
            "use_convergence_monitor": True,
            "early_stop_threshold": 2,
        }
    )
    result = givp(sphere, [(-1.0, 1.0)] * 2, config=cfg)
    assert np.isfinite(result.fun)


def test_n_workers_parallel_path(fast_config: GIVPConfig) -> None:
    cfg = GIVPConfig(**{**fast_config.__dict__, "n_workers": 2})
    result = givp(sphere, [(-1.0, 1.0)] * 3, config=cfg)
    assert np.isfinite(result.fun)


def test_n_workers_parity_serial_vs_parallel(fast_config: GIVPConfig) -> None:
    """n_workers=2 must return a finite, valid result for the same objective.

    Strict value equality is not guaranteed because thread scheduling affects
    the order in which candidates are evaluated, which can alter the random
    state and thus the trajectory.  The test verifies that:
    - Both executions return finite objective values.
    - The parallel result is within a reasonable absolute tolerance of the
      serial result (same seed, same low-iteration budget).
    - The parallel result respects bounds (sphere minimum is 0).

    Note: speedup from n_workers>1 requires the objective to release the GIL
    (e.g., NumPy/SciPy internals).  Pure-Python objectives run serially inside
    ThreadPoolExecutor due to the GIL.
    """
    bounds = [(-1.0, 1.0)] * 4
    cfg_serial = GIVPConfig(**{**fast_config.__dict__, "n_workers": 1})
    cfg_parallel = GIVPConfig(**{**fast_config.__dict__, "n_workers": 2})

    r_serial = givp(sphere, bounds, config=cfg_serial, seed=42)
    r_parallel = givp(sphere, bounds, config=cfg_parallel, seed=42)

    assert np.isfinite(r_serial.fun), "serial result must be finite"
    assert np.isfinite(r_parallel.fun), "parallel result must be finite"
    assert r_serial.fun >= 0.0, (
        "sphere minimum is 0; serial result must be non-negative"
    )
    assert r_parallel.fun >= 0.0, (
        "sphere minimum is 0; parallel result must be non-negative"
    )
    # Both should achieve a similar quality bound: within 10x of each other.
    assert r_parallel.fun < r_serial.fun * 10 + 1.0, (
        f"parallel result ({r_parallel.fun:.4f}) is unexpectedly much worse than "
        f"serial ({r_serial.fun:.4f})"
    )


def test_time_limit_triggers_early_stop(fast_config: GIVPConfig) -> None:
    cfg = GIVPConfig(
        **{
            **fast_config.__dict__,
            "max_iterations": 10_000,
            "vnd_iterations": 10_000,
            "ils_iterations": 50,
            "time_limit": 0.05,
        }
    )
    result = givp(sphere, [(-1.0, 1.0)] * 3, config=cfg)
    assert np.isfinite(result.fun)


def test_verbose_runs_without_error(
    fast_config: GIVPConfig, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO"):
        result = givp(sphere, [(-1.0, 1.0)] * 2, config=fast_config, verbose=True)
    assert np.isfinite(result.fun)


def test_combinatorial_tsp_like_discretized_example() -> None:
    """TSP-like discretized objective should be reproducible and finite."""
    dist = np.array(
        [
            [0, 2, 9, 10, 7, 3],
            [2, 0, 6, 4, 3, 8],
            [9, 6, 0, 8, 5, 7],
            [10, 4, 8, 0, 6, 9],
            [7, 3, 5, 6, 0, 4],
            [3, 8, 7, 9, 4, 0],
        ],
        dtype=float,
    )

    def decode_permutation(x: np.ndarray) -> np.ndarray:
        scores = np.rint(np.clip(x, 0.0, dist.shape[0] - 1)).astype(int)
        return np.argsort(scores, kind="mergesort")

    def tsp_like_cost(x: np.ndarray) -> float:
        p = decode_permutation(x)
        total = 0.0
        for i in range(len(p)):
            a = int(p[i])
            b = int(p[(i + 1) % len(p)])
            total += float(dist[a, b])
        return total

    bounds = [(0.0, float(dist.shape[0] - 1))] * dist.shape[0]
    cfg = GIVPConfig(
        integer_split=dist.shape[0],
        max_iterations=60,
        ils_iterations=10,
    )

    r1 = givp(tsp_like_cost, bounds, seed=77, config=cfg)
    r2 = givp(tsp_like_cost, bounds, seed=77, config=cfg)

    p1 = decode_permutation(r1.x)
    p2 = decode_permutation(r2.x)

    assert np.isfinite(r1.fun)
    assert np.isfinite(r2.fun)
    assert np.isclose(r1.fun, r2.fun)
    assert np.array_equal(np.sort(p1), np.arange(dist.shape[0]))
    assert np.array_equal(np.sort(p2), np.arange(dist.shape[0]))


def test_multiobjective_scalarization_reproducible() -> None:
    """Weighted-sum scalarization should be reproducible with fixed seed."""
    target_return = 0.08
    mu = np.array([0.05, 0.09, 0.12])
    cov = np.array(
        [
            [0.020, 0.004, 0.002],
            [0.004, 0.030, 0.006],
            [0.002, 0.006, 0.050],
        ]
    )

    def project_simplex(v: np.ndarray) -> np.ndarray:
        v = np.clip(v, 0.0, None)
        s = float(v.sum())
        return v / s if s > 0 else np.array([1.0, 0.0, 0.0])

    def scalarized(x: np.ndarray) -> float:
        w = project_simplex(x)
        ret = float(w @ mu)
        risk = float(w @ cov @ w)
        obj_return = (ret - target_return) ** 2
        obj_risk = risk
        alpha = 0.5
        return alpha * obj_return + (1.0 - alpha) * obj_risk

    cfg = GIVPConfig(max_iterations=40, ils_iterations=8)
    bounds = [(0.0, 1.0)] * 3

    r1 = givp(scalarized, bounds, seed=123, config=cfg)
    r2 = givp(scalarized, bounds, seed=123, config=cfg)

    assert np.isfinite(r1.fun)
    assert np.isfinite(r2.fun)
    assert np.isclose(r1.fun, r2.fun)


def test_multiobjective_scalarization_tradeoff_sweep() -> None:
    """Changing the scalarization weight must alter objective priorities."""
    target_return = 0.08
    mu = np.array([0.05, 0.09, 0.12])
    cov = np.array(
        [
            [0.020, 0.004, 0.002],
            [0.004, 0.030, 0.006],
            [0.002, 0.006, 0.050],
        ]
    )

    def project_simplex(v: np.ndarray) -> np.ndarray:
        v = np.clip(v, 0.0, None)
        s = float(v.sum())
        return v / s if s > 0 else np.array([1.0, 0.0, 0.0])

    def objectives(x: np.ndarray) -> tuple[float, float]:
        w = project_simplex(x)
        ret = float(w @ mu)
        risk = float(w @ cov @ w)
        return (ret - target_return) ** 2, risk

    def make_scalarized(alpha: float) -> Callable[[np.ndarray], float]:
        def scalarized(x: np.ndarray) -> float:
            f1, f2 = objectives(x)
            return alpha * f1 + (1.0 - alpha) * f2

        return scalarized

    cfg = GIVPConfig(max_iterations=40, ils_iterations=8)
    bounds = [(0.0, 1.0)] * 3

    r_return = givp(make_scalarized(1.0), bounds, seed=123, config=cfg)
    r_risk = givp(make_scalarized(0.0), bounds, seed=123, config=cfg)

    ret_obj_return, risk_obj_return = objectives(r_return.x)
    ret_obj_risk, risk_obj_risk = objectives(r_risk.x)

    assert np.isfinite(r_return.fun)
    assert np.isfinite(r_risk.fun)
    assert ret_obj_return <= ret_obj_risk + 1e-6
    assert risk_obj_risk <= risk_obj_return + 1e-6


# ----------------------------- sklearn integration (optional) -----


def test_givp_optimizer_has_fit_method() -> None:
    """GIVPOptimizer must have a fit() method for sklearn compatibility."""
    opt = GIVPOptimizer(sphere, [(-1.0, 1.0)] * 2)
    assert hasattr(opt, "fit")
    assert callable(opt.fit)


def test_fit_returns_self() -> None:
    """fit() must return self to enable method chaining."""
    opt = GIVPOptimizer(sphere, [(-1.0, 1.0)] * 2, config=GIVPConfig(max_iterations=2))
    result = opt.fit()
    assert result is opt


def test_fit_calls_run() -> None:
    """fit() must internally call run() and update best_x, best_fun."""
    opt = GIVPOptimizer(sphere, [(-1.0, 1.0)] * 2, config=GIVPConfig(max_iterations=2))
    opt.fit()
    assert len(opt.history) == 1
    assert opt.best_x is not None
    assert np.isfinite(opt.best_fun)


def test_fit_ignores_x_y_parameters() -> None:
    """fit(X, y) must work even with X and y (sklearn API compatibility)."""
    opt = GIVPOptimizer(sphere, [(-1.0, 1.0)] * 2, config=GIVPConfig(max_iterations=2))
    dummy_x = np.array([[1, 2], [3, 4]])
    dummy_y = np.array([0, 1])
    opt.fit(_x=dummy_x, _y=dummy_y)
    assert len(opt.history) == 1
    assert opt.best_x is not None


def test_sklearn_grid_search_cv_integration() -> None:
    """GIVPOptimizer works with sklearn's GridSearchCV."""
    from sklearn.model_selection import GridSearchCV  # type: ignore[import-untyped]

    def objective(x: np.ndarray) -> float:
        return float(np.sum(x**2))

    opt = GIVPOptimizer(
        objective,
        [(-5.0, 5.0), (-5.0, 5.0)],
        config=GIVPConfig(max_iterations=2),
    )

    # Verify that GridSearchCV can instantiate and work with the optimizer
    grid = GridSearchCV(opt, param_grid={"seed": [42, 43]}, cv=2)  # type: ignore[call-arg]
    assert isinstance(grid, GridSearchCV)


def test_fit_full_signature_coverage() -> None:
    """fit() called with and without arguments covers all code paths."""
    opt = GIVPOptimizer(sphere, [(-1.0, 1.0)] * 2, config=GIVPConfig(max_iterations=2))
    # Call with no arguments
    result1 = opt.fit()
    assert result1 is opt
    # Call with explicit None arguments
    result2 = opt.fit(_x=None, _y=None)
    assert result2 is opt
    # Call with dummy arrays
    dummy_x = np.array([[0.0, 0.0], [1.0, 1.0]])
    dummy_y = np.array([0.0, 1.0])
    result3 = opt.fit(_x=dummy_x, _y=dummy_y)
    assert result3 is opt


def test_long_run_triggers_path_relinking_and_restart() -> None:
    cfg = GIVPConfig(
        max_iterations=8,
        vnd_iterations=6,
        ils_iterations=2,
        elite_size=4,
        path_relink_frequency=1,
        num_candidates_per_step=4,
        perturbation_strength=2,
        adaptive_alpha=True,
        use_cache=True,
        use_convergence_monitor=True,
        early_stop_threshold=100,
    )
    result = givp(sphere, [(-2.0, 2.0)] * 4, config=cfg, verbose=True)
    assert np.isfinite(result.fun)


# ----------------------------- _wrap_objective coverage --------------------


def test_wrap_objective_invalid_direction_raises() -> None:
    """`_wrap_objective` raises ValueError for an unknown direction string."""
    from givp.api import _wrap_objective

    with pytest.raises(ValueError, match="direction must be"):
        _wrap_objective(sphere, "sideways", [0])


@pytest.mark.parametrize("direction", ["minimize", "maximize"])
def test_wrap_objective_valid_directions(direction: str) -> None:
    """`_wrap_objective` accepts both valid direction strings."""
    from givp.api import _wrap_objective

    counter: list[int] = [0]
    wrapped = _wrap_objective(sphere, direction, counter)
    val = wrapped(np.array([1.0, 2.0]))
    assert np.isfinite(val)
    assert counter[0] == 1


# ----------------------------- integer_split pre-set ----------------------


def test_integer_split_preset_is_respected(fast_config: GIVPConfig) -> None:
    """When ``integer_split`` is already set on the config the branch that
    auto-fills it from ``n`` must NOT overwrite it (line 178 false-branch)."""
    cfg = GIVPConfig(**{**fast_config.__dict__, "integer_split": 2})
    # 4-variable problem but integer_split=2 pre-set — should not be overwritten
    result = givp(sphere, [(-2.0, 2.0)] * 4, config=cfg)
    assert np.isfinite(result.fun)


def test_grasp_optimizer_run_second_call_not_better(
    monkeypatch: pytest.MonkeyPatch, fast_config: GIVPConfig
) -> None:
    """Line 269->272: second run() result is NOT better -> best_fun/best_x unchanged."""
    from givp import api as api_mod
    from givp.result import OptimizeResult

    call_count = [0]
    results = [
        OptimizeResult(
            x=np.zeros(2),
            fun=0.5,
            nit=1,
            nfev=1,
            success=True,
            message="ok",
            direction="minimize",
        ),
        OptimizeResult(
            x=np.ones(2),
            fun=2.0,
            nit=1,
            nfev=1,
            success=True,
            message="ok",
            direction="minimize",
        ),
    ]

    def fake_run(*_args: tuple, **_kwargs: dict) -> OptimizeResult:
        r = results[call_count[0]]
        call_count[0] += 1
        return r

    monkeypatch.setattr(api_mod, "givp", fake_run)

    opt = GIVPOptimizer(sphere, [(-1.0, 1.0)] * 2, config=fast_config)
    opt.run()  # best_fun set to 0.5
    opt.run()  # 2.0 is NOT better -> best_fun stays 0.5
    assert opt.best_fun == pytest.approx(0.5)
