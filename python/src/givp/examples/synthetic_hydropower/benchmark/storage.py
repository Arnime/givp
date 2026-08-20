"""Atomic persistence helpers for benchmark artifacts."""

import json
from pathlib import Path

import pandas as pd


def _write_csv_atomic(dataframe: pd.DataFrame, path: Path) -> None:
    """Write a CSV through a temporary file to avoid partial artifacts."""
    temporary_path = path.with_suffix(".tmp")
    dataframe.to_csv(temporary_path, index=False)
    temporary_path.replace(path)


def _write_json_atomic(payload: object, path: Path) -> None:
    """Write JSON through a temporary file to avoid partial artifacts."""
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary_path.replace(path)
