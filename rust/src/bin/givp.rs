// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

//! Minimal CLI for running GIVP on built-in benchmark functions.

use givp::{givp, Direction, GivpConfig};

fn sphere(x: &[f64]) -> f64 {
    x.iter().map(|v| v * v).sum()
}

fn rosenbrock(x: &[f64]) -> f64 {
    x.windows(2)
        .map(|w| 100.0 * (w[1] - w[0] * w[0]).powi(2) + (1.0 - w[0]).powi(2))
        .sum()
}

fn parse_args_from<I>(args: I) -> (String, usize, u64, Direction, usize)
where
    I: IntoIterator<Item = String>,
{
    let args: Vec<String> = args.into_iter().collect();
    let mut function = String::from("sphere");
    let mut dims = 10usize;
    let mut seed = 42u64;
    let mut direction = Direction::Minimize;
    let mut workers = 1usize;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--function" if i + 1 < args.len() => {
                function = args[i + 1].clone();
                i += 2;
            }
            "--dims" if i + 1 < args.len() => {
                dims = args[i + 1].parse().unwrap_or(10);
                i += 2;
            }
            "--seed" if i + 1 < args.len() => {
                seed = args[i + 1].parse().unwrap_or(42);
                i += 2;
            }
            "--direction" if i + 1 < args.len() => {
                direction = if args[i + 1].eq_ignore_ascii_case("maximize") {
                    Direction::Maximize
                } else {
                    Direction::Minimize
                };
                i += 2;
            }
            "--workers" if i + 1 < args.len() => {
                workers = args[i + 1].parse().unwrap_or(1);
                i += 2;
            }
            _ => {
                i += 1;
            }
        }
    }

    (function, dims.max(1), seed, direction, workers)
}

type Bounds = Vec<(f64, f64)>;
type ObjectiveFn = fn(&[f64]) -> f64;
type BoundsAndFn = (Bounds, ObjectiveFn);

struct CliResult<'a> {
    function: &'a str,
    dims: usize,
    seed: u64,
    best: f64,
    nfev: usize,
    nit: usize,
    success: bool,
    message: String,
}

fn to_json(record: &CliResult<'_>) -> String {
    format!(
        "{{\"function\":\"{}\",\"dims\":{},\"seed\":{},\"best\":{:.10e},\"nfev\":{},\"nit\":{},\"success\":{},\"message\":\"{}\"}}",
        record.function,
        record.dims,
        record.seed,
        record.best,
        record.nfev,
        record.nit,
        record.success,
        record.message.replace('"', "\\\"")
    )
}

fn run_cli_with<I>(args: I) -> (bool, String)
where
    I: IntoIterator<Item = String>,
{
    let (fun_name, dims, seed, direction, workers) = parse_args_from(args);
    let (bounds, f): BoundsAndFn = match fun_name.as_str() {
        "sphere" => (vec![(-5.12, 5.12); dims], sphere),
        "rosenbrock" => (vec![(-5.0, 10.0); dims], rosenbrock),
        _ => {
            let payload = CliResult {
                function: &fun_name,
                dims,
                seed,
                best: f64::INFINITY,
                nfev: 0,
                nit: 0,
                success: false,
                message: format!("unknown function: {}", fun_name),
            };
            return (false, to_json(&payload));
        }
    };

    let cfg = GivpConfig {
        max_iterations: 50,
        seed: Some(seed),
        direction,
        integer_split: Some(dims),
        n_workers: workers,
        ..Default::default()
    };

    match givp(f, &bounds, cfg) {
        Ok(result) => {
            let payload = CliResult {
                function: &fun_name,
                dims,
                seed,
                best: result.fun,
                nfev: result.nfev,
                nit: result.nit,
                success: result.success,
                message: result.message,
            };
            (true, to_json(&payload))
        }
        Err(e) => {
            let payload = CliResult {
                function: &fun_name,
                dims,
                seed,
                best: f64::INFINITY,
                nfev: 0,
                nit: 0,
                success: false,
                message: e.to_string(),
            };
            (false, to_json(&payload))
        }
    }
}

