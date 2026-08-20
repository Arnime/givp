# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""JSON and argument normalization for the command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from givp.config import GIVPConfig


def _parse_bounds(raw: str) -> list[tuple[float, float]]:
    """Parse a JSON array of lower and upper bound pairs."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--bounds must be valid JSON, got: {raw!r}") from exc
    if not isinstance(parsed, list):
        raise ValueError("--bounds must be a JSON array, e.g. [[-5,5],[-5,5]]")

    result: list[tuple[float, float]] = []
    for item in parsed:
        if not (isinstance(item, (list, tuple)) and len(item) == 2):
            raise ValueError(f"Each bound must be [low, high], got: {item!r}")
        result.append((float(item[0]), float(item[1])))
    return result


def _parse_config(raw: str | None) -> GIVPConfig:
    """Parse an optional JSON object into an optimizer configuration."""
    if raw is None:
        return GIVPConfig()
    try:
        kwargs = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--config must be valid JSON, got: {raw!r}") from exc
    if not isinstance(kwargs, dict):
        raise ValueError("--config must be a JSON object")
    return GIVPConfig(**kwargs)


def _resolve_args(namespace: argparse.Namespace) -> dict[str, Any]:
    """Merge JSON input with higher-priority explicit command-line flags."""
    merged: dict[str, Any] = {}
    if namespace.json_input is not None:
        raw = namespace.json_input
        if raw == "-":
            raw = sys.stdin.read()
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--json must be valid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise ValueError("--json must contain a JSON object")
        merged = decoded

    for attribute, key in (
        ("func_file", "func_file"),
        ("func_name", "func_name"),
        ("bounds", "bounds"),
        ("direction", "direction"),
        ("config", "config"),
        ("seed", "seed"),
    ):
        value = getattr(namespace, attribute)
        if value is not None:
            merged[key] = value
    return merged
