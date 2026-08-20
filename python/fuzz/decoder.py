# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Decode arbitrary bytes into bounded optimization cases."""

from __future__ import annotations

import struct

import numpy as np

DecodedCase = tuple[list[tuple[float, float]], str]


def decode_case(data: bytes) -> DecodedCase | None:
    """Decode fuzz bytes or return ``None`` when they are unusable."""
    if len(data) < 4:
        return None

    dimensions = max(1, min(6, data[0] % 6 + 1))
    direction = "maximize" if data[1] % 2 else "minimize"
    payload = data[2:]
    if len(payload) < dimensions * 16:
        return None

    bounds: list[tuple[float, float]] = []
    for index in range(dimensions):
        lower, width = struct.unpack("dd", payload[index * 16 : index * 16 + 16])
        if not (np.isfinite(lower) and np.isfinite(width) and abs(width) >= 1e-4):
            return None
        bounds.append((lower, lower + abs(width)))
    return bounds, direction
