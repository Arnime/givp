// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

use crate::cache::EvaluationCache;
use crate::config::PathRelinkStrategy;
use crate::grasp::evaluate_with_cache;
use crate::helpers::expired;
use rand::Rng;
use rand_chacha::ChaCha8Rng;
use std::time::Instant;

const MAX_PR_VARS: usize = 25;

/// Best (greedy) path relinking: at each step pick the variable move with best cost.
fn path_relinking_best<F>(
    func: &F,
    source: &[f64],
    target: &[f64],
    diff_indices: &[usize],
    cache: &mut Option<EvaluationCache>,
    half: usize,
    deadline: Option<Instant>,
) -> (Vec<f64>, f64)
where
    F: Fn(&[f64]) -> f64,
{
    let mut current = source.to_vec();
    let mut best = current.clone();
    let mut best_cost = evaluate_with_cache(&current, func, cache, half);
    let mut remaining: Vec<usize> = diff_indices.to_vec();

    while !remaining.is_empty() {
        if expired(deadline) {
            break;
        }
        let mut best_idx_pos = 0;
        let mut best_move_cost = f64::INFINITY;
        let mut best_move_val = 0.0;

        for (pos, &idx) in remaining.iter().enumerate() {
            let old = current[idx];
            current[idx] = target[idx];
            let cost = evaluate_with_cache(&current, func, cache, half);
            if cost < best_move_cost {
                best_move_cost = cost;
                best_idx_pos = pos;
                best_move_val = target[idx];
            }
            current[idx] = old;
        }

        let chosen_idx = remaining.swap_remove(best_idx_pos);
        current[chosen_idx] = best_move_val;

        if best_move_cost < best_cost {
            best_cost = best_move_cost;
            best = current.clone();
        }
    }
    (best, best_cost)
}

