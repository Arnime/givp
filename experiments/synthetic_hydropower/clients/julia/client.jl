using JSON3

length(ARGS) == 1 || error("usage: julia client.jl <batch-request.json>")
request = JSON3.read(read(ARGS[1], String))
command = get(ENV, "SYNTHETIC_HYDROPOWER_COMMAND", "synthetic-hydropower")
worker = open(`$command worker`, "r+")
try
    write(worker, JSON3.write(request), "\n")
    flush(worker)
    response = JSON3.read(readline(worker))
    haskey(response, :error) && error(response.error.message)
    println("received ", length(response.results), " hydraulic result(s)")
    println(response.results[1].simulation.level_m)
finally
    close(worker)
end
