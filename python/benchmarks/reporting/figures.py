# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Benchmark report figures."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from benchmarks.reporting.models import RunRecord

matplotlib.use("Agg")

_MPL_OK = True
_log = logging.getLogger(__name__)


def plot_boxplot(
    records: list[RunRecord],
    meta: dict,
    output_path: Path,
) -> None:
    """Save a boxplot figure: objective value distribution per function × algorithm."""
    if not _MPL_OK:
        _log.warning("[warning] matplotlib not installed — boxplot skipped.")
        return

    functions = meta.get("functions", sorted({r.function for r in records}))
    algorithms = meta.get("algorithms", sorted({r.algorithm for r in records}))
    dims = meta.get("dims", "?")
    n_runs = meta.get("n_runs", "?")

    palette = [
        "#2196F3",
        "#FF9800",
        "#4CAF50",
        "#F44336",
        "#9C27B0",
        "#00BCD4",
        "#FF5722",
        "#607D8B",
    ]
    algo_colors = {a: palette[i % len(palette)] for i, a in enumerate(algorithms)}

    fig, axes = plt.subplots(
        1,
        len(functions),
        figsize=(max(4 * len(functions), 8), 5),
        sharey=False,
    )
    if len(functions) == 1:
        axes = [axes]

    for ax, fn_name in zip(axes, functions, strict=True):
        data = [
            [r.fun for r in records if r.function == fn_name and r.algorithm == a]
            for a in algorithms
        ]
        bp = ax.boxplot(
            data,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5},
            flierprops={"marker": ".", "markersize": 4, "alpha": 0.5},
        )
        ax.set_xticks(range(1, len(algorithms) + 1))
        ax.set_xticklabels(algorithms)
        for patch, a in zip(bp["boxes"], algorithms, strict=True):
            patch.set_facecolor(algo_colors[a])
            patch.set_alpha(0.75)

        ax.set_title(fn_name, fontsize=11, fontweight="bold")
        ax.set_ylabel("Objective value", fontsize=9)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8)
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter(useMathText=True))
        ax.grid(axis="y", linestyle="--", alpha=0.35)

    fig.suptitle(
        f"Objective value distribution — n={dims}, {n_runs} runs per cell",
        fontsize=12,
        fontweight="bold",
        y=1.01,
    )
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _log.info("  Boxplot saved \u2192 %s", output_path)


def plot_convergence(
    records: list[RunRecord],
    meta: dict,
    output_path: Path,
    trace_seed: int = 0,
) -> None:
    """Save convergence traces (best-so-far per iteration) for one seed.

    Only runs with a non-None `trace` list are plotted.  If the JSON was
    generated without ``--traces``, this function prints a warning and exits.
    """
    if not _MPL_OK:
        _log.warning("[warning] matplotlib not installed — convergence plot skipped.")
        return

    has_traces = any(r.trace is not None for r in records)
    if not has_traces:
        _log.warning(
            "[warning] No convergence traces in the JSON.  "
            "Re-run benchmarks.comparison with --traces to capture them."
        )
        return

    functions = meta.get("functions", sorted({r.function for r in records}))
    algorithms = meta.get("algorithms", sorted({r.algorithm for r in records}))

    palette = [
        "#2196F3",
        "#FF9800",
        "#4CAF50",
        "#F44336",
        "#9C27B0",
        "#00BCD4",
        "#FF5722",
        "#607D8B",
    ]
    algo_colors = {a: palette[i % len(palette)] for i, a in enumerate(algorithms)}

    fig, axes = plt.subplots(
        1,
        len(functions),
        figsize=(max(4 * len(functions), 8), 4),
        sharey=False,
    )
    if len(functions) == 1:
        axes = [axes]

    for ax, fn_name in zip(axes, functions, strict=True):
        plotted_any = False
        for a in algorithms:
            matching = [
                r
                for r in records
                if r.function == fn_name
                and r.algorithm == a
                and r.seed == trace_seed
                and r.trace is not None
            ]
            if not matching:
                continue
            trace = matching[0].trace
            assert trace is not None  # narrowing
            ax.plot(
                range(1, len(trace) + 1),
                trace,
                label=a,
                color=algo_colors[a],
                linewidth=1.6,
            )
            plotted_any = True

        ax.set_title(fn_name, fontsize=11, fontweight="bold")
        ax.set_xlabel("Iteration", fontsize=9)
        ax.set_ylabel("Best objective (symlog)", fontsize=9)
        ax.set_yscale("symlog", linthresh=1e-6)
        if plotted_any:
            ax.legend(fontsize=8)
        ax.grid(linestyle="--", alpha=0.35)

    fig.suptitle(
        f"Convergence traces — seed={trace_seed}",
        fontsize=12,
        fontweight="bold",
        y=1.01,
    )
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _log.info("  Convergence plot saved → %s", output_path)