fn directional_path_relinking<F>(
    func: &F,
    source: &[f64],
    target: &[f64],
    half: usize,
    cache: &mut Option<EvaluationCache>,
    rng: &mut ChaCha8Rng,
    deadline: Option<Instant>,
) -> (Vec<f64>, f64)
where
    F: Fn(&[f64]) -> f64,
{
    let n = source.len();
    let mut diff_indices: Vec<usize> = (0..n)
        .filter(|&i| (source[i] - target[i]).abs() > 1e-12)
        .collect();

    if diff_indices.is_empty() {
        let cost = evaluate_with_cache(source, func, cache, half);
        return (source.to_vec(), cost);
    }

    if diff_indices.len() > MAX_PR_VARS {
        diff_indices.sort_by(|&a, &b| {
            let da = (source[a] - target[a]).abs();
            let db = (source[b] - target[b]).abs();
            db.partial_cmp(&da).unwrap()
        });
        diff_indices.truncate(MAX_PR_VARS);
    }

    for i in (1..diff_indices.len()).rev() {
        let j = rng.random_range(0..=i);
        diff_indices.swap(i, j);
    }

    path_relinking_best(func, source, target, &diff_indices, cache, half, deadline)
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn apply_path_relinking_strategy<F>(
    func: &F,
    sol1: &[f64],
    sol2: &[f64],
    strategy: PathRelinkStrategy,
    half: usize,
    cache: &mut Option<EvaluationCache>,
    rng: &mut ChaCha8Rng,
    deadline: Option<Instant>,
) -> (Vec<f64>, f64)
where
    F: Fn(&[f64]) -> f64,
{
    match strategy {
        PathRelinkStrategy::Bidirectional => {
            bidirectional_path_relinking(func, sol1, sol2, half, cache, rng, deadline)
        }
        PathRelinkStrategy::Forward => {
            directional_path_relinking(func, sol1, sol2, half, cache, rng, deadline)
        }
        PathRelinkStrategy::Backward => {
            directional_path_relinking(func, sol2, sol1, half, cache, rng, deadline)
        }
        PathRelinkStrategy::Randomized => {
            if rng.random_range(0..2) == 0 {
                directional_path_relinking(func, sol1, sol2, half, cache, rng, deadline)
            } else {
                directional_path_relinking(func, sol2, sol1, half, cache, rng, deadline)
            }
        }
    }
}

/// Bidirectional path relinking between two solutions.
pub(crate) fn bidirectional_path_relinking<F>(
    func: &F,
    sol1: &[f64],
    sol2: &[f64],
    half: usize,
    cache: &mut Option<EvaluationCache>,
    rng: &mut ChaCha8Rng,
    deadline: Option<Instant>,
) -> (Vec<f64>, f64)
where
    F: Fn(&[f64]) -> f64,
{
    let (best_fwd, cost_fwd) =
        directional_path_relinking(func, sol1, sol2, half, cache, rng, deadline);
    let (best_bwd, cost_bwd) =
        directional_path_relinking(func, sol2, sol1, half, cache, rng, deadline);

    if cost_fwd <= cost_bwd {
        (best_fwd, cost_fwd)
    } else {
        (best_bwd, cost_bwd)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;
    use std::time::{Duration, Instant};

    #[test]
    fn test_identical_solutions_returns_immediately() {
        let mut rng = ChaCha8Rng::seed_from_u64(0);
        let sol = vec![1.0, 2.0, 3.0];
        let (result, cost) = bidirectional_path_relinking(
            &|x: &[f64]| x.iter().sum::<f64>(),
            &sol,
            &sol,
            3,
            &mut None,
            &mut rng,
            None,
        );
        assert_eq!(result, sol);
        assert!((cost - 6.0).abs() < 1e-10);
    }

    #[test]
    fn test_expired_deadline_breaks_inner_loop() {
        // deadline already expired → path_relinking_best loop breaks at line 33
        let mut rng = ChaCha8Rng::seed_from_u64(0);
        let sol1 = vec![0.0, 0.0, 0.0];
        let sol2 = vec![1.0, 1.0, 1.0];
        let func = |x: &[f64]| x.iter().map(|&xi| xi * xi).sum::<f64>();
        assert!((func(&sol1) - 0.0).abs() < 1e-10); // invoke closure body
        let deadline = Some(Instant::now() - Duration::from_secs(1));
        let (result, _cost) =
            bidirectional_path_relinking(&func, &sol1, &sol2, 3, &mut None, &mut rng, deadline);
        assert_eq!(result.len(), 3);
    }

    /// Constructs a function on the {0,1}^3 grid where the backward greedy path
    /// finds [0,1,1] (cost 2.0) — a point the forward greedy path never visits.
    /// Forward best = 5.0 (sol2), backward best = 2.0 → backward wins.
    #[test]
    fn test_backward_path_wins() {
        let mut rng = ChaCha8Rng::seed_from_u64(0);
        let func = |x: &[f64]| {
            let a = x[0] >= 0.5;
            let b = x[1] >= 0.5;
            let c = x[2] >= 0.5;
            match (a, b, c) {
                (false, false, false) => 10.0_f64, // sol1
                (true, false, false) => 8.0,
                (false, true, false) => 9.0,
                (false, false, true) => 11.0,
                (true, true, false) => 6.0,
                (true, false, true) => 7.0,
                (false, true, true) => 2.0, // backward step-1 finds this; forward never does
                (true, true, true) => 5.0,  // sol2
            }
        };
        let sol1 = vec![0.0, 0.0, 0.0];
        let sol2 = vec![1.0, 1.0, 1.0];
        let (result, cost) =
            bidirectional_path_relinking(&func, &sol1, &sol2, 3, &mut None, &mut rng, None);
        // Backward path: [1,1,1]→ set x[0]=0 → [0,1,1]=2.0 (best) → backward wins
        assert!((cost - 2.0).abs() < 1e-10);
        assert!((result[0]).abs() < 1e-10);
        assert!((result[1] - 1.0).abs() < 1e-10);
        assert!((result[2] - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_truncates_when_many_differences() {
        let mut rng = ChaCha8Rng::seed_from_u64(1);
        let sol1 = vec![0.0; 40];
        let sol2 = vec![1.0; 40];
        let func = |x: &[f64]| x.iter().sum::<f64>();
        let (result, cost) =
            bidirectional_path_relinking(&func, &sol1, &sol2, 40, &mut None, &mut rng, None);
        assert_eq!(result.len(), 40);
        assert!(cost.is_finite());
    }

    #[test]
    fn test_apply_path_relinking_strategy_all_modes() {
        let sphere = |x: &[f64]| x.iter().map(|&v| v * v).sum::<f64>();
        let source = vec![2.0, 2.0, 2.0];
        let target = vec![0.0, 0.0, 0.0];

        let mut rng_fwd = ChaCha8Rng::seed_from_u64(1);
        let mut rng_bwd = ChaCha8Rng::seed_from_u64(2);
        let mut rng_bi = ChaCha8Rng::seed_from_u64(3);
        let mut rng_rand = ChaCha8Rng::seed_from_u64(4);

        let (_fwd_sol, fwd_cost) = apply_path_relinking_strategy(
            &sphere,
            &source,
            &target,
            PathRelinkStrategy::Forward,
            3,
            &mut None,
            &mut rng_fwd,
            None,
        );
        let (_bwd_sol, bwd_cost) = apply_path_relinking_strategy(
            &sphere,
            &source,
            &target,
            PathRelinkStrategy::Backward,
            3,
            &mut None,
            &mut rng_bwd,
            None,
        );
        let (_bi_sol, bi_cost) = apply_path_relinking_strategy(
            &sphere,
            &source,
            &target,
            PathRelinkStrategy::Bidirectional,
            3,
            &mut None,
            &mut rng_bi,
            None,
        );
        let (_rand_sol, rand_cost) = apply_path_relinking_strategy(
            &sphere,
            &source,
            &target,
            PathRelinkStrategy::Randomized,
            3,
            &mut None,
            &mut rng_rand,
            None,
        );

        assert!(fwd_cost.is_finite());
        assert!(bwd_cost.is_finite());
        assert!(bi_cost.is_finite());
        assert!(rand_cost.is_finite());
    }

    #[test]
    fn test_randomized_strategy_exercises_both_branches() {
        let func = |x: &[f64]| {
            let a = x[0] >= 0.5;
            let b = x[1] >= 0.5;
            let c = x[2] >= 0.5;
            match (a, b, c) {
                (false, false, false) => 10.0_f64,
                (true, false, false) => 8.0,
                (false, true, false) => 9.0,
                (false, false, true) => 11.0,
                (true, true, false) => 6.0,
                (true, false, true) => 7.0,
                (false, true, true) => 2.0,
                (true, true, true) => 5.0,
            }
        };

        let sol1 = vec![0.0, 0.0, 0.0];
        let sol2 = vec![1.0, 1.0, 1.0];

        let mut saw_forward = false;
        let mut saw_backward = false;

        for seed in 0..1024_u64 {
            if saw_forward && saw_backward {
                break;
            }
            let mut rng = ChaCha8Rng::seed_from_u64(seed);
            let mut cache = None;
            let (_res, cost) = apply_path_relinking_strategy(
                &func,
                &sol1,
                &sol2,
                PathRelinkStrategy::Randomized,
                3,
                &mut cache,
                &mut rng,
                None,
            );

            // Forward path best cost is >= 5.0, backward can hit 2.0.
            if cost <= 2.0 + 1e-10 {
                saw_backward = true;
            } else {
                saw_forward = true;
            }
        }

        assert!(saw_forward);
        assert!(saw_backward);
    }
}
