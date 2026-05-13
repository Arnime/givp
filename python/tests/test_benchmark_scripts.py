# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Smoke tests for the benchmark scripts (tune_hyperparams, run_literature_comparison,
generate_report).

These tests exercise the full CLI pipeline with minimal settings so they
complete in a few seconds on any machine.  They are marked ``slow`` and
excluded from the default test run to keep CI fast.

Run explicitly with:
    pytest -m slow python/tests/test_benchmark_scripts.py
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_script(script_name: str) -> Any:
    """Import a benchmark script from python/benchmarks/ by module name."""
    benchmarks_dir = Path(__file__).parent.parent / "benchmarks"
    if str(benchmarks_dir) not in sys.path:
        sys.path.insert(0, str(benchmarks_dir))
    return importlib.import_module(script_name)


def _run_script_main(script_name: str, args: list[str]) -> Any:
    """Run benchmark script main with CLI-like args."""
    return _import_script(script_name).main(args)


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _tune_smoke_args(output: Path, *, include_sampler_seed: bool) -> list[str]:
    args = [
        "--n-trials",
        "2",
        "--dims",
        "3",
        "--n-eval-seeds",
        "1",
        "--functions",
        "Sphere",
        "--max-iter",
        "10",
        "--time-limit",
        "5",
    ]
    if include_sampler_seed:
        args.extend(["--sampler-seed", "0"])
    args.extend(["--output", str(output)])
    return args


def _rlc_smoke_args(
    output: Path,
    *,
    functions: list[str],
    algorithms: list[str],
    tune_config: Path | None = None,
    resume: bool = False,
) -> list[str]:
    args = [
        "--dims",
        "3",
        "--n-runs",
        "2",
        "--max-iter",
        "10",
        "--time-limit",
        "5",
        "--functions",
        *functions,
        "--algorithms",
        *algorithms,
        "--output",
        str(output),
    ]
    if tune_config is not None:
        args.extend(["--tune-config", str(tune_config)])
    if resume:
        args.append("--resume")
    return args


# ---------------------------------------------------------------------------
# tune_hyperparams smoke test
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_tune_hyperparams_smoke(tmp_path: Path) -> None:
    """tune_hyperparams.main() produces a valid JSON config with best_params."""
    output = tmp_path / "best_config.json"

    exit_code = _run_script_main(
        "tune_hyperparams", _tune_smoke_args(output, include_sampler_seed=True)
    )

    assert exit_code == 0, "tune_hyperparams.main() returned non-zero exit code"
    assert output.exists(), "Output JSON not created"

    data = _read_json(output)
    assert "best_params" in data, "JSON missing 'best_params' key"
    assert "metadata" in data, "JSON missing 'metadata' key"
    assert data["metadata"]["n_trials"] == 2
    assert data["metadata"]["dims"] == 3

    # best_params must be a valid GIVPConfig
    from givp import GIVPConfig

    cfg = GIVPConfig(**data["best_params"])
    assert cfg.max_iterations > 0


# ---------------------------------------------------------------------------
# run_literature_comparison smoke test
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_run_literature_comparison_smoke(tmp_path: Path) -> None:
    """run_literature_comparison.main() produces valid results JSON."""
    output = tmp_path / "results.json"

    exit_code = _run_script_main(
        "run_literature_comparison",
        _rlc_smoke_args(
            output,
            functions=["Sphere"],
            algorithms=["GIVP-full", "GRASP-only"],
        ),
    )

    assert exit_code == 0, (
        "run_literature_comparison.main() returned non-zero exit code"
    )
    assert output.exists(), "Output JSON not created"

    data = _read_json(output)
    assert "metadata" in data
    assert "runs" in data
    assert "records" in data
    assert "summary" in data
    assert "stats" in data
    assert data["metadata"]["schema_version"] == "benchmark-schema-v1"
    assert data["metadata"]["n_runs"] == 2
    assert data["metadata"]["dims"] == 3
    assert "Sphere" in data["records"]
    assert len(data["runs"]) == 4
    assert data["stats"] == data["summary"]
    assert len(data["records"]["Sphere"]) == 4  # 2 algos x 2 runs


