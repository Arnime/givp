use std::env;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let request_path = env::args()
        .nth(1)
        .ok_or("usage: cargo run -- <batch-request.json>")?;
    let request: serde_json::Value = serde_json::from_str(&fs::read_to_string(request_path)?)?;
    let command = env::var("SYNTHETIC_HYDROPOWER_COMMAND")
        .unwrap_or_else(|_| "synthetic-hydropower".to_owned());
    let mut worker_command = Command::new(command);
    if cfg!(unix) {
        worker_command.env("PYTHONUNBUFFERED", "1");
    }
    let mut worker = worker_command
        .arg("worker")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()?;
    writeln!(worker.stdin.as_mut().ok_or("worker stdin unavailable")?, "{}", request)?;
    let mut output = BufReader::new(worker.stdout.take().ok_or("worker stdout unavailable")?);
    let mut line = String::new();
    output.read_line(&mut line)?;
    let response: serde_json::Value = serde_json::from_str(&line)?;
    if let Some(error) = response.get("error") {
        return Err(error.to_string().into());
    }
    println!("received {} hydraulic result(s)", response["results"].as_array().ok_or("missing results")?.len());
    Ok(())
}
