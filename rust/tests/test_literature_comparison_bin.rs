// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

use std::fs;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn test_literature_comparison_smoke_schema_v1() {
    let exe = env!("CARGO_BIN_EXE_run_literature_comparison");
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time should be after UNIX_EPOCH")
        .as_nanos();
    let output_path = std::env::temp_dir().join(format!("givp-rust-lit-{}.json", ts));

    let out = Command::new(exe)
        .args([
            "--n-runs",
            "1",
            "--dims",
            "2",
            "--output",
            output_path
                .to_str()
                .expect("temp output path should be valid UTF-8"),
        ])
        .output()
        .expect("failed to run run_literature_comparison binary");

    assert!(
        out.status.success(),
        "runner failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );

    let payload = fs::read_to_string(&output_path)
        .expect("literature comparison runner should emit output JSON file");
    assert!(payload.contains("\"metadata\""));
    assert!(payload.contains("\"runs\""));
    assert!(payload.contains("\"summary\""));
    assert!(payload.contains("\"stats\""));
    assert!(payload.contains("\"schema_version\":\"benchmark-schema-v1\""));

    let _ = fs::remove_file(output_path);
}
