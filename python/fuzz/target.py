# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Backend-independent GIVP fuzz target."""

from __future__ import annotations

import numpy as np

from fuzz.config import FAST_CONFIG, sphere
from fuzz.decoder import decode_case
from givp import givp


def run_case(bounds: list[tuple[float, float]], direction: str) -> None:
    """Run and validate one decoded optimization case."""
    result = givp(sphere, bounds, direction=direction, config=FAST_CONFIG)
    assert result.x.shape == (len(bounds),)
    assert np.isfinite(result.fun)


def fuzz_bytes(data: bytes) -> None:
    """Run a fuzz case encoded as arbitrary bytes when it is valid."""
    case = decode_case(data)
    if case is not None:
        run_case(*case)
