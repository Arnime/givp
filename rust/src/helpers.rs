// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

use rand::Rng;
use rand_chacha::ChaCha8Rng;
use std::time::Instant;

/// Get the integer split index: defaults to num_vars / 2.
pub(crate) fn get_half(num_vars: usize, integer_split: Option<usize>) -> usize {
    integer_split.unwrap_or(num_vars / 2)
}

/// Check if the deadline has passed.
pub(crate) fn expired(deadline: Option<Instant>) -> bool {
    match deadline {
        Some(d) => Instant::now() >= d,
        None => false,
    }
}

/// Safely evaluate the objective function, returning `f64::INFINITY` on panic.
pub(crate) fn safe_evaluate<F>(func: &F, candidate: &[f64]) -> f64
where
    F: Fn(&[f64]) -> f64,
{
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| func(candidate)));
    match result {
        Ok(v) if v.is_finite() => v,
        _ => f64::INFINITY,
    }
}

/// Create a seeded RNG, optionally from a parent.
pub(crate) fn new_rng(seed: Option<u64>) -> ChaCha8Rng {
    use rand::SeedableRng;
    match seed {
        Some(s) => ChaCha8Rng::seed_from_u64(s),
        None => ChaCha8Rng::from_os_rng(),
    }
}

/// Spawn a child RNG from a parent.
pub(crate) fn child_rng(parent: &mut ChaCha8Rng) -> ChaCha8Rng {
    use rand::SeedableRng;
    let seed: u64 = parent.random();
    ChaCha8Rng::seed_from_u64(seed)
}

/// Round integer-portion variables to the nearest integer.
pub(crate) fn normalize_integer_tail(solution: &mut [f64], half: usize) {
    for v in solution[half..].iter_mut() {
        *v = v.round();
    }
}

/// Clamp a value to bounds.
pub(crate) fn clamp(v: f64, lo: f64, hi: f64) -> f64 {
    v.max(lo).min(hi)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};

    #[test]
    fn test_expired_none_and_past_deadline() {
        assert!(!expired(None));
        let past = Some(Instant::now() - Duration::from_millis(1));
        assert!(expired(past));
    }

    #[test]
    fn test_safe_evaluate_nan_and_panic_return_infinity() {
        let nan_fn = |_x: &[f64]| f64::NAN;
        let panic_fn = |_x: &[f64]| -> f64 { panic!("boom") };

        assert!(safe_evaluate(&nan_fn, &[1.0]).is_infinite());
        assert!(safe_evaluate(&panic_fn, &[1.0]).is_infinite());
    }

    #[test]
    fn test_safe_evaluate_finite_value() {
        let sphere = |x: &[f64]| x.iter().map(|v| v * v).sum::<f64>();
        let v = safe_evaluate(&sphere, &[2.0, 1.0]);
        assert!((v - 5.0).abs() < 1e-10);
    }
}
