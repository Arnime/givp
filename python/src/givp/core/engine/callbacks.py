"""Protected callbacks and optimization-run logging."""

from collections.abc import Callable

import numpy as np

from givp.core.cache import EvaluationCache
from givp.core.helpers import (
    _CoreConfigProto,
    _ensure_verbose_handler,
    _time_mod,
    logger,
)


def _safe_iteration_callback(
    callback: Callable | None,
    iter_idx: int,
    benefit: float,
    sol: np.ndarray,
    verbose: bool,
) -> None:
    """Invoke an iteration callback without interrupting optimization."""
    if callback is None:
        return
    try:
        callback(iter_idx, benefit, sol)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "iteration_callback raised at iter %d; continuing",
            iter_idx,
            exc_info=True,
        )
        if verbose:
            logger.info("iteration_callback error at iter %d (see warning above)", iter_idx)


def _print_iteration_status(
    verbose: bool,
    iteration: int,
    max_iterations: int,
    current_cost: float,
    best_cost: float,
    original_best: float,
    *,
    alpha: float | None = None,
    stagnation: int = 0,
    elite_size: int = 0,
    start_time: float | None = None,
) -> None:
    """Log one concise iteration status line."""
    if not verbose:
        return
    marker = "*" if current_cost < original_best else " "
    elapsed = _time_mod.monotonic() - start_time if start_time is not None else 0.0
    alpha_text = f"{alpha:.3f}" if alpha is not None else "  -  "
    logger.info(
        "%s iter %3d/%d | cur=%12.4f | best=%12.4f | alpha=%s "
        "| stag=%3d | elite=%2d | t=%6.2fs",
        marker, iteration + 1, max_iterations, current_cost, best_cost,
        alpha_text, stagnation, elite_size, elapsed,
    )


def _print_run_header(verbose: bool, num_vars: int, config: _CoreConfigProto) -> None:
    """Log the run configuration."""
    if not verbose:
        return
    _ensure_verbose_handler()
    logger.info(
        "GRASP-ILS-VND-PR start | n=%d | iters=%d | alpha=[%.3f, %.3f] "
        "| elite=%d | time_limit=%s",
        num_vars, config.max_iterations,
        config.alpha_min if config.adaptive_alpha else config.alpha,
        config.alpha_max if config.adaptive_alpha else config.alpha,
        config.elite_size if config.use_elite_pool else 0,
        f"{config.time_limit:.1f}s" if config.time_limit > 0 else "unlimited",
    )


def _print_run_footer(
    verbose: bool, best_cost: float, stagnation: int, start_time: float
) -> None:
    """Log the final run state."""
    if verbose:
        logger.info(
            "GRASP-ILS-VND-PR end   | best=%.4f | stagnation=%d | t=%.2fs",
            best_cost, stagnation, _time_mod.monotonic() - start_time,
        )


def _print_cache_stats(cache: EvaluationCache | None, verbose: bool) -> None:
    """Log evaluation-cache statistics."""
    if verbose and cache is not None:
        stats = cache.stats()
        logger.info(
            "Cache Stats: %d hits, %d misses, taxa=%.1f%%, tamanho=%d",
            stats["hits"], stats["misses"], stats["hit_rate"], stats["size"],
        )
