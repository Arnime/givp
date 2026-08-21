# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Non-parametric benchmark statistics."""

from __future__ import annotations

import logging

import numpy as np
from scipy import stats as _scipy_stats  # type: ignore[import-untyped]

from benchmarks.reporting.models import FriedmanRow, RunRecord, WilcoxonRow

_SCIPY_OK = True
_log = logging.getLogger(__name__)


def wilcoxon_table(
    records: list[RunRecord],
    reference: str,
    alpha: float = 0.05,
) -> list[WilcoxonRow]:
    """Compute Wilcoxon signed-rank tests for each algorithm vs *reference*.

    Only algorithms that share the same seeds as *reference* are compared
    (matched-pairs requirement).  The alternative hypothesis is two-sided:
    the two algorithms produce different objective values.

    Parameters
    ----------
    records:
        Raw per-run records (all algorithms).
    reference:
        Algorithm name to use as the baseline in pairwise comparisons.
    alpha:
        Significance level (default: 0.05).

    Returns
    -------
    list[WilcoxonRow]
        One row per (challenger, function) pair.  Excludes reference vs itself.
    """
    if not _SCIPY_OK:
        _log.warning(
            "[warning] scipy not installed — Wilcoxon tests skipped.\n"
            "          Run:  pip install scipy"
        )
        return []

    # Group values by (function, algorithm, seed) for matched pairs
    idx: dict[tuple[str, str, int], float] = {}
    for r in records:
        idx[(r.function, r.algorithm, r.seed)] = r.fun

    functions = sorted({r.function for r in records})
    algorithms = sorted({r.algorithm for r in records})
    challengers = [a for a in algorithms if a != reference]

    rows: list[WilcoxonRow] = []
    for fn_name in functions:
        ref_seeds = sorted(
            s for (fn, algo, s) in idx if fn == fn_name and algo == reference
        )
        if not ref_seeds:
            continue

        for challenger in challengers:
            ref_vals = [
                idx[(fn_name, reference, s)]
                for s in ref_seeds
                if (fn_name, challenger, s) in idx
            ]
            chal_vals = [
                idx[(fn_name, challenger, s)]
                for s in ref_seeds
                if (fn_name, challenger, s) in idx
            ]
            if len(ref_vals) < 2:
                continue

            a = np.asarray(ref_vals, dtype=float)
            b = np.asarray(chal_vals, dtype=float)

            # scipy ≥1.7 supports zero_method="wilcox" and nan_policy
            # Unpack as tuple to avoid Pylance attribute-access false positives
            # on the conditionally-imported _scipy_stats module.
            _stat, _pvalue = _scipy_stats.wilcoxon(a, b, alternative="two-sided")
            stat = float(_stat)  # type: ignore[arg-type]  # scipy stubs unavailable
            pvalue = float(_pvalue)  # type: ignore[arg-type]  # scipy stubs unavailable
            n = len(a)
            # Rank-biserial correlation: effect size for Wilcoxon
            effect_r = float(1.0 - (2.0 * stat) / (n * (n + 1) / 2.0))

            rows.append(
                WilcoxonRow(
                    function=fn_name,
                    algorithm=challenger,
                    reference=reference,
                    stat=stat,
                    pvalue=pvalue,
                    effect_r=effect_r,
                    significant=pvalue < alpha,
                )
            )

    return rows


def holm_bonferroni_correction(
    rows: list[WilcoxonRow],
    alpha: float = 0.05,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], bool]]:
    """Apply Holm-Bonferroni correction to Wilcoxon p-values.

    Correction is applied over the full family of Wilcoxon comparisons in the
    current report. Returns indexes keyed by (function, algorithm).
    """
    if not rows:
        return {}, {}

    order = sorted(range(len(rows)), key=lambda i: rows[i].pvalue)
    m = len(rows)
    adjusted = [1.0] * m
    running_max = 0.0

    for rank, idx in enumerate(order, start=1):
        factor = m - rank + 1
        adj = min(1.0, rows[idx].pvalue * factor)
        running_max = max(running_max, adj)
        adjusted[idx] = running_max

    p_adj_idx: dict[tuple[str, str], float] = {}
    sig_adj_idx: dict[tuple[str, str], bool] = {}
    for i, row in enumerate(rows):
        key = (row.function, row.algorithm)
        p_adj_idx[key] = adjusted[i]
        sig_adj_idx[key] = adjusted[i] < alpha

    return p_adj_idx, sig_adj_idx


def friedman_table(
    records: list[RunRecord],
    alpha: float = 0.05,
) -> list[FriedmanRow]:
    """Compute Friedman omnibus test across algorithms for each function."""
    if not _SCIPY_OK:
        _log.warning(
            "[warning] scipy not installed — Friedman tests skipped.\n"
            "          Run:  pip install scipy"
        )
        return []

    idx: dict[tuple[str, str, int], float] = {}
    for r in records:
        idx[(r.function, r.algorithm, r.seed)] = r.fun

    functions = sorted({r.function for r in records})
    algorithms = sorted({r.algorithm for r in records})
    out: list[FriedmanRow] = []

    for fn_name in functions:
        seeds_by_algo: dict[str, set[int]] = {
            algo: {s for (fn, a, s) in idx if fn == fn_name and a == algo}
            for algo in algorithms
        }
        if not seeds_by_algo:
            continue

        common_seeds = (
            set.intersection(*seeds_by_algo.values()) if seeds_by_algo else set()
        )
        if len(common_seeds) < 2 or len(algorithms) < 3:
            continue

        common_seed_list = sorted(common_seeds)
        samples = [
            np.asarray([idx[(fn_name, algo, s)] for s in common_seed_list], dtype=float)
            for algo in algorithms
        ]
        _stat, _pvalue = _scipy_stats.friedmanchisquare(*samples)
        stat = float(_stat)  # type: ignore[arg-type]
        pvalue = float(_pvalue)  # type: ignore[arg-type]

        rank_matrix = np.vstack(
            [
                _scipy_stats.rankdata(
                    [idx[(fn_name, algo, s)] for algo in algorithms],
                    method="average",
                )
                for s in common_seed_list
            ]
        )
        mean_ranks = {
            algo: float(rank_matrix[:, i].mean()) for i, algo in enumerate(algorithms)
        }

        out.append(
            FriedmanRow(
                function=fn_name,
                n_blocks=len(common_seed_list),
                n_algorithms=len(algorithms),
                stat=stat,
                pvalue=pvalue,
                significant=pvalue < alpha,
                mean_ranks=mean_ranks,
            )
        )

    return out
