using JSON

length(ARGS) == 1 || error("usage: julia client.jl <batch-request.json>")
include(joinpath(@__DIR__, "adapter.jl"))

request = JSON.parsefile(ARGS[1])
worker = open(worker_command(), "r+")
try
    write(worker, JSON.json(request), "\n")
    flush(worker)
    response = JSON.parse(readline(worker))
    haskey(response, "error") && error(response["error"]["message"])
    println("received ", length(response["results"]), " hydraulic result(s)")
    println(response["results"][1]["simulation"]["level_m"])
finally
    close(worker)
end
