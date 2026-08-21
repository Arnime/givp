# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Pure-utility helpers shared across the ``givp.core`` submodules.

This module deliberately has zero internal dependencies (other than ``numpy``)
so it can be imported from every other ``core`` submodule without risking
circular imports.
"""

from __future__ import annotations

import logging
import secrets
import time as _time_mod
from collections.abc import Callable
from contextvars import ContextVar
from typing import Literal, Protocol

import numpy as np

EvaluatorFn = Callable[[np.ndarray], float]
PathRelinkStrategy = Literal[
    "bidirectional",
    "forward",
    "backward",
    "randomized",
    "random",
]

logger = logging.getLogger("givp.core")
_VERBOSE_HANDLER_ATTACHED: list[bool] = [False]

_INTEGER_SPLIT: ContextVar[int | None] = ContextVar("givp_integer_split", default=None)
_GROUP_SIZE: ContextVar[int | None] = ContextVar("givp_group_size", default=None)
_MASTER_SEED_SEQ: ContextVar[np.random.SeedSequence | None] = ContextVar(
    "givp_master_seed_seq", default=None
)


def _ensure_verbose_handler() -> None:
    """Attach a stdout handler to the ``givp.core`` logger so verbose=True
    actually prints to the console even when the application has not
    configured ``logging`` itself.

    Idempotent: safe to call repeatedly; only the first call adds a handler.
    """
    if _VERBOSE_HANDLER_ATTACHED[0]:
        logger.setLevel(logging.INFO)
        return
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("[givp] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _VERBOSE_HANDLER_ATTACHED[0] = True


def _set_seed(seed: int | None) -> None:
    """Pin the master :class:`SeedSequence` used to spawn per-call generators.

    Pass ``None`` to restore the default non-deterministic behaviour. When
    a seed is pinned, every subsequent :func:`_new_rng` call (without an
    explicit seed) gets a deterministic, statistically independent child
    seed via :meth:`SeedSequence.spawn`.
    """
    if seed is None:
        _MASTER_SEED_SEQ.set(None)
    else:
        _MASTER_SEED_SEQ.set(np.random.SeedSequence(seed))


def _get_half(n: int) -> int:
    """Return the index where integer variables begin, given vector length ``n``."""
    split = _INTEGER_SPLIT.get()
    if split is not None and 0 <= split <= n:
        return split
    return n // 2


def _set_integer_split(split: int | None) -> None:
    """Set the integer split used by the helpers below (per ContextVar)."""
    _INTEGER_SPLIT.set(split)


def _set_group_size(size: int | None) -> None:
    """Set the number of steps per group for the group/block neighbourhoods."""
    _GROUP_SIZE.set(size)


def _get_group_size() -> int | None:
    """Return the configured group size, if any."""
    return _GROUP_SIZE.get()


def _new_rng(seed: int | None = None) -> np.random.Generator:
    """Create a RNG using an explicit seed to satisfy static-analysis rules.

    When a master seed has been pinned via :func:`_set_seed`, an independent
    child :class:`SeedSequence` is spawned from the master and used to seed
    the new generator. Otherwise OS entropy is used.
    """
    if seed is not None:
        return np.random.default_rng(seed)
    master = _MASTER_SEED_SEQ.get()
    if master is not None:
        (child,) = master.spawn(1)
        return np.random.default_rng(child)
    return np.random.default_rng(secrets.randbits(64))


def _expired(deadline: float) -> bool:
    """Retorna True se o deadline foi atingido (0 = sem limite).

    Uses :func:`time.monotonic` so suspended/sleeping systems do not skew
    the deadline.
    """
    return deadline > 0 and _time_mod.monotonic() >= deadline


def _safe_evaluate(evaluator: EvaluatorFn, candidate: np.ndarray) -> float:
    """Call the user evaluator and coerce the result to a finite float.

    Returns ``np.inf`` on any failure (treated as an infeasible candidate).
    Logs a warning with traceback so silent bugs in the evaluator are visible.
    """
    try:
        cost = float(evaluator(candidate))
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning(
            "evaluator raised an exception; treating candidate as infeasible",
            exc_info=True,
        )
        return np.inf
    if not np.isfinite(cost):
        return np.inf
    return cost


class _CoreConfigProto(Protocol):
    """Structural protocol satisfied by ``givp.config.GIVPConfig`` and any
    compatible config object passed to core functions.

    Core functions accept any object with these attributes, so ``GIVPConfig``
    can be passed directly without copying field values into a separate class.
    """

    max_iterations: int
    alpha: float
    vnd_iterations: int
    ils_iterations: int
    perturbation_strength: int
    use_elite_pool: bool
    elite_size: int
    path_relink_frequency: int
    path_relink_strategy: PathRelinkStrategy
    adaptive_alpha: bool
    alpha_min: float
    alpha_max: float
    num_candidates_per_step: int
    use_cache: bool
    cache_size: int
    early_stop_threshold: int
    use_convergence_monitor: bool
    n_workers: int
    time_limit: float
    integer_split: int | None
    group_size: int | None
