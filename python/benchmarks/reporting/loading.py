# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Benchmark result loading and normalization."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from benchmarks.reporting.models import RunRecord, SummaryRow


def _parse_records_from_records(raw: dict) -> list[RunRecord]:
    records: list[RunRecord] = []
    for fn_name, fn_recs in raw["records"].items():
        for r in fn_recs:
            records.append(
                RunRecord(
                    algorithm=r["algorithm"],
                    function=fn_name,
                    seed=r["seed"],
                    fun=r["fun"],
                    nit=r.get("nit", 0),
                    nfev=r.get("nfev", 0),
                    time_s=r.get("time_s", 0.0),
                    trace=r.get("trace"),
                )
            )
    return records


def _parse_records_from_runs(raw: dict) -> list[RunRecord]:
    return [
        RunRecord(
            algorithm=r["algorithm"],
            function=r["function"],
            seed=r["seed"],
            fun=r["fun"],
            nit=r.get("nit", 0),
            nfev=r.get("nfev", 0),
            time_s=r.get("time_s", 0.0),
            trace=r.get("trace"),
        )
        for r in raw["runs"]
    ]


def _synthesize_summary(records: list[RunRecord]) -> list[SummaryRow]:
    grouped: dict[tuple[str, str], list[RunRecord]] = {}
    for record in records:
        grouped.setdefault((record.function, record.algorithm), []).append(record)

    summary = []
    for (function, algorithm), group in sorted(grouped.items()):
        fun_values = np.asarray([record.fun for record in group], dtype=float)
        nfev_values = np.asarray([record.nfev for record in group], dtype=float)
        summary.append(
            SummaryRow(
                function=function,
                algorithm=algorithm,
                n_runs=len(group),
                mean=float(fun_values.mean()),
                std=float(fun_values.std(ddof=0)),
                best=float(fun_values.min()),
                median=float(np.median(fun_values)),
                worst=float(fun_values.max()),
                nfev_mean=float(nfev_values.mean()) if len(nfev_values) else 0.0,
            )
        )
    return summary


def load_results(path: Path) -> tuple[dict, list[RunRecord], list[SummaryRow]]:
    """Parse the JSON output of the comparison benchmark.

    Returns
    -------
    (metadata, records, summary)
        - metadata : dict with experimental settings
        - records  : flat list of RunRecord (one per run)
        - summary  : pre-computed statistics per (function, algorithm)
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = raw["metadata"]

    if "records" in raw:
        records = _parse_records_from_records(raw)
    elif "runs" in raw:
        records = _parse_records_from_runs(raw)
    else:
        msg = "Unsupported benchmark schema: expected 'records' or 'runs'"
        raise KeyError(msg)

    summary_data = raw.get("summary", [])
    if summary_data:
        summary = [SummaryRow(**row) for row in summary_data]
    else:
        summary = _synthesize_summary(records)

    return meta, records, summary
