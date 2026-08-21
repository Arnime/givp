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


def validate_cli_paths(config_path: Path, output_dir: Path) -> None:
    """Validate CLI paths against the files owned by the benchmark checkout.

    The console command is intended to reproduce the checked-in benchmark.  It
    therefore accepts only its packaged configuration and its dedicated output
    directory.  Callers that need custom paths can use the Python API directly.

    Args:
        config_path: Configuration path received by the command-line parser.
        output_dir: Output directory received by the command-line parser.

    Raises:
        ValueError: If either supplied path is outside the CLI allowlist.
    """
    trusted_config = default_config_path().resolve(strict=True)
    benchmark_output = default_output_dir()
    if benchmark_output.is_symlink():
        raise ValueError("the benchmark output directory must not be a symbolic link")
    trusted_output = benchmark_output.resolve(strict=False)
    supplied_config = config_path.expanduser().resolve(strict=True)
    supplied_output = output_dir.expanduser().resolve(strict=False)

    if supplied_config != trusted_config:
        raise ValueError(
            "the CLI accepts only the packaged synthetic hydropower base configuration"
        )
    if supplied_output != trusted_output:
        raise ValueError(
            "the CLI writes only to the synthetic hydropower benchmark output directory"
        )
