# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Normalized documentation artifact models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SummaryRow:
    """Normalized summary statistics for one function/algorithm pair."""

    function: str
    algorithm: str
    n_runs: int | None
    mean: float
    std: float | None
    best: float | None
    median: float | None
    worst: float | None
    nfev_mean: float | None
    time_mean_s: float | None


@dataclass(frozen=True)
class ArtifactReport:
    """Normalized documentation payload for one committed benchmark artifact."""

    label: str
    slug: str
    source_path: Path
    source_repo_path: str
    metadata: dict[str, Any]
    summary_rows: list[SummaryRow]
    algorithms: list[str]
    functions: list[str]
    dims: int | None
    n_runs: int | None
