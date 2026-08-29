"""Persistent JSON-lines client for the canonical synthetic hydropower worker."""

using JSON

function worker_command()
    command = get(ENV, "SYNTHETIC_HYDROPOWER_COMMAND", "synthetic-hydropower")
    if Sys.iswindows() && endswith(lowercase(command), ".cmd")
        python = joinpath(dirname(command), "python.exe")
        script = command[1:end-4]
        isfile(python) && isfile(script) || error("incomplete Windows hydropower launcher")
        return Cmd([python, "-u", script, "worker"])
    end
    Cmd([command, "worker"])
end

mutable struct HydropowerWorker
    io::IO
end

function HydropowerWorker()
    return HydropowerWorker(open(worker_command(), "r+"))
end

function close_hydropower_worker(worker::HydropowerWorker)
    Base.close(worker.io)
end

function project_power(vector::Vector{Float64}, definition)
    periods = Int(definition["periods"])
    length(vector) == 2 * periods || error("power vector must have $(2 * periods) values")
    minimum = Float64.(definition["power_bounds_mw"]["minimum"])
    maximum = Float64.(definition["power_bounds_mw"]["maximum"])
    schedule = [zeros(Float64, periods), zeros(Float64, periods)]
    for plant in 1:2, period in 1:periods
        raw = clamp(vector[(plant - 1) * periods + period], 0.0, maximum[plant])
        schedule[plant][period] = raw < minimum[plant] / 2 ? 0.0 : max(raw, minimum[plant])
    end
    schedule
end

function evaluate!(worker::HydropowerWorker, vector::Vector{Float64}, definition; case_id="candidate")
    payload = Dict(
        "schema_version" => "synthetic-hydropower/v1",
        "requests" => [Dict(
            "case_id" => case_id,
            "incremental_inflow_m3s" => definition["incremental_inflow_m3s"],
            "target_power_mw" => project_power(vector, definition),
        )],
    )
    write(worker.io, JSON.json(payload), "\n")
    flush(worker.io)
    response = JSON.parse(readline(worker.io))
    haskey(response, "error") && error(response["error"]["message"])
    only(response["results"])
end

canonical_objective(worker::HydropowerWorker, vector::Vector{Float64}, definition) =
    Float64(evaluate!(worker, vector, definition)["simulation"]["objective"])
