"""Validation helpers for optimizer bounds and warm-start candidates."""

from __future__ import annotations

import numpy as np

from givp.exceptions import InvalidBoundsError, InvalidInitialGuessError


def _validate_bounds_and_initial(
    lower_arr: np.ndarray,
    upper_arr: np.ndarray,
    initial_guess: np.ndarray | None,
    num_vars: int,
) -> None:
    """Validate bounds and an optional initial candidate."""
    if lower_arr.shape[0] != num_vars or upper_arr.shape[0] != num_vars:
        raise InvalidBoundsError(
            f"lower (len={lower_arr.shape[0]}) and upper (len={upper_arr.shape[0]}) "
            f"must both have length num_vars={num_vars}"
        )
    if initial_guess is not None:
        if initial_guess.shape[0] != num_vars:
            raise InvalidInitialGuessError(
                f"initial_guess has length {initial_guess.shape[0]}, expected {num_vars}"
            )
        if np.any(initial_guess <= lower_arr) or np.any(initial_guess >= upper_arr):
            bad = np.nonzero(
                (initial_guess <= lower_arr) | (initial_guess >= upper_arr)
            )[0]
            raise InvalidInitialGuessError(
                "initial_guess values must be strictly between lower and upper; "
                f"violating indices: {bad.tolist()[:10]}"
            )


def _prepare_bounds(
    lower: list[float] | None,
    upper: list[float] | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Validate public bounds and convert them to NumPy arrays."""
    if lower is None or upper is None:
        raise InvalidBoundsError("lower and upper bounds must be provided")
    lower_arr = np.array(lower, dtype=float)
    upper_arr = np.array(upper, dtype=float)
    if lower_arr.shape != upper_arr.shape:
        raise InvalidBoundsError(
            f"lower (shape={lower_arr.shape}) and upper "
            f"(shape={upper_arr.shape}) must have the same shape"
        )
    if np.any(upper_arr <= lower_arr):
        bad = np.nonzero(upper_arr <= lower_arr)[0]
        raise InvalidBoundsError(
            "each element of upper must be strictly greater than lower; "
            f"violating indices: {bad.tolist()[:10]}"
        )
    return lower_arr, upper_arr
