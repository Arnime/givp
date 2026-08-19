"""Stable paths for resources owned by the standalone experiment."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def project_root() -> Path:
    """Return the experiment root from the installed editable package location."""
    package_directory = Path(str(files("synthetic_hydropower")))
    return package_directory.parent.parent


def default_config_path() -> Path:
    """Return the checked-in base configuration regardless of notebook working directory."""
    config_path = project_root() / "configs" / "base.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"default configuration is missing: {config_path}")
    return config_path


def default_output_dir() -> Path:
    """Return the checked-in local output directory regardless of notebook working directory."""
    return project_root() / "output"
