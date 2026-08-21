"""Tests for the experiment-local benchmark figure renderer."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import pandas as pd
import pytest

from givp.examples.synthetic_hydropower.paths import default_config_path

FigureRenderer = Callable[[Path, Path, Path], list[Path]]


def _load_figures_module(project_root: Path) -> ModuleType:
    """Load the notebook-local figure module without making it a GIVP package."""
    module_path = (
        project_root
        / "experiments"
        / "synthetic_hydropower"
        / "notebooks"
        / "figures.py"
    )
    spec = importlib.util.spec_from_file_location(
        "synthetic_hydropower_notebook_figures", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load figure module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_figures_creates_three_pngs_per_scenario(
    tmp_path: Path,
    pytestconfig: pytest.Config,
) -> None:
    """Render the expected visual artifacts from a minimal valid time series."""
    reference_dir = tmp_path / "reference_results"
    reference_dir.mkdir()
    rows = []
    for plant, initial_level, final_level in (("A", 147.0, 147.1), ("B", 103.0, 103.1)):
        for period in range(2):
            rows.append(
                {
                    "scenario": "case",
                    "plant": plant,
                    "period": period,
                    "total_inflow_m3s": 100.0,
                    "turbine_flow_m3s": 90.0,
                    "spill_flow_m3s": 10.0,
                    "power_mw": 50.0,
                    "initial_upstream_level_m": initial_level,
                    "final_upstream_level_m": final_level,
                }
            )
    pd.DataFrame(rows).to_csv(reference_dir / "benchmark_time_series.csv", index=False)

    python_root = pytestconfig.rootpath
    project_root = python_root.parent if python_root.name == "python" else python_root
    module = _load_figures_module(project_root)
    render_figures = cast(FigureRenderer, module.render_figures)
    paths = render_figures(reference_dir, default_config_path(), tmp_path / "figures")

    assert len(paths) == 3
    assert all(path.is_file() for path in paths)
