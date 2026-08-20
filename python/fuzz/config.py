# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Shared objective and optimizer configuration for fuzz targets."""

from __future__ import annotations

import numpy as np

from givp import GIVPConfig

FAST_CONFIG = GIVPConfig(
    max_iterations=2,
    vnd_iterations=3,
    ils_iterations=1,
    early_stop_threshold=2,
    use_convergence_monitor=False,
)


def sphere(values: np.ndarray) -> float:
    """Return the sum-of-squares objective value."""
    return float(np.sum(values**2))