fn main() -> std::process::ExitCode {
    let (ok, payload) = run_cli_with(std::env::args());
    if ok {
        println!("{}", payload);
        std::process::ExitCode::SUCCESS
    } else {
        eprintln!("{}", payload);
        std::process::ExitCode::from(1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_args_defaults() {
        let args = vec!["givp".to_string()];
        let (function, dims, seed, direction, workers) = parse_args_from(args);
        assert_eq!(function, "sphere");
        assert_eq!(dims, 10);
        assert_eq!(seed, 42);
        assert_eq!(direction, Direction::Minimize);
        assert_eq!(workers, 1);
    }

    #[test]
    fn test_parse_args_custom_values() {
        let args = vec![
            "givp".to_string(),
            "--function".to_string(),
            "rosenbrock".to_string(),
            "--dims".to_string(),
            "7".to_string(),
            "--seed".to_string(),
            "123".to_string(),
            "--direction".to_string(),
            "maximize".to_string(),
            "--workers".to_string(),
            "4".to_string(),
        ];
        let (function, dims, seed, direction, workers) = parse_args_from(args);
        assert_eq!(function, "rosenbrock");
        assert_eq!(dims, 7);
        assert_eq!(seed, 123);
        assert_eq!(direction, Direction::Maximize);
        assert_eq!(workers, 4);
    }

    #[test]
    fn test_parse_args_invalid_values_fallback() {
        let args = vec![
            "givp".to_string(),
            "--dims".to_string(),
            "abc".to_string(),
            "--seed".to_string(),
            "x".to_string(),
            "--direction".to_string(),
            "other".to_string(),
            "--workers".to_string(),
            "n".to_string(),
        ];
        let (_function, dims, seed, direction, workers) = parse_args_from(args);
        assert_eq!(dims, 10);
        assert_eq!(seed, 42);
        assert_eq!(direction, Direction::Minimize);
        assert_eq!(workers, 1);
    }

    #[test]
    fn test_parse_args_ignores_unknown_tokens() {
        let args = vec![
            "givp".to_string(),
            "--weird".to_string(),
            "x".to_string(),
            "--dims".to_string(),
            "2".to_string(),
        ];
        let (_function, dims, _seed, _direction, _workers) = parse_args_from(args);
        assert_eq!(dims, 2);
    }

    #[test]
    fn test_parse_args_dims_min_one() {
        let args = vec!["givp".to_string(), "--dims".to_string(), "0".to_string()];
        let (_function, dims, _seed, _direction, _workers) = parse_args_from(args);
        assert_eq!(dims, 1);
    }

    #[test]
    fn test_to_json_escapes_quotes() {
        let payload = CliResult {
            function: "sphere",
            dims: 5,
            seed: 42,
            best: 1.25,
            nfev: 100,
            nit: 10,
            success: true,
            message: "msg with \"quote\"".to_string(),
        };
        let json = to_json(&payload);
        assert!(json.contains("\\\"quote\\\""));
        assert!(json.contains("\"function\":\"sphere\""));
    }

    #[test]
    fn test_run_cli_success() {
        let (ok, payload) = run_cli_with(vec![
            "givp".to_string(),
            "--function".to_string(),
            "sphere".to_string(),
            "--dims".to_string(),
            "3".to_string(),
        ]);
        assert!(ok);
        assert!(payload.contains("\"success\":true"));
        assert!(payload.contains("\"function\":\"sphere\""));
    }

    #[test]
    fn test_run_cli_unknown_function_error() {
        let (ok, payload) = run_cli_with(vec![
            "givp".to_string(),
            "--function".to_string(),
            "unknown".to_string(),
        ]);
        assert!(!ok);
        assert!(payload.contains("unknown function"));
        assert!(payload.contains("\"success\":false"));
    }

    #[test]
    fn test_run_cli_invalid_workers_error() {
        let (ok, payload) = run_cli_with(vec![
            "givp".to_string(),
            "--workers".to_string(),
            "0".to_string(),
        ]);
        assert!(!ok);
        assert!(payload.contains("n_workers must be >= 1"));
        assert!(payload.contains("\"success\":false"));
    }

    #[test]
    fn test_main_test_variant() {
        main();
    }
}
