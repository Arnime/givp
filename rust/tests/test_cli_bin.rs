// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

use std::process::Command;

fn run_givp(args: &[&str]) -> std::process::Output {
    let exe = env!("CARGO_BIN_EXE_givp");
    Command::new(exe)
        .args(args)
        .output()
        .expect("failed to run givp binary")
}

#[test]
fn test_cli_default_success_json() {
    let out = run_givp(&[]);
    assert!(out.status.success());

    let stdout = String::from_utf8(out.stdout).expect("stdout should be valid UTF-8");
    assert!(stdout.contains("\"function\":\"sphere\""));
    assert!(stdout.contains("\"success\":true"));
}

#[test]
fn test_cli_rosenbrock_maximize_success() {
    let out = run_givp(&[
        "--function",
        "rosenbrock",
        "--dims",
        "3",
        "--seed",
        "123",
        "--direction",
        "maximize",
        "--workers",
        "2",
    ]);
    assert!(out.status.success());

    let stdout = String::from_utf8(out.stdout).expect("stdout should be valid UTF-8");
    assert!(stdout.contains("\"function\":\"rosenbrock\""));
    assert!(stdout.contains("\"success\":true"));
}

#[test]
fn test_cli_unknown_function_fails() {
    let out = run_givp(&["--function", "unknown"]);
    assert!(!out.status.success());

    let stderr = String::from_utf8(out.stderr).expect("stderr should be valid UTF-8");
    assert!(stderr.contains("unknown function"));
    assert!(stderr.contains("\"success\":false"));
}

#[test]
fn test_cli_invalid_workers_fails_via_config_validation() {
    let out = run_givp(&["--workers", "0"]);
    assert!(!out.status.success());

    let stderr = String::from_utf8(out.stderr).expect("stderr should be valid UTF-8");
    assert!(stderr.contains("n_workers must be >= 1"));
    assert!(stderr.contains("\"success\":false"));
}
