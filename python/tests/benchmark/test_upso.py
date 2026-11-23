# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Unit tests for the Pymoo-backed unified swarm baseline."""

from __future__ import annotations

import math

import numpy as np
import pytest

from benchmarks.comparison.cli import _build_parser
from benchmarks.comparison.pymoo import run_pymoo
from benchmarks.comparison.upso import UPSO


def test_upso_optimizes_a_bounded_sphere() -> None:
    """UPSO executes through Pymoo and reports its evaluation count."""
    value, iterations, evaluations = run_pymoo(
        "UPSO",
        lambda values: float(np.dot(values, values)),
        [(-1.0, 1.0), (-1.0, 1.0)],
        seed=44,
        max_iter=8,
    )

    assert math.isfinite(value)
    assert iterations == 8
    assert evaluations > 0


def test_upso_defaults_match_the_notebook_variant() -> None:
    """The named baseline preserves the legacy notebook's published controls."""
    algorithm = UPSO(max_generations=8)

    assert algorithm.unification_factor == 0.3
    assert algorithm.w_min == 0.6
    assert algorithm.w_max == 0.9
    assert algorithm.c1 == 0.6
    assert algorithm.c2 == 0.4


def test_comparison_cli_includes_upso_by_default() -> None:
    """The standard literature run includes the UPSO baseline."""
    assert "UPSO" in _build_parser().parse_args([]).algorithms


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"unification_factor": -0.1}, "unification_factor"),
        ({"neighborhood_size": 2}, "neighborhood_size"),
        ({"w_min": 1.0, "w_max": 0.5}, "inertia weights"),
        ({"c1": -0.1}, "acceleration coefficients"),
        ({"max_generations": 0}, "max_generations"),
    ],
)
def test_upso_rejects_invalid_hyperparameters(
    kwargs: dict[str, float | int], message: str
) -> None:
    """UPSO rejects invalid controls before an optimization run starts."""
    configuration: dict[str, float | int] = {"max_generations": 8}
    configuration.update(kwargs)
    with pytest.raises(ValueError, match=message):
        UPSO(**configuration)
