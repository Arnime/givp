# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Optuna workflows for synthetic hydropower benchmarks."""

from benchmarks.tuning.hydropower.cli import main
from benchmarks.tuning.hydropower.runner import run_tuning

__all__ = ["main", "run_tuning"]
