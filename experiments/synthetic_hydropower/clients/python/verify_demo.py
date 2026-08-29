"""Validate the language-neutral summary emitted by an optimisation demo."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


def _read_summary(path: Path) -> dict[str, Any]:
    """Return the last JSON object written by a demo command."""
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError(f"no JSON summary found in {path}")


def main(path: Path) -> None:
    """Check canonical re-evaluation and baseline improvement invariants."""
    summary = _read_summary(path)
    required = ("baseline_objective", "optimizer_objective", "objective", "energy_mwh")
    values = {name: summary.get(name) for name in required}
    if not all(isinstance(value, int | float) and math.isfinite(value) for value in values.values()):
        raise ValueError("demo summary contains a missing or non-finite metric")
    baseline = float(values["baseline_objective"])
    optimized = float(values["objective"])
    optimizer_value = float(values["optimizer_objective"])
    if optimized > baseline + 1e-6:
        raise ValueError("optimisation did not improve the all-off baseline")
    if not math.isclose(optimized, optimizer_value, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("final worker re-evaluation differs from the optimiser objective")
    print(f"{summary.get('language', 'unknown')}: canonical optimisation summary verified")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
