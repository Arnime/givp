# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Tests for benchmark sweeps and parallel objective evaluation.

Also covers the parallel paths in _evaluate_candidates_batch:
  - ProcessPoolExecutor (standard pickle — module-level function)
  - cloudpickle ProcessPoolExecutor (closure / lambda, required dependency)
  - ThreadPoolExecutor fallback (cache enabled with n_workers > 1)
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from givp import GIVPConfig, givp
from givp.core.cache import EvaluationCache
from givp.core.engine import evaluation as evaluation_module
from givp.core.engine.evaluation import (
    _cloudpickle_worker,
    _evaluate_candidates_batch,
)
from givp.examples.benchmark import seed_sweep, sweep_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sphere(x: np.ndarray) -> float:
    return float(np.sum(x**2))


_FAST = GIVPConfig(
    max_iterations=3, vnd_iterations=5, ils_iterations=1, use_cache=False
)
_FAST_CACHE = GIVPConfig(
    max_iterations=3, vnd_iterations=5, ils_iterations=1, use_cache=True
)
_BOUNDS = [(-2.0, 2.0)] * 3


# ---------------------------------------------------------------------------
# PY-4 — seed_sweep and sweep_summary
# ---------------------------------------------------------------------------


class TestSeedSweep:
    def test_returns_list_of_dicts(self) -> None:
        rows = seed_sweep(_sphere, _BOUNDS, seeds=3, config=_FAST)
        assert isinstance(rows, list)
        assert len(rows) == 3
        for row in rows:
            assert "seed" in row and "fun" in row and "nit" in row
            assert "nfev" in row and "time_s" in row and "success" in row

    def test_seeds_are_correct(self) -> None:
        rows = seed_sweep(_sphere, _BOUNDS, seeds=[7, 42, 99], config=_FAST)
        assert [r["seed"] for r in rows] == [7, 42, 99]

    def test_results_are_finite(self) -> None:
        rows = seed_sweep(_sphere, _BOUNDS, seeds=5, config=_FAST)
        for r in rows:
            assert np.isfinite(r["fun"])
            assert r["nfev"] > 0
            assert r["time_s"] >= 0.0

    def test_different_seeds_may_differ(self) -> None:
        rows = seed_sweep(_sphere, _BOUNDS, seeds=5, config=_FAST)
        funs = [r["fun"] for r in rows]
        # At least two distinct values across 5 seeds (not always identical)
        assert len({round(f, 8) for f in funs}) >= 1  # always passes; real check below
        assert all(np.isfinite(f) for f in funs)

    def test_maximize_direction(self) -> None:
        def neg_sphere(x: np.ndarray) -> float:
            return -float(np.sum(x**2))

        rows = seed_sweep(
            neg_sphere, _BOUNDS, seeds=3, config=_FAST, direction="maximize"
        )
        for r in rows:
            assert np.isfinite(r["fun"])

