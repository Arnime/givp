# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Console benchmark report rendering."""

from __future__ import annotations

from benchmarks.reporting.models import FriedmanRow, SummaryRow, WilcoxonRow


def _fmt_mean_std(mean: float, std: float) -> str:
    """Format mean ± std in consistent scientific notation."""
    return f"{mean:.4e} ± {std:.4e}"


def _sig_marker(sig_raw: bool, sig_holm: bool) -> str:
    """Return significance marker prioritizing Holm-corrected significance."""
    if sig_holm:
        return "*H"
    if sig_raw:
        return "*"
    return "-"


def _pvalue_display(
    fn_name: str,
    algorithm: str,
    pval_idx: dict[tuple[str, str], float],
    ref_label: str,
) -> str:
    """Return display string for p-value if present, otherwise reference label."""
    key = (fn_name, algorithm)
    if key in pval_idx:
        return f"{pval_idx[key]:.4f}"
    return ref_label


def _console_function_rows(
    fn_name: str,
    summary: list[SummaryRow],
    pval_idx: dict[tuple[str, str], float],
    sig_idx: dict[tuple[str, str], bool],
    holm_p_idx: dict[tuple[str, str], float],
    holm_sig_idx: dict[tuple[str, str], bool],
    col: int,
) -> None:
    """Print one function block in the console summary."""
    print(f"  --- {fn_name} ---")
    print(
        f"  {'Algorithm':<{col}} {'Mean':>14} {'Std':>14} "
        f"{'Best':>14} {'Median':>14} {'p':>8} {'p(Holm)':>10} {'Sig':>5}"
    )
    print("  " + "-" * (col + 14 * 4 + 8 + 10 + 5 + 8))
    for row in (r for r in summary if r.function == fn_name):
        key = (fn_name, row.algorithm)
        pval_str_raw = _pvalue_display(fn_name, row.algorithm, pval_idx, "  ref")
        pval_str_holm = _pvalue_display(fn_name, row.algorithm, holm_p_idx, "  ref")
        sig_str = _sig_marker(sig_idx.get(key, False), holm_sig_idx.get(key, False))
        print(
            f"  {row.algorithm:<{col}} "
            f"{row.mean:>14.4e} {row.std:>14.4e} "
            f"{row.best:>14.4e} {row.median:>14.4e} "
            f"{pval_str_raw:>8} {pval_str_holm:>10} {sig_str:>5}"
        )
    print()


def _console_friedman_rows(friedman: list[FriedmanRow], col: int) -> None:
    """Print Friedman omnibus section in console output."""
    if not friedman:
        return
    print("  --- Friedman Omnibus (per function) ---")
    print(
        f"  {'Function':<{col}} {'Blocks':>8} {'k':>4} {'chi2':>10} {'p-value':>10} {'Sig':>5}"
    )
    print("  " + "-" * (col + 8 + 4 + 10 + 10 + 5 + 10))
    for row in friedman:
        sig_str = "*" if row.significant else "-"
        print(
            f"  {row.function:<{col}} {row.n_blocks:>8d} {row.n_algorithms:>4d} "
            f"{row.stat:>10.4f} {row.pvalue:>10.4f} {sig_str:>5}"
        )
    print()


def print_console_summary(
    summary: list[SummaryRow],
    wilcoxon: list[WilcoxonRow],
    holm_p_idx: dict[tuple[str, str], float] | None = None,
    holm_sig_idx: dict[tuple[str, str], bool] | None = None,
    friedman: list[FriedmanRow] | None = None,
) -> None:
    """Print a human-readable summary table to stdout."""
    holm_p_idx = holm_p_idx or {}
    holm_sig_idx = holm_sig_idx or {}
    pval_idx: dict[tuple[str, str], float] = {
        (r.function, r.algorithm): r.pvalue for r in wilcoxon
    }
    sig_idx: dict[tuple[str, str], bool] = {
        (r.function, r.algorithm): r.significant for r in wilcoxon
    }

    functions = list(dict.fromkeys(r.function for r in summary))
    col = 16

    print()
    for fn_name in functions:
        _console_function_rows(
            fn_name,
            summary,
            pval_idx,
            sig_idx,
            holm_p_idx,
            holm_sig_idx,
            col,
        )

    _console_friedman_rows(friedman or [], col)
