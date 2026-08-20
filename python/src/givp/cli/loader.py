# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Safe loading of user-defined objective functions."""

from __future__ import annotations

import importlib.util
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast


def _load_func(func_file: str, func_name: str) -> Callable[..., Any]:
    """Load an objective callable from a Python source file."""
    path = Path(func_file).resolve()
    if not path.exists():
        raise FileNotFoundError(f"func-file not found: {path}")

    spec = importlib.util.spec_from_file_location("_givp_user_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from: {path}")

    module: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, func_name):
        available_names = [name for name in dir(module) if not name.startswith("_")]
        raise AttributeError(
            f"Function '{func_name}' not found in '{path}'. "
            f"Available names: {available_names}"
        )
    loaded = getattr(module, func_name)
    if not callable(loaded):
        raise TypeError(f"'{func_name}' in '{path}' is not callable")
    return cast(Callable[..., Any], loaded)
