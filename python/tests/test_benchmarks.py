# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Unit tests for the functions in `givp.examples.benchmark`.

These tests assert that the classic functions return their known minima
at the canonical inputs (e.g. zeros or ones) and exercise the knapsack DP
helper with a small instance.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from givp.examples import benchmark


def test_sphere_zero() -> None:
    assert benchmark.sphere(np.zeros(3)) == pytest.approx(0.0)


def test_rosenbrock_ones() -> None:
    assert benchmark.rosenbrock(np.ones(5)) == pytest.approx(0.0)


def test_rastrigin_zero() -> None:
    assert benchmark.rastrigin(np.zeros(4)) == pytest.approx(0.0)


def test_ackley_zero() -> None:
    assert benchmark.ackley(np.zeros(6)) == pytest.approx(0.0)


def test_griewank_zero() -> None:
    assert benchmark.griewank(np.zeros(5)) == pytest.approx(0.0)


def test_schwefel_known_optimum() -> None:
    # Schwefel has known minimum near 420.9687 per-coordinate (value ~ 0)
    x = np.full(3, 420.9687)
    assert benchmark.schwefel(x) == pytest.approx(0.0, abs=1e-3)


def test_knapsack_dp_small(
    knapsack_values: Sequence[int],
    knapsack_weights: Sequence[int],
    knapsack_capacity: int,
) -> None:
    val, sel = benchmark.knapsack_dp(
        knapsack_values, knapsack_weights, knapsack_capacity
    )
    assert val == 220
    assert np.array_equal(sel, np.array([0, 1, 1]))


def test_knapsack_penalty_selection(
    knapsack_values: Sequence[int],
    knapsack_weights: Sequence[int],
    knapsack_capacity: int,
) -> None:
    x = np.array([0.0, 1.0, 1.0])
    val = benchmark.knapsack_penalty(
        x, knapsack_values, knapsack_weights, knapsack_capacity, overflow_penalty=1000.0
    )
    assert val == pytest.approx(-220.0)


def test_qap_cost_matches_manual(qap_flow: np.ndarray, qap_dist: np.ndarray) -> None:
    x = np.array([0.2, 0.1])  # permutation [1, 0]
    cost = benchmark.qap_cost(x, qap_flow, qap_dist)
    assert cost == pytest.approx(10.0)


def test_rosenbrock_short_vector() -> None:
    # exercise the x.size < 2 branch
    assert benchmark.rosenbrock(np.array([1.0])) == pytest.approx(0.0)


def test_ackley_empty_vector() -> None:
    # exercise the n == 0 branch
    assert benchmark.ackley(np.array([])) == pytest.approx(0.0)


def test_griewank_empty_vector() -> None:
    # exercise the x.size == 0 branch
    assert benchmark.griewank(np.array([])) == pytest.approx(1.0)


def test_constrained_cubic_is_finite() -> None:
    val = benchmark.constrained_cubic(np.array([10.0, 20.0]))
    assert isinstance(val, float)
    assert np.isfinite(val)
