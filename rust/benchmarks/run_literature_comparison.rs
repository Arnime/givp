// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

//! Reproducible multi-run literature comparison experiment.
//!
//! Runs GIVP-full on six standard benchmark functions over N independent seeds
//! and writes results to a JSON file compatible with the Python/Julia
//! `generate_report` tool.
//!
//! # Usage
//!
//! ```bash
//! # Default: 30 seeds × 10-D × 6 functions
//! cargo run --bin run_literature_comparison
//!
//! # Custom parameters
//! cargo run --bin run_literature_comparison -- \
//!     --n-runs 30 --dims 10 --output results.json --verbose
//! ```
//!
//! # References
//!
//! - De Jong, K.A. (1975). Sphere / De Jong F1.
//! - Rosenbrock, H.H. (1960). The Computer Journal, 3(3), 175–184.
//! - Rastrigin, L.A. (1974). Systems of Extremal Control. Nauka, Moscow.
//! - Ackley, D.H. (1987). A Connectionist Machine for Genetic Hillclimbing.
//! - Griewank, A.O. (1981). J. Optim. Theory Appl., 34(1), 11–39.
//! - Schwefel, H.P. (1981). Numerical Optimization of Computer Models.

use givp::{givp, GivpConfig};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::env;
use std::fs;
use std::time::Instant;

type ObjectiveFn = fn(&[f64]) -> f64;

// ── benchmark functions ──────────────────────────────────────────────────────

fn sphere(x: &[f64]) -> f64 {
    x.iter().map(|v| v * v).sum()
}

fn rosenbrock(x: &[f64]) -> f64 {
    x.windows(2)
        .map(|w| 100.0 * (w[1] - w[0] * w[0]).powi(2) + (1.0 - w[0]).powi(2))
        .sum()
}

fn rastrigin(x: &[f64]) -> f64 {
    let n = x.len() as f64;
    10.0 * n
        + x.iter()
            .map(|&xi| xi * xi - 10.0 * (2.0 * std::f64::consts::PI * xi).cos())
            .sum::<f64>()
}

fn ackley(x: &[f64]) -> f64 {
    let n = x.len() as f64;
    let sum_sq: f64 = x.iter().map(|&xi| xi * xi).sum::<f64>() / n;
    let sum_cos: f64 = x
        .iter()
        .map(|&xi| (2.0 * std::f64::consts::PI * xi).cos())
        .sum::<f64>()
        / n;
    -20.0 * (-0.2 * sum_sq.sqrt()).exp() - sum_cos.exp() + 20.0 + std::f64::consts::E
}

fn griewank(x: &[f64]) -> f64 {
    let sum_sq: f64 = x.iter().map(|&xi| xi * xi).sum::<f64>() / 4000.0;
    let prod_cos: f64 = x
        .iter()
        .enumerate()
        .map(|(i, &xi)| (xi / ((i + 1) as f64).sqrt()).cos())
        .product();
    1.0 + sum_sq - prod_cos
}

fn schwefel(x: &[f64]) -> f64 {
    let n = x.len() as f64;
    418.9829 * n - x.iter().map(|&xi| xi * xi.abs().sqrt().sin()).sum::<f64>()
}

// ── function registry ────────────────────────────────────────────────────────

struct BenchFunc {
    name: &'static str,
    func: fn(&[f64]) -> f64,
    bounds_fn: fn(usize) -> Vec<(f64, f64)>,
    optimum: f64,
    reference: &'static str,
}

