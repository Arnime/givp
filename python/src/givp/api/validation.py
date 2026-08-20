# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Input normalization and validation for the public optimizer API."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from givp.api.types import BoundsLike, Direction
from givp.core.engine.validation import _validate_bounds_and_initial
from givp.exceptions import InvalidInitialGuessError


def _normalize_initial_guesses(
    initial_guess: Sequence[float] | None,
    initial_guesses: Sequence[Sequence[float]] | None,
    lower: list[float],
    upper: list[float],
    num_vars: int,
) -> list[list[float]] | None:
    """Validate and deduplicate warm-start candidates."""
    normalized: list[np.ndarray] = []

    def add_candidate(candidate: Sequence[float], label: str) -> None:
        candidate_arr = np.asarray(candidate, dtype=float)
        _validate_bounds_and_initial(
            np.asarray(lower, dtype=float),
            np.asarray(upper, dtype=float),
            candidate_arr,
            num_vars,
        )
        for existing in normalized:
            if np.array_equal(candidate_arr, existing):
                raise InvalidInitialGuessError(
                    f"{label} duplicates an existing warm-start candidate"
                )
        normalized.append(candidate_arr)

    if initial_guess is not None:
        add_candidate(initial_guess, "initial_guess")

    if initial_guesses is not None:
        if len(initial_guesses) == 0:
            raise InvalidInitialGuessError(
                "initial_guesses must contain at least one candidate"
            )
        for idx, candidate in enumerate(initial_guesses):
            add_candidate(candidate, f"initial_guesses[{idx}]")

    if not normalized:
        return None
    return [candidate.tolist() for candidate in normalized]


def _normalize_bounds(
    bounds: BoundsLike, num_vars: int | None
) -> tuple[list[float], list[float], int]:
    """Normalize supported bounds representations into lower and upper vectors."""
    if bounds is None:
        raise ValueError("bounds must be provided")

    if (
        isinstance(bounds, tuple)
        and len(bounds) == 2
        and isinstance(bounds[0], Iterable)
        and not isinstance(bounds[0], (str, bytes))
        and isinstance(bounds[1], Iterable)
        and not isinstance(bounds[1], (str, bytes))
        and len(list(bounds[0])) == len(list(bounds[1]))
        and (num_vars is None or len(list(bounds[0])) == num_vars)
    ):
        lower = [float(value) for value in bounds[0]]
        upper = [float(value) for value in bounds[1]]
    else:
        pairs = [(float(bound[0]), float(bound[1])) for bound in bounds]
        lower = [low for low, _ in pairs]
        upper = [high for _, high in pairs]

    inferred_num_vars = len(lower)
    if num_vars is not None and inferred_num_vars != num_vars:
        raise ValueError(
            f"bounds length ({inferred_num_vars}) does not match num_vars ({num_vars})"
        )
    return lower, upper, inferred_num_vars


def _resolve_direction(
    minimize: bool | None,
    direction: str | None,
    default: Direction = "minimize",
) -> Direction:
    """Reconcile the boolean and textual optimization-direction options."""
    if direction is None:
        if minimize is None:
            return default
        return "minimize" if minimize else "maximize"
    if direction not in ("minimize", "maximize"):
        raise ValueError(
            f"direction must be 'minimize' or 'maximize', got {direction!r}"
        )
    resolved: Direction = "minimize" if direction == "minimize" else "maximize"
    if minimize is None:
        return resolved
    derived: Direction = "minimize" if minimize else "maximize"
    if resolved != derived:
        raise ValueError(
            "`minimize` and `direction` disagree: "
            f"minimize={minimize} implies '{derived}', got direction={direction!r}"
        )
    return derived
