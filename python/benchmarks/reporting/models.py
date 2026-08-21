# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Typed statistical report records."""

from typing import NamedTuple


class RunRecord(NamedTuple):
    """Immutable record for a single (algorithm, function, seed) run result."""

    algorithm: str
    function: str
    seed: int
    fun: float
    nit: int
    nfev: int
    time_s: float
    trace: list[float] | None


class SummaryRow(NamedTuple):
    """Pre-computed descriptive statistics for one (function, algorithm) cell."""

    function: str
    algorithm: str
    n_runs: int
    mean: float
    std: float
    best: float
    median: float
    worst: float
    nfev_mean: float


class WilcoxonRow(NamedTuple):
    """Result of a Wilcoxon signed-rank test for one (challenger, function) pair."""

    function: str
    algorithm: str  # the challenger
    reference: str  # the reference algorithm
    stat: float
    pvalue: float
    effect_r: float  # rank-biserial correlation
    significant: bool


class FriedmanRow(NamedTuple):
    """Result of Friedman omnibus test for one benchmark function."""

    function: str
    n_blocks: int
    n_algorithms: int
    stat: float
    pvalue: float
    significant: bool
    mean_ranks: dict[str, float]
