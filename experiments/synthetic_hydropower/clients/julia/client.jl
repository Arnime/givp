using JSON

1 <= length(ARGS) <= 2 || error("usage: julia client.jl <batch-request.json> [response.json]")
include(joinpath(@__DIR__, "adapter.jl"))

request = JSON.parsefile(ARGS[1])
worker = open(worker_command(), "r+")
try
    write(worker, JSON.json(request), "\n")
    flush(worker)
    response = JSON.parse(readline(worker))
    haskey(response, "error") && error(response["error"]["message"])
    if length(ARGS) == 2
        mkpath(dirname(ARGS[2]))
        open(ARGS[2], "w") do output
            JSON.print(output, response, 4)
        end
    end
    println("received ", length(response["results"]), " hydraulic result(s)")
    println(response["results"][1]["simulation"]["level_m"])
finally
    close(worker)
end
