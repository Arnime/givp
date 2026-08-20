"""Stable paths for resources owned by the synthetic hydropower example."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

_PACKAGE_NAME = "givp.examples.synthetic_hydropower"


def project_root() -> Path:
    """Return the experiment checkout root for editable notebook execution."""
    package_directory = Path(str(files(_PACKAGE_NAME)))
    repository_root = package_directory.parents[4]
    experiment_root = repository_root / "experiments" / "synthetic_hydropower"
    if not experiment_root.is_dir():
        raise RuntimeError(
            "the default output directory is available only from the GIVP source checkout; "
            "pass an explicit output directory when using an installed package"
        )
    return experiment_root


def default_config_path() -> Path:
    """
    Return the checked-in base configuration regardless of notebook working directory.
    """
    config_resource = files(_PACKAGE_NAME).joinpath("configs").joinpath("base.json")
    config_path = Path(str(config_resource))
    if not config_path.is_file():
        raise FileNotFoundError(f"default configuration is missing: {config_path}")
    return config_path


def default_output_dir() -> Path:
    """
    Return the checked-in local output directory regardless of notebook working directory.
    """
    return project_root() / "output"
