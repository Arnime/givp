# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Smoke tests for publishing benchmark documentation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.publishing import cli as publishing_cli


@pytest.mark.slow
def test_benchmark_publishing_smoke(tmp_path: Path) -> None:
    publisher = publishing_cli

    python_like = {
        "metadata": {"dims": 3, "n_runs": 2, "algorithms": ["GIVP-full", "GRASP-only"]},
        "summary": [
            {
                "function": "Sphere",
                "algorithm": "GIVP-full",
                "n_runs": 2,
                "mean": 1e-4,
                "std": 2e-5,
                "median": 9e-5,
                "nfev_mean": 100.0,
                "time_s": 0.12,
            },
            {
                "function": "Sphere",
                "algorithm": "GRASP-only",
                "n_runs": 2,
                "mean": 1e-2,
                "std": 1e-3,
                "median": 1.1e-2,
                "nfev_mean": 80.0,
                "time_s": 0.03,
            },
        ],
    }
    r_like = {
        "metadata": {"n_dims": 4, "n_runs": 3},
        "summary": [
            {
                "function_name": "Ackley",
                "algorithm": "GIVP-full",
                "mean_fun": 2.5,
                "sd_fun": 0.3,
                "median_fun": 2.4,
                "mean_nfev": 500.0,
                "mean_time_s": 1.2,
            },
            {
                "function_name": "Ackley",
                "algorithm": "GRASP-only",
                "mean_fun": 8.0,
                "sd_fun": 0.9,
                "median_fun": 7.9,
                "mean_nfev": 90.0,
                "mean_time_s": 0.2,
            },
        ],
    }

    python_json = tmp_path / "python_results.json"
    r_json = tmp_path / "r_results.json"
    python_json.write_text(json.dumps(python_like), encoding="utf-8")
    r_json.write_text(json.dumps(r_like), encoding="utf-8")

    output_dir = tmp_path / "docs" / "examples" / "benchmark-reports"
    exit_code = publisher.main(
        [
            "--artifact",
            f"Python={python_json}",
            "--artifact",
            f"R={r_json}",
            "--repo-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "index.md").exists()
    assert (output_dir / "python.md").exists()
    assert (output_dir / "r.md").exists()
    assert (output_dir / "assets" / "python_mean_fun.svg").exists()
    assert (output_dir / "assets" / "r_time_mean_s.svg").exists()

    index_content = (output_dir / "index.md").read_text(encoding="utf-8")
    python_content = (output_dir / "python.md").read_text(encoding="utf-8")

    assert "Benchmark reports" in index_content
    assert "Python report" in index_content
    assert "Generated charts" in python_content
    assert "Sphere" in python_content
    assert "python -m benchmarks.publishing" in python_content