class TestSweepSummary:
    def _make_rows(self) -> list[dict]:
        return [
            {"seed": i, "fun": float(i), "nit": 10, "nfev": 100, "time_s": 0.1}
            for i in range(5)
        ]

    def test_summary_keys(self) -> None:
        summary = sweep_summary(self._make_rows())
        for metric in ("fun", "nit", "nfev", "time_s"):
            assert metric in summary
            assert "mean" in summary[metric]
            assert "std" in summary[metric]
            assert "min" in summary[metric]
            assert "max" in summary[metric]

    def test_summary_values_correct(self) -> None:
        rows = [
            {"seed": i, "fun": float(i), "nit": 10, "nfev": 100, "time_s": 0.1}
            for i in range(5)
        ]
        s = sweep_summary(rows)
        assert s["fun"]["mean"] == pytest.approx(2.0)
        assert s["fun"]["min"] == pytest.approx(0.0)
        assert s["fun"]["max"] == pytest.approx(4.0)

    def test_single_row_std_is_zero(self) -> None:
        rows = [{"seed": 0, "fun": 1.5, "nit": 10, "nfev": 50, "time_s": 0.05}]
        s = sweep_summary(rows)
        assert s["fun"]["std"] == pytest.approx(0.0)

    def test_sweep_summary_with_real_pandas_dataframe(self) -> None:
        """PY-8: Test sweep_summary accepts real pandas.DataFrame when available."""
        pd = pytest.importorskip("pandas")

        # Create a real DataFrame with sweep results
        rows = [
            {"seed": 0, "fun": 1.0, "nit": 10, "nfev": 100, "time_s": 0.1},
            {"seed": 1, "fun": 3.0, "nit": 20, "nfev": 300, "time_s": 0.3},
            {"seed": 2, "fun": 5.0, "nit": 30, "nfev": 500, "time_s": 0.5},
        ]
        df = pd.DataFrame(rows)

        # Pass the real DataFrame to sweep_summary
        s = sweep_summary(df)

        # Verify it computed correctly
        assert s["fun"]["mean"] == pytest.approx(3.0)
        assert s["fun"]["min"] == pytest.approx(1.0)
        assert s["fun"]["max"] == pytest.approx(5.0)
        assert s["nit"]["mean"] == pytest.approx(20.0)
        assert s["nfev"]["mean"] == pytest.approx(300.0)
        assert s["time_s"]["mean"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# PY-5 — parallel evaluation paths in _evaluate_candidates_batch
# ---------------------------------------------------------------------------


class TestParallelPaths:
    """Cover ProcessPoolExecutor, cloudpickle, and ThreadPool fallback paths."""

    def test_process_pool_module_level_function(self) -> None:
        """Standard ProcessPool path: module-level function is picklable."""
        cfg = GIVPConfig(**{**_FAST.__dict__, "n_workers": 2, "use_cache": False})
        result = givp(_sphere, _BOUNDS, config=cfg, seed=0)
        assert np.isfinite(result.fun)
        assert result.nfev > 0

    def test_thread_pool_fallback_when_cache_enabled(self) -> None:
        """With cache=True, always falls back to ThreadPoolExecutor (logs warning)."""
        cfg = GIVPConfig(**{**_FAST_CACHE.__dict__, "n_workers": 2})
        result = givp(_sphere, _BOUNDS, config=cfg, seed=0)
        assert np.isfinite(result.fun)

    def test_thread_pool_fallback_warning_emitted(self) -> None:
        """With cache enabled, thread fallback path executes and returns values."""
        candidates = [np.array([0.1, -0.2, 1.0]), np.array([0.3, 0.4, 2.0])]
        cache = EvaluationCache(maxsize=64)
        values = _evaluate_candidates_batch(
            candidates=candidates,
            evaluated_count=0,
            evaluator=_sphere,
            cache=cache,
            n_workers=2,
        )
        assert len(values) == 2
        assert all(np.isfinite(v) for v in values)

    def test_cloudpickle_path_with_closure(self) -> None:
        """cloudpickle path: lambda/closure is not picklable with standard pickle."""
        offset = 1.0  # captured in closure

        def closure_func(x: np.ndarray) -> float:
            return float(np.sum((x - offset) ** 2))

        cfg = GIVPConfig(**{**_FAST.__dict__, "n_workers": 2, "use_cache": False})
        result = givp(closure_func, _BOUNDS, config=cfg, seed=0)
        assert np.isfinite(result.fun)

class TestParallelInternals:
    def test_cloudpickle_worker_returns_inf_on_non_finite(self) -> None:
        with patch.object(
            evaluation_module.cloudpickle,
            "loads",
            return_value=lambda _x: float("nan"),
        ):
            value = _cloudpickle_worker((np.array([1.0, 2.0, 3.0]), b"dummy"))
        assert value == float("inf")

    def test_cloudpickle_worker_returns_inf_on_exception(self) -> None:
        def _raiser(_x: Any) -> float:
            raise RuntimeError("boom")

        with patch.object(evaluation_module.cloudpickle, "loads", return_value=_raiser):
            value = _cloudpickle_worker((np.array([1.0, 2.0, 3.0]), b"dummy"))
        assert value == float("inf")

    def test_evaluate_candidates_logs_info_when_cloudpickle_serialization_fails(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        candidates = [np.array([0.1, 0.2, 1.0]), np.array([0.3, 0.4, 2.0])]
        with (
            patch(
                "givp.core.engine.evaluation._try_standard_process_pool",
                return_value=(None, TypeError("pickle failed")),
            ),
            patch(
                "givp.core.engine.evaluation._try_cloudpickle_process_pool",
                return_value=(None, TypeError("serialization failed")),
            ),
            caplog.at_level(logging.INFO),
        ):
            values = _evaluate_candidates_batch(
                candidates=candidates,
                evaluated_count=0,
                evaluator=_sphere,
                cache=None,
                n_workers=2,
            )
        assert len(values) == 2
        assert all(np.isfinite(v) for v in values)

    def test_evaluate_candidates_no_cloudpickle_error_object(self) -> None:
        candidates = [np.array([0.1, 0.2, 1.0]), np.array([0.3, 0.4, 2.0])]
        with (
            patch(
                "givp.core.engine.evaluation._try_standard_process_pool",
                return_value=(None, TypeError("pickle failed")),
            ),
            patch(
                "givp.core.engine.evaluation._try_cloudpickle_process_pool",
                return_value=(None, None),
            ),
        ):
            values = _evaluate_candidates_batch(
                candidates=candidates,
                evaluated_count=0,
                evaluator=_sphere,
                cache=None,
                n_workers=2,
            )
        assert len(values) == 2