fn get_functions() -> Vec<BenchFunc> {
    vec![
        BenchFunc {
            name: "Sphere",
            func: sphere,
            bounds_fn: |d| vec![(-5.12, 5.12); d],
            optimum: 0.0,
            reference: "De Jong (1975)",
        },
        BenchFunc {
            name: "Rosenbrock",
            func: rosenbrock,
            bounds_fn: |d| vec![(-5.0, 10.0); d],
            optimum: 0.0,
            reference: "Rosenbrock (1960)",
        },
        BenchFunc {
            name: "Rastrigin",
            func: rastrigin,
            bounds_fn: |d| vec![(-5.12, 5.12); d],
            optimum: 0.0,
            reference: "Rastrigin (1974)",
        },
        BenchFunc {
            name: "Ackley",
            func: ackley,
            bounds_fn: |d| vec![(-32.768, 32.768); d],
            optimum: 0.0,
            reference: "Ackley (1987)",
        },
        BenchFunc {
            name: "Griewank",
            func: griewank,
            bounds_fn: |d| vec![(-600.0, 600.0); d],
            optimum: 0.0,
            reference: "Griewank (1981)",
        },
        BenchFunc {
            name: "Schwefel",
            func: schwefel,
            bounds_fn: |d| vec![(-500.0, 500.0); d],
            optimum: 0.0,
            reference: "Schwefel (1981)",
        },
    ]
}

// ── trial runner ─────────────────────────────────────────────────────────────

struct TrialResult {
    algorithm: String,
    function: &'static str,
    seed: u64,
    fun: f64,
    nfev: usize,
    elapsed_s: f64,
}

struct SummaryRow {
    function: &'static str,
    algorithm: String,
    n_runs: usize,
    mean: f64,
    std: f64,
    best: f64,
    median: f64,
    worst: f64,
    nfev_mean: f64,
}

struct AlgoSpec {
    name: &'static str,
    description: &'static str,
}

fn algorithm_specs() -> &'static [AlgoSpec] {
    const ALGORITHMS: [AlgoSpec; 7] = [
        AlgoSpec {
            name: "GIVP-full",
            description: "GRASP-ILS-VND-PR -- full hybrid pipeline (this work)",
        },
        AlgoSpec {
            name: "GRASP-only",
            description: "GRASP-only baseline (Feo & Resende 1995)",
        },
        AlgoSpec {
            name: "DE",
            description: "Differential Evolution -- native benchmark implementation (Storn & Price 1997)",
        },
        AlgoSpec {
            name: "PSO",
            description: "Particle Swarm Optimization -- native benchmark implementation (Kennedy & Eberhart 1995)",
        },
        AlgoSpec {
            name: "GA",
            description: "Genetic Algorithm -- native benchmark implementation (Holland 1975)",
        },
        AlgoSpec {
            name: "CMA-ES",
            description: "CMA-ES style evolution strategy -- native benchmark implementation (Hansen & Ostermeier 2001)",
        },
        AlgoSpec {
            name: "SA",
            description: "Simulated Annealing -- native benchmark implementation (Kirkpatrick et al. 1983)",
        },
    ];
    &ALGORITHMS
}

fn sample_uniform(bounds: &[(f64, f64)], rng: &mut StdRng) -> Vec<f64> {
    bounds
        .iter()
        .map(|(lo, hi)| rng.random_range(*lo..=*hi))
        .collect()
}

fn clamp_to_bounds(x: &mut [f64], bounds: &[(f64, f64)]) {
    for (xi, (lo, hi)) in x.iter_mut().zip(bounds.iter()) {
        if *xi < *lo {
            *xi = *lo;
        } else if *xi > *hi {
            *xi = *hi;
        }
    }
}

