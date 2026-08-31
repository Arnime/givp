use std::env;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Mutex, OnceLock};

use givp::{givp, Direction, GivpConfig};
use serde_json::{json, Value};

struct HydropowerWorker {
    child: Child,
    input: ChildStdin,
    output: BufReader<ChildStdout>,
}

impl HydropowerWorker {
    fn start() -> Result<Self, Box<dyn std::error::Error>> {
        let launcher = env::var("SYNTHETIC_HYDROPOWER_COMMAND")
            .unwrap_or_else(|_| "synthetic-hydropower".to_owned());
        let mut command = if cfg!(windows) && launcher.to_lowercase().ends_with(".cmd") {
            let script = launcher.trim_end_matches(".cmd");
            let python = std::path::Path::new(&launcher)
                .parent()
                .ok_or("launcher has no parent")?
                .join("python.exe");
            let mut process = Command::new(python);
            process.args(["-u", script, "worker"]);
            process
        } else {
            let mut process = Command::new(launcher);
            if cfg!(unix) {
                process.env("PYTHONUNBUFFERED", "1");
            }
            process.arg("worker");
            process
        };
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()?;
        Ok(Self {
            input: child.stdin.take().ok_or("worker stdin unavailable")?,
            output: BufReader::new(child.stdout.take().ok_or("worker stdout unavailable")?),
            child,
        })
    }

    fn evaluate(
        &mut self,
        vector: &[f64],
        definition: &Value,
        case_id: &str,
    ) -> Result<Value, Box<dyn std::error::Error>> {
        let schedule = project_power(vector, definition)?;
        let payload = json!({"schema_version":"synthetic-hydropower/v1","requests":[{
            "case_id":case_id,
            "incremental_inflow_m3s":definition["incremental_inflow_m3s"],
            "target_power_mw":schedule
        }]});
        writeln!(self.input, "{payload}")?;
        self.input.flush()?;
        let mut line = String::new();
        self.output.read_line(&mut line)?;
        let response: Value = serde_json::from_str(&line)?;
        if let Some(error) = response.get("error") {
            return Err(error.to_string().into());
        }
        response["results"]
            .as_array()
            .and_then(|items| items.first())
            .cloned()
            .ok_or_else(|| "worker returned no result".into())
    }
}

impl Drop for HydropowerWorker {
    fn drop(&mut self) {
        let _ = self.child.kill();
    }
}

fn project_power(
    vector: &[f64],
    definition: &Value,
) -> Result<Vec<Vec<f64>>, Box<dyn std::error::Error>> {
    let periods = definition["periods"].as_u64().ok_or("missing periods")? as usize;
    let minimum = definition["power_bounds_mw"]["minimum"]
        .as_array()
        .ok_or("missing minimum bounds")?;
    let maximum = definition["power_bounds_mw"]["maximum"]
        .as_array()
        .ok_or("missing maximum bounds")?;
    if vector.len() != periods * 2 {
        return Err("invalid power vector length".into());
    }
    (0..2)
        .map(|plant| {
            let min = minimum[plant].as_f64().ok_or("invalid minimum")?;
            let max = maximum[plant].as_f64().ok_or("invalid maximum")?;
            Ok(vector[plant * periods..(plant + 1) * periods]
                .iter()
                .map(|value| {
                    let raw = value.clamp(0.0, max);
                    if raw < min / 2.0 {
                        0.0
                    } else {
                        raw.max(min)
                    }
                })
                .collect())
        })
        .collect()
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = env::args()
        .nth(1)
        .ok_or("usage: optimize <definition.json>")?;
    let definition: Value = serde_json::from_str(&fs::read_to_string(path)?)?;
    let periods = definition["periods"].as_u64().ok_or("missing periods")? as usize;
    let maximum = definition["power_bounds_mw"]["maximum"]
        .as_array()
        .ok_or("missing maximum bounds")?;
    let bounds: Vec<(f64, f64)> = (0..2)
        .flat_map(|plant| std::iter::repeat((0.0, maximum[plant].as_f64().unwrap())).take(periods))
        .collect();
    let settings = &definition["optimizer"];
    let config = GivpConfig {
        max_iterations: settings["max_iterations"].as_u64().unwrap() as usize,
        vnd_iterations: settings["vnd_iterations"].as_u64().unwrap() as usize,
        ils_iterations: settings["ils_iterations"].as_u64().unwrap() as usize,
        num_candidates_per_step: settings["num_candidates_per_step"].as_u64().unwrap() as usize,
        use_elite_pool: settings["use_elite_pool"].as_bool().unwrap(),
        use_convergence_monitor: settings["use_convergence_monitor"].as_bool().unwrap(),
        n_workers: 1,
        direction: Direction::Minimize,
        seed: Some(definition["seed"].as_u64().unwrap()),
        ..Default::default()
    };
    let worker = Mutex::new(HydropowerWorker::start()?);
    let worker_error = OnceLock::<String>::new();
    let baseline =
        worker
            .lock()
            .unwrap()
            .evaluate(&vec![0.0; periods * 2], &definition, "baseline")?;
    let result = givp(
        |candidate| match worker
            .lock()
            .unwrap()
            .evaluate(candidate, &definition, "candidate")
        {
            Ok(value) => value["simulation"]["objective"]
                .as_f64()
                .filter(|objective| objective.is_finite())
                .unwrap_or_else(|| {
                    let _ = worker_error.set("worker returned a non-finite objective".to_owned());
                    f64::INFINITY
                }),
            Err(error) => {
                let _ = worker_error.set(error.to_string());
                f64::INFINITY
            }
        },
        &bounds,
        config,
    )?;
    if let Some(error) = worker_error.get() {
        return Err(format!("synthetic hydropower worker failed: {error}").into());
    }
    let physical = worker
        .lock()
        .unwrap()
        .evaluate(&result.x, &definition, "optimized")?;
    println!(
        "{}",
        json!({"language":"rust","scenario":definition["scenario"],
        "baseline_objective":baseline["simulation"]["objective"], "optimizer_objective":result.fun,
        "objective":physical["simulation"]["objective"],
        "energy_mwh":physical["simulation"]["energy_mwh"], "level_penalty":physical["simulation"]["level_penalty"],
        "target_power_mw":physical["power"]["target_power_mw"]})
    );
    Ok(())
}
