# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""CLI command implementations."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from givp.api import givp
from givp.cli.loader import _load_func
from givp.cli.parsing import _parse_bounds, _parse_config, _resolve_args
from givp.config import GIVPConfig


def _normalize_config(raw_config: Any) -> GIVPConfig:
    """Normalize a JSON string, mapping or absent CLI configuration."""
    if isinstance(raw_config, dict):
        return GIVPConfig(**raw_config)
    return _parse_config(raw_config if isinstance(raw_config, str) else None)


def _cmd_run(namespace: argparse.Namespace) -> int:
    """Execute the optimizer run command and emit its JSON result."""
    try:
        args = _resolve_args(namespace)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    missing = [key for key in ("func_file", "func_name", "bounds") if key not in args]
    if missing:
        print(
            f"error: missing required argument(s): {', '.join(missing)}\n"
            "       Provide via --func-file/--func-name/--bounds or --json.",
            file=sys.stderr,
        )
        return 2

    try:
        objective = _load_func(args["func_file"], args["func_name"])
        raw_bounds = args["bounds"]
        bounds = (
            _parse_bounds(raw_bounds)
            if isinstance(raw_bounds, str)
            else [tuple(bound) for bound in raw_bounds]
        )
        result = givp(
            objective,
            bounds,
            direction=args.get("direction", "minimize"),
            config=_normalize_config(args.get("config")),
            seed=args.get("seed"),
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (AttributeError, ImportError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"error: unexpected failure — {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict()))
    return 0