@pytest.mark.slow
def test_run_literature_comparison_with_tuned_config(tmp_path: Path) -> None:
    """GIVP-tuned algorithm works when --tune-config is supplied."""
    tune_output = tmp_path / "best_config.json"
    _run_script_main(
        "tune_hyperparams",
        _tune_smoke_args(tune_output, include_sampler_seed=False),
    )

    results_output = tmp_path / "results_tuned.json"
    exit_code = _run_script_main(
        "run_literature_comparison",
        _rlc_smoke_args(
            results_output,
            functions=["Sphere"],
            algorithms=["GIVP-full", "GIVP-tuned"],
            tune_config=tune_output,
        ),
    )

    assert exit_code == 0
    data = _read_json(results_output)
    algos_in_results = {r["algorithm"] for r in data["records"]["Sphere"]}
    assert "GIVP-tuned" in algos_in_results


@pytest.mark.slow
def test_run_literature_comparison_resume(tmp_path: Path) -> None:
    """--resume skips already-completed functions."""
    output = tmp_path / "results_resume.json"

    # First pass: run only Sphere
    _run_script_main(
        "run_literature_comparison",
        _rlc_smoke_args(output, functions=["Sphere"], algorithms=["GIVP-full"]),
    )
    assert output.exists()
    data_first = _read_json(output)
    sphere_records_first = list(data_first["records"]["Sphere"])

    # Second pass: resume — Sphere should be skipped; Rastrigin added
    exit_code = _run_script_main(
        "run_literature_comparison",
        _rlc_smoke_args(
            output,
            functions=["Sphere", "Rastrigin"],
            algorithms=["GIVP-full"],
            resume=True,
        ),
    )

    assert exit_code == 0
    data_resumed = _read_json(output)
    # Sphere records must be identical (skipped, not re-run)
    assert data_resumed["records"]["Sphere"] == sphere_records_first
    # Rastrigin must now be present
    assert "Rastrigin" in data_resumed["records"]
    assert len(data_resumed["records"]["Rastrigin"]) == 2