fn normal01(rng: &mut StdRng) -> f64 {
    let u1 = rng.random::<f64>().max(1e-12);
    let u2 = rng.random::<f64>();
    (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
}

fn run_de(
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    seed: u64,
    max_iter: usize,
) -> (f64, usize, f64) {
    let start = Instant::now();
    let dim = bounds.len();
    let pop_size = (10 * dim).max(20);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut pop: Vec<Vec<f64>> = (0..pop_size)
        .map(|_| sample_uniform(bounds, &mut rng))
        .collect();
    let mut fit: Vec<f64> = pop.iter().map(|x| func(x)).collect();
    let mut nfev = fit.len();
    let mut best = fit.iter().copied().fold(f64::INFINITY, f64::min);

    for _ in 0..max_iter {
        for i in 0..pop_size {
            let mut r1;
            let mut r2;
            let mut r3;
            loop {
                r1 = rng.random_range(0..pop_size);
                if r1 != i {
                    break;
                }
            }
            loop {
                r2 = rng.random_range(0..pop_size);
                if r2 != i && r2 != r1 {
                    break;
                }
            }
            loop {
                r3 = rng.random_range(0..pop_size);
                if r3 != i && r3 != r1 && r3 != r2 {
                    break;
                }
            }

            let f = 0.8;
            let cr = 0.9;
            let jrand = rng.random_range(0..dim);
            let mut trial = pop[i].clone();
            for j in 0..dim {
                if rng.random::<f64>() < cr || j == jrand {
                    trial[j] = pop[r1][j] + f * (pop[r2][j] - pop[r3][j]);
                }
            }
            clamp_to_bounds(&mut trial, bounds);
            let trial_fit = func(&trial);
            nfev += 1;
            if trial_fit < fit[i] {
                pop[i] = trial;
                fit[i] = trial_fit;
                best = best.min(trial_fit);
            }
        }
    }

    (best, nfev, start.elapsed().as_secs_f64())
}

fn run_pso(
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    seed: u64,
    max_iter: usize,
) -> (f64, usize, f64) {
    let start = Instant::now();
    let dim = bounds.len();
    let swarm_size = (10 * dim).max(20);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut pos: Vec<Vec<f64>> = (0..swarm_size)
        .map(|_| sample_uniform(bounds, &mut rng))
        .collect();
    let mut vel: Vec<Vec<f64>> = vec![vec![0.0; dim]; swarm_size];
    let mut pbest = pos.clone();
    let mut pbest_fit: Vec<f64> = pbest.iter().map(|x| func(x)).collect();
    let mut nfev = pbest_fit.len();

    let mut gbest_idx = 0usize;
    for i in 1..swarm_size {
        if pbest_fit[i] < pbest_fit[gbest_idx] {
            gbest_idx = i;
        }
    }
    let mut gbest = pbest[gbest_idx].clone();
    let mut gbest_fit = pbest_fit[gbest_idx];

    let w = 0.729;
    let c1 = 1.494;
    let c2 = 1.494;

    for _ in 0..max_iter {
        for i in 0..swarm_size {
            for d in 0..dim {
                let r1 = rng.random::<f64>();
                let r2 = rng.random::<f64>();
                vel[i][d] = w * vel[i][d]
                    + c1 * r1 * (pbest[i][d] - pos[i][d])
                    + c2 * r2 * (gbest[d] - pos[i][d]);
                pos[i][d] += vel[i][d];
            }
            clamp_to_bounds(&mut pos[i], bounds);
            let f = func(&pos[i]);
            nfev += 1;
            if f < pbest_fit[i] {
                pbest[i] = pos[i].clone();
                pbest_fit[i] = f;
                if f < gbest_fit {
                    gbest = pbest[i].clone();
                    gbest_fit = f;
                }
            }
        }
    }

    (gbest_fit, nfev, start.elapsed().as_secs_f64())
}

fn run_ga(
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    seed: u64,
    max_iter: usize,
) -> (f64, usize, f64) {
    let start = Instant::now();
    let dim = bounds.len();
    let pop_size = (12 * dim).max(30);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut pop: Vec<Vec<f64>> = (0..pop_size)
        .map(|_| sample_uniform(bounds, &mut rng))
        .collect();
    let mut fit: Vec<f64> = pop.iter().map(|x| func(x)).collect();
    let mut nfev = fit.len();

    let tournament = |fit: &[f64], rng: &mut StdRng| -> usize {
        let a = rng.random_range(0..fit.len());
        let b = rng.random_range(0..fit.len());
        let c = rng.random_range(0..fit.len());
        let mut best = a;
        if fit[b] < fit[best] {
            best = b;
        }
        if fit[c] < fit[best] {
            best = c;
        }
        best
    };

    for _ in 0..max_iter {
        let mut order: Vec<usize> = (0..pop_size).collect();
        order.sort_by(|a, b| {
            fit[*a]
                .partial_cmp(&fit[*b])
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let mut new_pop: Vec<Vec<f64>> = Vec::with_capacity(pop_size);
        new_pop.push(pop[order[0]].clone());

        while new_pop.len() < pop_size {
            let p1 = tournament(&fit, &mut rng);
            let p2 = tournament(&fit, &mut rng);
            let mut child = vec![0.0; dim];
            for d in 0..dim {
                let beta = rng.random::<f64>();
                child[d] = beta * pop[p1][d] + (1.0 - beta) * pop[p2][d];
                if rng.random::<f64>() < 0.1 {
                    let scale = (bounds[d].1 - bounds[d].0) * 0.1;
                    child[d] += normal01(&mut rng) * scale;
                }
            }
            clamp_to_bounds(&mut child, bounds);
            new_pop.push(child);
        }

        pop = new_pop;
        fit = pop.iter().map(|x| func(x)).collect();
        nfev += fit.len();
    }

    let best = fit.iter().copied().fold(f64::INFINITY, f64::min);
    (best, nfev, start.elapsed().as_secs_f64())
}

fn run_cmaes_style(
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    seed: u64,
    max_iter: usize,
) -> (f64, usize, f64) {
    let start = Instant::now();
    let dim = bounds.len();
    let lambda = (4 + (3.0 * (dim as f64).ln()) as usize).max(6);
    let mu = (lambda / 2).max(2);
    let mut rng = StdRng::seed_from_u64(seed);
    let mut mean = sample_uniform(bounds, &mut rng);
    let avg_range = bounds.iter().map(|(lo, hi)| hi - lo).sum::<f64>() / dim as f64;
    let mut sigma = (avg_range * 0.3).max(1e-8);
    let mut nfev = 0usize;
    let mut best = f64::INFINITY;

    for _ in 0..max_iter {
        let mut population: Vec<(Vec<f64>, f64)> = Vec::with_capacity(lambda);
        for _ in 0..lambda {
            let mut x = vec![0.0; dim];
            for d in 0..dim {
                x[d] = mean[d] + sigma * normal01(&mut rng);
            }
            clamp_to_bounds(&mut x, bounds);
            let f = func(&x);
            nfev += 1;
            best = best.min(f);
            population.push((x, f));
        }
        population.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

        let mut new_mean = vec![0.0; dim];
        let mut w_sum = 0.0;
        for (rank, (x, _)) in population.iter().take(mu).enumerate() {
            let w = (mu as f64 + 0.5).ln() - ((rank + 1) as f64).ln();
            w_sum += w;
            for d in 0..dim {
                new_mean[d] += w * x[d];
            }
        }
        for value in new_mean.iter_mut().take(dim) {
            *value /= w_sum;
        }
        mean = new_mean;

        let success = population[0].1 <= best;
        sigma *= if success { 1.03 } else { 0.97 };
        sigma = sigma.clamp(1e-12, avg_range.max(1e-12));
    }

    (best, nfev, start.elapsed().as_secs_f64())
}

fn run_sa(
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    seed: u64,
    max_iter: usize,
) -> (f64, usize, f64) {
    let start = Instant::now();
    let dim = bounds.len();
    let mut rng = StdRng::seed_from_u64(seed);
    let mut x = sample_uniform(bounds, &mut rng);
    let mut fx = func(&x);
    let mut best = fx;
    let mut nfev = 1usize;
    let steps = (max_iter * 30).max(100);
    let t0 = 1.0_f64;
    let tf = 1e-3_f64;

    for k in 0..steps {
        let frac = k as f64 / steps as f64;
        let temp = t0 * (tf / t0).powf(frac);
        let mut y = x.clone();
        for d in 0..dim {
            let scale = (bounds[d].1 - bounds[d].0) * 0.1;
            y[d] += normal01(&mut rng) * scale;
        }
        clamp_to_bounds(&mut y, bounds);
        let fy = func(&y);
        nfev += 1;
        let delta = fy - fx;
        if delta <= 0.0 || rng.random::<f64>() < (-delta / temp.max(1e-12_f64)).exp() {
            x = y;
            fx = fy;
            if fx < best {
                best = fx;
            }
        }
    }

    (best, nfev, start.elapsed().as_secs_f64())
}

fn run_trial_with_config(
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    cfg: GivpConfig,
) -> (f64, usize, f64) {
    let start = Instant::now();
    match givp(func, bounds, cfg) {
        Ok(r) => (r.fun, r.nfev, start.elapsed().as_secs_f64()),
        Err(_) => (f64::INFINITY, 0, start.elapsed().as_secs_f64()),
    }
}

fn run_trial_dispatch(
    algorithm: &str,
    func: ObjectiveFn,
    bounds: &[(f64, f64)],
    dims: usize,
    seed: u64,
    max_iter: usize,
    time_limit: f64,
) -> Option<(f64, usize, f64)> {
    let mut cfg = GivpConfig {
        max_iterations: max_iter,
        seed: Some(seed),
        integer_split: Some(dims),
        time_limit,
        ..Default::default()
    };

    match algorithm {
        "GIVP-full" => Some(run_trial_with_config(func, bounds, cfg)),
        "GRASP-only" => {
            cfg.adaptive_alpha = false;
            cfg.vnd_iterations = 1;
            cfg.ils_iterations = 1;
            cfg.perturbation_strength = 1;
            cfg.use_elite_pool = false;
            cfg.use_convergence_monitor = false;
            cfg.early_stop_threshold = max_iter;
            Some(run_trial_with_config(func, bounds, cfg))
        }
        "DE" => Some(run_de(func, bounds, seed, max_iter)),
        "PSO" => Some(run_pso(func, bounds, seed, max_iter)),
        "GA" => Some(run_ga(func, bounds, seed, max_iter)),
        "CMA-ES" => Some(run_cmaes_style(func, bounds, seed, max_iter)),
        "SA" => Some(run_sa(func, bounds, seed, max_iter)),
        _ => None,
    }
}

// ── JSON serialisation (no external deps) ───────────────────────────────────

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn format_run_json(e: &TrialResult) -> String {
    format!(
        "{{\"algorithm\":\"{}\",\"function\":\"{}\",\"seed\":{},\"fun\":{:.10e},\"nfev\":{},\"time_s\":{:.4}}}",
        json_escape(&e.algorithm),
        json_escape(e.function),
        e.seed,
        e.fun,
        e.nfev,
        e.elapsed_s,
    )
}

fn format_summary_json(e: &SummaryRow) -> String {
    format!(
        concat!(
            "{{\"function\":\"{}\",\"algorithm\":\"{}\",\"n_runs\":{},",
            "\"mean\":{:.10e},\"std\":{:.10e},\"best\":{:.10e},",
            "\"median\":{:.10e},\"worst\":{:.10e},\"nfev_mean\":{:.10e}}}"
        ),
        json_escape(e.function),
        json_escape(&e.algorithm),
        e.n_runs,
        e.mean,
        e.std,
        e.best,
        e.median,
        e.worst,
        e.nfev_mean,
    )
}

fn build_summary(entries: &[TrialResult], functions: &[BenchFunc]) -> Vec<SummaryRow> {
    let mut rows = Vec::new();
    let algorithms = entries
        .iter()
        .map(|entry| entry.algorithm.as_str())
        .collect::<std::collections::BTreeSet<_>>();
    for bf in functions {
        for algorithm in &algorithms {
            let mut vals: Vec<f64> = entries
                .iter()
                .filter(|entry| entry.function == bf.name && entry.algorithm == *algorithm)
                .map(|entry| entry.fun)
                .collect();
            let nfevs: Vec<f64> = entries
                .iter()
                .filter(|entry| entry.function == bf.name && entry.algorithm == *algorithm)
                .map(|entry| entry.nfev as f64)
                .collect();
            vals.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            let n = vals.len();
            if n == 0 {
                continue;
            }
            let mean = vals.iter().sum::<f64>() / n as f64;
            let std = if n > 1 {
                let ss = vals.iter().map(|value| (value - mean).powi(2)).sum::<f64>();
                (ss / (n as f64 - 1.0)).sqrt()
            } else {
                0.0
            };
            let median = if n % 2 == 0 {
                (vals[n / 2 - 1] + vals[n / 2]) / 2.0
            } else {
                vals[n / 2]
            };
            rows.push(SummaryRow {
                function: bf.name,
                algorithm: (*algorithm).to_string(),
                n_runs: n,
                mean,
                std,
                best: vals[0],
                median,
                worst: vals[n - 1],
                nfev_mean: nfevs.iter().sum::<f64>() / nfevs.len() as f64,
            });
        }
    }
    rows
}

fn payload_to_json(entries: &[TrialResult], functions: &[BenchFunc], args: &Args) -> String {
    let summary = build_summary(entries, functions);
    let runs_json = entries
        .iter()
        .map(format_run_json)
        .collect::<Vec<_>>()
        .join(",\n    ");
    let summary_json = summary
        .iter()
        .map(format_summary_json)
        .collect::<Vec<_>>()
        .join(",\n    ");
    let function_refs = functions
        .iter()
        .map(|bf| {
            format!(
                "\"{}\":\"{}\"",
                json_escape(bf.name),
                json_escape(bf.reference)
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let function_names = functions
        .iter()
        .map(|bf| format!("\"{}\"", json_escape(bf.name)))
        .collect::<Vec<_>>()
        .join(", ");
    let algorithms_json = args
        .algorithms
        .iter()
        .map(|algorithm| format!("\"{}\"", json_escape(algorithm)))
        .collect::<Vec<_>>()
        .join(", ");
    let algo_desc_json = args
        .algorithms
        .iter()
        .filter_map(|algorithm| {
            algorithm_specs()
                .iter()
                .find(|spec| spec.name == algorithm)
                .map(|spec| {
                    format!(
                        "\"{}\":\"{}\"",
                        json_escape(spec.name),
                        json_escape(spec.description)
                    )
                })
        })
        .collect::<Vec<_>>()
        .join(",");

    format!(
        concat!(
            "{{\n",
            "  \"metadata\": {{",
            "\"schema_version\":\"benchmark-schema-v1\",",
            "\"givp_version\":\"{}\",",
            "\"dims\":{},\"n_runs\":{},",
            "\"algorithms\":[{}],",
            "\"functions\":[{}],",
            "\"problem_references\":{{{}}},",
            "\"algo_descriptions\":{{{}}}",
            "}},\n",
            "  \"runs\": [\n    {}\n  ],\n",
            "  \"summary\": [\n    {}\n  ],\n",
            "  \"stats\": [\n    {}\n  ]\n",
            "}}\n"
        ),
        env!("CARGO_PKG_VERSION"),
        args.dims,
        args.n_runs,
        algorithms_json,
        function_names,
        function_refs,
        algo_desc_json,
        runs_json,
        summary_json,
        summary_json,
    )
}

// ── CLI argument parsing ─────────────────────────────────────────────────────

struct Args {
    n_runs: usize,
    dims: usize,
    max_iter: usize,
    time_limit: f64,
    algorithms: Vec<String>,
    output: String,
    verbose: bool,
}

fn parse_args() -> Args {
    let argv: Vec<String> = env::args().collect();
    let mut n_runs = 30usize;
    let mut dims = 10usize;
    let mut max_iter = 200usize;
    let mut time_limit = 30.0f64;
    let mut algorithms = vec![
        "GIVP-full".to_string(),
        "DE".to_string(),
        "PSO".to_string(),
        "GA".to_string(),
        "CMA-ES".to_string(),
        "SA".to_string(),
    ];
    let mut output = "rust/benchmarks/literature_comparison.json".to_string();
    let mut verbose = false;
    let mut i = 1;
    while i < argv.len() {
        match argv[i].as_str() {
            "--n-runs" if i + 1 < argv.len() => {
                n_runs = argv[i + 1].parse().unwrap_or(30);
                i += 2;
            }
            "--dims" if i + 1 < argv.len() => {
                dims = argv[i + 1].parse().unwrap_or(10);
                i += 2;
            }
            "--max-iter" if i + 1 < argv.len() => {
                max_iter = argv[i + 1].parse().unwrap_or(200);
                i += 2;
            }
            "--time-limit" if i + 1 < argv.len() => {
                time_limit = argv[i + 1].parse().unwrap_or(30.0);
                i += 2;
            }
            "--algorithms" => {
                let mut parsed: Vec<String> = Vec::new();
                i += 1;
                while i < argv.len() && !argv[i].starts_with("--") {
                    parsed.push(argv[i].clone());
                    i += 1;
                }
                if !parsed.is_empty() {
                    algorithms = parsed;
                }
            }
            "--output" if i + 1 < argv.len() => {
                output = argv[i + 1].clone();
                i += 2;
            }
            "--verbose" => {
                verbose = true;
                i += 1;
            }
            _ => {
                i += 1;
            }
        }
    }
    Args {
        n_runs,
        dims,
        max_iter,
        time_limit,
        algorithms,
        output,
        verbose,
    }
}

// ── main ─────────────────────────────────────────────────────────────────────

fn main() {
    let args = parse_args();
    let functions = get_functions();

    println!("GIVP Literature Comparison (Rust)");
    println!(
        "  dims={}  runs/function={}  functions={}  algorithms={}",
        args.dims,
        args.n_runs,
        functions.len(),
        args.algorithms.join(",")
    );
    println!("  output → {}", args.output);
    println!();

    let mut entries: Vec<TrialResult> = Vec::new();
    let known_algorithms = args
        .algorithms
        .iter()
        .filter(|algorithm| {
            algorithm_specs()
                .iter()
                .any(|spec| spec.name == algorithm.as_str())
        })
        .cloned()
        .collect::<Vec<_>>();
    let total = functions.len() * known_algorithms.len() * args.n_runs;
    let mut done = 0usize;

    for algorithm in &args.algorithms {
        if !algorithm_specs()
            .iter()
            .any(|spec| spec.name == algorithm.as_str())
        {
            eprintln!("[warn] unknown algorithm '{}': skipping", algorithm);
            continue;
        }

        for bf in &functions {
            let bounds = (bf.bounds_fn)(args.dims);
            let mut bests: Vec<f64> = Vec::with_capacity(args.n_runs);

            for seed in 0..args.n_runs as u64 {
                let Some((best, nfev, elapsed)) = run_trial_dispatch(
                    algorithm,
                    bf.func,
                    &bounds,
                    args.dims,
                    seed,
                    args.max_iter,
                    args.time_limit,
                ) else {
                    continue;
                };
                if args.verbose {
                    println!(
                        "  {:>10} {:>12} seed={:>3} best={:.6e} nfev={} {:.2}s",
                        algorithm, bf.name, seed, best, nfev, elapsed
                    );
                }
                bests.push(best);
                entries.push(TrialResult {
                    algorithm: algorithm.clone(),
                    function: bf.name,
                    seed,
                    fun: best,
                    nfev,
                    elapsed_s: elapsed,
                });
                done += 1;
                if !args.verbose && done % 30 == 0 {
                    println!(
                        "  [{}/{}] last: {} {} seed={}",
                        done, total, algorithm, bf.name, seed
                    );
                }
            }

            if bests.is_empty() {
                continue;
            }
            let mean = bests.iter().sum::<f64>() / bests.len() as f64;
            let variance =
                bests.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / bests.len() as f64;
            let std = variance.sqrt();
            let min = bests.iter().cloned().fold(f64::INFINITY, f64::min);
            println!(
                "  {:>10} {:>12} mean={:.4e} std={:.4e} best={:.4e} gap={:.4e}",
                algorithm,
                bf.name,
                mean,
                std,
                min,
                (min - bf.optimum).abs()
            );
        }
    }

    // ensure output directory exists
    if let Some(parent) = std::path::Path::new(&args.output).parent() {
        if !parent.as_os_str().is_empty() {
            let _ = fs::create_dir_all(parent);
        }
    }

    let json = payload_to_json(&entries, &functions, &args);
    match fs::write(&args.output, &json) {
        Ok(_) => println!("\nResults written to {}", args.output),
        Err(e) => {
            eprintln!("Failed to write {}: {}", args.output, e);
            std::process::exit(1);
        }
    }
}
