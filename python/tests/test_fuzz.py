# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Tests for the backend-independent Python fuzz target."""

from __future__ import annotations

import struct

import pytest

from fuzz import atheris as atheris_target
from fuzz import fuzz_bytes, run_case
from fuzz.decoder import decode_case


def test_decode_case_rejects_short_input() -> None:
    """Inputs without a complete header are ignored."""
    assert decode_case(b"\x00\x00") is None


def test_decode_case_returns_bounds_and_direction() -> None:
    """A finite float pair produces one minimization bound."""
    data = bytes((0, 0)) + struct.pack("dd", -2.0, 4.0)
    assert decode_case(data) == ([(-2.0, 2.0)], "minimize")


def test_fuzz_bytes_ignores_invalid_input() -> None:
    """Invalid byte streams do not reach the optimizer."""
    fuzz_bytes(b"invalid")


def test_run_case_returns_finite_result() -> None:
    """A valid case satisfies the shared target assertions."""
    run_case([(-2.0, 2.0)], "minimize")


def test_atheris_backend_reports_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Atheris entry point remains importable outside Linux."""
    monkeypatch.setattr(atheris_target.platform, "system", lambda: "Windows")
    with pytest.raises(RuntimeError, match="only on Linux"):
        atheris_target.main()
