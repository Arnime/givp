"""Tests for rendering figures from frozen benchmark results."""

from pathlib import Path

import pandas as pd
from synthetic_hydropower.paths import default_config_path
from synthetic_hydropower.reference_figures import render_reference_figures


def test_render_reference_figures_creates_three_pngs_per_scenario(
    tmp_path: Path,
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

    paths = render_reference_figures(
        reference_dir, default_config_path(), tmp_path / "figures"
    )

    assert len(paths) == 3
    assert all(path.is_file() for path in paths)
