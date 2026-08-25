# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Nox sessions: ``pip install nox`` then run ``nox`` locally to mirror CI."""

from __future__ import annotations

import nox

nox.options.sessions = ["lint", "typecheck", "tests", "docs"]
nox.options.reuse_existing_virtualenvs = True

PY_VERSIONS = ["3.10", "3.11", "3.12", "3.13", "3.14", "3.15"]
_DEV = ".[dev]"
OVERRIDE_INI = "--override-ini=addopts="


@nox.session(python=PY_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the unit test suite with coverage."""
    session.install("-e", _DEV)
    session.run("pytest", *session.posargs)


@nox.session
def integration(session: nox.Session) -> None:
    """Run cross-component execution tests without collecting coverage."""
    session.install("-e", _DEV)
    session.run(
        "pytest",
        "-m",
        "integration",
        "tests",
        "--no-cov",
        OVERRIDE_INI,
        *session.posargs,
    )


@nox.session
def properties(session: nox.Session) -> None:
    """Run property-based tests without collecting coverage."""
    session.install("-e", _DEV)
    session.run(
        "pytest",
        "-m",
        "property",
        "tests/givp/test_properties.py",
        "--no-cov",
        OVERRIDE_INI,
        "-p",
        "no:randomly",
        *session.posargs,
    )


@nox.session
def benchmark_regression(session: nox.Session) -> None:
    """Validate frozen benchmark protocols without collecting coverage."""
    session.install("-e", _DEV)
    session.run(
        "pytest",
        "-m",
        "benchmark_regression",
        "tests",
        "--no-cov",
        OVERRIDE_INI,
        *session.posargs,
    )


@nox.session
def lint(session: nox.Session) -> None:
    """Run ruff."""
    session.install("ruff>=0.6")
    session.run("ruff", "check", "src", "tests", "benchmarks", "fuzz")


@nox.session
def typecheck(session: nox.Session) -> None:
    """Run mypy."""
    session.install("-e", _DEV)
    session.run("mypy")


@nox.session
def docs(session: nox.Session) -> None:
    """Build docs in strict mode."""
    session.install("-e", ".[docs]")
    session.run("mkdocs", "build", "-f", "../mkdocs.yml", "--strict")


@nox.session
def benchmarks(session: nox.Session) -> None:
    """Run the performance benchmarks."""
    session.install("-e", _DEV)
    session.run(
        "pytest",
        "-m",
        "performance",
        "tests/benchmark/test_performance.py",
        "--benchmark-only",
        "--benchmark-autosave",
        *session.posargs,
    )


@nox.session
def audit(session: nox.Session) -> None:
    """Audit dependencies for known CVEs."""
    session.install("pip-audit>=2.7")
    session.run("pip-audit", "--strict")
