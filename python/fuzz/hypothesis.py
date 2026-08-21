# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Cross-platform Hypothesis fuzz target."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from fuzz.target import run_case

BOUNDS = st.lists(
    st.tuples(
        st.floats(
            min_value=-50.0,
            max_value=50.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        st.floats(
            min_value=1e-3,
            max_value=10.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    ),
    min_size=1,
    max_size=6,
).map(lambda pairs: [(lower, lower + width) for lower, width in pairs])


def _fuzz_case(bounds: list[tuple[float, float]], direction: str) -> None:
    """Exercise GIVP with generated bounds and both directions."""
    run_case(bounds, direction)


fuzz = cast(
    Callable[[], None],
    settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )(
        given(bounds=BOUNDS, direction=st.sampled_from(["minimize", "maximize"]))(
            _fuzz_case
        )
    ),
)


def main() -> None:
    """Run the Hypothesis target."""
    fuzz()
