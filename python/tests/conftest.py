# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Pytest fixtures for benchmark functions used in examples and tests."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from givp.examples import benchmark
from tests.fixtures import problems as _problems


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Clean transient test artifact directories at the end of a test session."""
    del session, exitstatus
    repo_root = Path(__file__).resolve().parents[2]
    for artifact_dir in (
        repo_root / ".hypothesis",
        repo_root / ".benchmarks",
        repo_root / "python" / ".hypothesis",
        repo_root / "python" / ".benchmarks",
    ):
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir, ignore_errors=True)


@pytest.fixture
def sphere() -> Callable:
    """Return the classic Sphere benchmark callable."""
    return benchmark.sphere


@pytest.fixture
def sphere_bounds_1d() -> list[tuple[float, float]]:
    """Return a typical 1D bound for the Sphere function."""
    return [(-5.12, 5.12)]


@pytest.fixture
def sphere_bounds_4d() -> list[tuple[float, float]]:
    """Return a typical 4D bound set for the Sphere function."""
    return [(-5.12, 5.12)] * 4


@pytest.fixture
def sphere_file() -> str:
    """Path to the example sphere function file in `tests/fixtures`."""
    return str(Path(__file__).parent / "fixtures" / "sphere.py")


@pytest.fixture
def knapsack_values() -> list[int]:
    """Return knapsack values from the fixtures module."""
    return list(_problems.KNAP_VALUES)


@pytest.fixture
def knapsack_weights() -> list[int]:
    """Return knapsack weights from the fixtures module."""
    return list(_problems.KNAP_WEIGHTS)


@pytest.fixture
def knapsack_capacity() -> int:
    """Return knapsack capacity from the fixtures module."""
    return int(_problems.KNAP_CAPACITY)


@pytest.fixture
def qap_flow() -> NDArray[np.float64]:
    """Return the flow matrix for a small QAP instance."""
    return _problems.QAP_FLOW.copy()


@pytest.fixture
def qap_dist() -> NDArray[np.float64]:
    """Return the distance matrix for a small QAP instance."""
    return _problems.QAP_DIST.copy()