# ---------------------------------------------------------------------------
# generate_report smoke test
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_generate_report_smoke(tmp_path: Path) -> None:
    """generate_report.main() consumes results JSON and produces output files."""
    # Create minimal results JSON (no scipy needed)
    results = {
        "metadata": {
            "givp_version": "test",
            "dims": 3,
            "n_runs": 2,
            "seed_start": 0,
            "seeds": [0, 1],
            "max_iter": 10,
            "time_limit": 5.0,
            "algorithms": ["GIVP-full", "GRASP-only"],
            "functions": ["Sphere"],
            "algo_descriptions": {
                "GIVP-full": "full pipeline",
                "GRASP-only": "grasp only",
            },
            "problem_references": {"Sphere": "De Jong (1975)"},
        },
        "summary": [
            {
                "function": "Sphere",
                "algorithm": "GIVP-full",
                "n_runs": 2,
                "mean": 1e-4,
                "std": 1e-5,
                "best": 5e-5,
                "median": 1e-4,
                "worst": 2e-4,
                "nfev_mean": 100.0,
            },
            {
                "function": "Sphere",
                "algorithm": "GRASP-only",
                "n_runs": 2,
                "mean": 1e-2,
                "std": 1e-3,
                "best": 5e-3,
                "median": 1e-2,
                "worst": 2e-2,
                "nfev_mean": 80.0,
            },
        ],
        "records": {
            "Sphere": [
                {
                    "algorithm": "GIVP-full",
                    "seed": 0,
                    "fun": 5e-5,
                    "nit": 10,
                    "nfev": 100,
                    "time_s": 0.1,
                    "trace": None,
                },
                {
                    "algorithm": "GIVP-full",
                    "seed": 1,
                    "fun": 2e-4,
                    "nit": 10,
                    "nfev": 100,
                    "time_s": 0.1,
                    "trace": None,
                },
                {
                    "algorithm": "GRASP-only",
                    "seed": 0,
                    "fun": 5e-3,
                    "nit": 10,
                    "nfev": 80,
                    "time_s": 0.05,
                    "trace": None,
                },
                {
                    "algorithm": "GRASP-only",
                    "seed": 1,
                    "fun": 2e-2,
                    "nit": 10,
                    "nfev": 80,
                    "time_s": 0.05,
                    "trace": None,
                },
            ]
        },
    }
    input_path = tmp_path / "results.json"
    input_path.write_text(json.dumps(results), encoding="utf-8")

    gr = _import_script("generate_report")
    exit_code = gr.main(
        [
            "--input",
            str(input_path),
            "--format",
            "both",
            "--no-plots",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "results_report.md").exists(), "Markdown report not created"
    assert (tmp_path / "results_report.tex").exists(), "LaTeX report not created"

    md_content = (tmp_path / "results_report.md").read_text(encoding="utf-8")
    assert "GIVP-full" in md_content
    assert "Sphere" in md_content


# ---------------------------------------------------------------------------
# Error-path and flag coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_run_literature_comparison_missing_tune_config(tmp_path: Path) -> None:
    """--algorithms GIVP-tuned without --tune-config returns exit code 1."""
    rlc = _import_script("run_literature_comparison")
    exit_code = rlc.main(
        [
            "--algorithms",
            "GIVP-tuned",
            "--functions",
            "Sphere",
            "--output",
            str(tmp_path / "out.json"),
        ]
    )
    assert exit_code == 1


@pytest.mark.slow
def test_run_literature_comparison_verbose(tmp_path: Path) -> None:
    """--verbose flag produces the same valid output (exercises DEBUG logging path)."""
    rlc = _import_script("run_literature_comparison")
    output = tmp_path / "results_verbose.json"
    exit_code = rlc.main(
        [
            "--dims",
            "2",
            "--n-runs",
            "2",
            "--max-iter",
            "5",
            "--time-limit",
            "3",
            "--functions",
            "Sphere",
            "--algorithms",
            "GIVP-full",
            "--verbose",
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    assert output.exists()


@pytest.mark.slow
def test_run_literature_comparison_with_traces(tmp_path: Path) -> None:
    """--traces flag stores per-iteration trace lists in the output JSON."""
    rlc = _import_script("run_literature_comparison")
    output = tmp_path / "results_traces.json"
    exit_code = rlc.main(
        [
            "--dims",
            "2",
            "--n-runs",
            "2",
            "--max-iter",
            "5",
            "--time-limit",
            "3",
            "--functions",
            "Sphere",
            "--algorithms",
            "GIVP-full",
            "--traces",
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    # At least one record should have a non-null trace
    traces = [r["trace"] for r in data["records"]["Sphere"]]
    assert any(t is not None for t in traces)


@pytest.mark.slow
def test_generate_report_missing_input(tmp_path: Path) -> None:
    """generate_report.main() returns 1 when --input file does not exist."""
    gr = _import_script("generate_report")
    exit_code = gr.main(
        [
            "--input",
            str(tmp_path / "nonexistent.json"),
        ]
    )
    assert exit_code == 1


@pytest.mark.slow
def test_generate_report_bad_reference(tmp_path: Path) -> None:
    """generate_report.main() returns 1 when --reference algorithm is not in records."""
    results = {
        "metadata": {
            "givp_version": "test",
            "dims": 3,
            "n_runs": 2,
            "seed_start": 0,
            "seeds": [0, 1],
            "max_iter": 10,
            "time_limit": 5.0,
            "algorithms": ["GIVP-full"],
            "functions": ["Sphere"],
            "algo_descriptions": {"GIVP-full": "full pipeline"},
            "problem_references": {"Sphere": "De Jong (1975)"},
        },
        "summary": [
            {
                "function": "Sphere",
                "algorithm": "GIVP-full",
                "n_runs": 2,
                "mean": 1e-4,
                "std": 1e-5,
                "best": 5e-5,
                "median": 1e-4,
                "worst": 2e-4,
                "nfev_mean": 100.0,
            }
        ],
        "records": {
            "Sphere": [
                {
                    "algorithm": "GIVP-full",
                    "seed": 0,
                    "fun": 5e-5,
                    "nit": 10,
                    "nfev": 100,
                    "time_s": 0.1,
                    "trace": None,
                },
                {
                    "algorithm": "GIVP-full",
                    "seed": 1,
                    "fun": 2e-4,
                    "nit": 10,
                    "nfev": 100,
                    "time_s": 0.1,
                    "trace": None,
                },
            ]
        },
    }
    input_path = tmp_path / "results.json"
    input_path.write_text(json.dumps(results), encoding="utf-8")

    gr = _import_script("generate_report")
    exit_code = gr.main(
        [
            "--input",
            str(input_path),
            "--reference",
            "NONEXISTENT",
            "--no-plots",
        ]
    )
    assert exit_code == 1


@pytest.mark.slow
def test_generate_report_verbose_and_markdown_only(tmp_path: Path) -> None:
    """--verbose + --format markdown exercises DEBUG path and skips LaTeX."""
    results = {
        "metadata": {
            "givp_version": "test",
            "dims": 3,
            "n_runs": 2,
            "seed_start": 0,
            "seeds": [0, 1],
            "max_iter": 10,
            "time_limit": 5.0,
            "algorithms": ["GIVP-full", "GRASP-only"],
            "functions": ["Sphere"],
            "algo_descriptions": {
                "GIVP-full": "full pipeline",
                "GRASP-only": "grasp only",
            },
            "problem_references": {"Sphere": "De Jong (1975)"},
        },
        "summary": [
            {
                "function": "Sphere",
                "algorithm": "GIVP-full",
                "n_runs": 2,
                "mean": 1e-4,
                "std": 1e-5,
                "best": 5e-5,
                "median": 1e-4,
                "worst": 2e-4,
                "nfev_mean": 100.0,
            },
            {
                "function": "Sphere",
                "algorithm": "GRASP-only",
                "n_runs": 2,
                "mean": 1e-2,
                "std": 1e-3,
                "best": 5e-3,
                "median": 1e-2,
                "worst": 2e-2,
                "nfev_mean": 80.0,
            },
        ],
        "records": {
            "Sphere": [
                {
                    "algorithm": "GIVP-full",
                    "seed": 0,
                    "fun": 5e-5,
                    "nit": 10,
                    "nfev": 100,
                    "time_s": 0.1,
                    "trace": None,
                },
                {
                    "algorithm": "GIVP-full",
                    "seed": 1,
                    "fun": 2e-4,
                    "nit": 10,
                    "nfev": 100,
                    "time_s": 0.1,
                    "trace": None,
                },
                {
                    "algorithm": "GRASP-only",
                    "seed": 0,
                    "fun": 5e-3,
                    "nit": 10,
                    "nfev": 80,
                    "time_s": 0.05,
                    "trace": None,
                },
                {
                    "algorithm": "GRASP-only",
                    "seed": 1,
                    "fun": 2e-2,
                    "nit": 10,
                    "nfev": 80,
                    "time_s": 0.05,
                    "trace": None,
                },
            ]
        },
    }
    input_path = tmp_path / "results.json"
    input_path.write_text(json.dumps(results), encoding="utf-8")

    gr = _import_script("generate_report")
    exit_code = gr.main(
        [
            "--input",
            str(input_path),
            "--format",
            "markdown",
            "--no-plots",
            "--verbose",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "results_report.md").exists()
    assert not (tmp_path / "results_report.tex").exists()


@pytest.mark.slow
def test_tune_hyperparams_verbose(tmp_path: Path) -> None:
    """--verbose flag in tune_hyperparams exercises the DEBUG logging path."""
    tune = _import_script("tune_hyperparams")
    output = tmp_path / "best_config_verbose.json"
    exit_code = tune.main(
        [
            "--n-trials",
            "2",
            "--dims",
            "2",
            "--n-eval-seeds",
            "1",
            "--functions",
            "Sphere",
            "--max-iter",
            "5",
            "--time-limit",
            "3",
            "--verbose",
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    assert output.exists()
