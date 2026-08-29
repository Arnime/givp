"""Run Julia GIVP using the Python synthetic hydropower reference worker."""

using GIVPOptimizer
using JSON

length(ARGS) == 1 || error("usage: julia --project=julia optimize.jl <definition.json>")
include(joinpath(@__DIR__, "adapter.jl"))

definition = JSON.parsefile(ARGS[1])
periods = Int(definition["periods"])
maximum = Float64.(definition["power_bounds_mw"]["maximum"])
bounds = vcat(fill((0.0, maximum[1]), periods), fill((0.0, maximum[2]), periods))
settings = definition["optimizer"]
config = GIVPConfig(
    max_iterations=Int(settings["max_iterations"]),
    vnd_iterations=Int(settings["vnd_iterations"]),
    ils_iterations=Int(settings["ils_iterations"]),
    num_candidates_per_step=Int(settings["num_candidates_per_step"]),
    use_elite_pool=Bool(settings["use_elite_pool"]),
    use_convergence_monitor=Bool(settings["use_convergence_monitor"]),
    n_workers=Int(settings["n_workers"]),
)
worker = HydropowerWorker()
try
    baseline = evaluate!(worker, zeros(48), definition; case_id="baseline")
    result = givp(x -> canonical_objective(worker, x, definition), bounds;
        config=config, direction=minimize, seed=Int(definition["seed"]))
    physical = evaluate!(worker, result.x, definition; case_id="optimized")
    println(JSON.json(Dict(
        "language" => "julia",
        "scenario" => definition["scenario"],
        "baseline_objective" => baseline["simulation"]["objective"],
        "optimizer_objective" => result.fun,
        "objective" => physical["simulation"]["objective"],
        "energy_mwh" => physical["simulation"]["energy_mwh"],
        "level_penalty" => physical["simulation"]["level_penalty"],
        "target_power_mw" => physical["power"]["target_power_mw"],
    )))
finally
    close_hydropower_worker(worker)
end
