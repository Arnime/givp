#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <givp/givp.hpp>
#include <nlohmann/json.hpp>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>
#endif

namespace {

class Worker {
public:
    Worker() { start(); }
    ~Worker() { stop(); }
    Worker(const Worker&) = delete;
    Worker& operator=(const Worker&) = delete;

    nlohmann::json evaluate(const std::vector<double>& vector, const nlohmann::json& definition,
                            const std::string& case_id) {
        const auto schedule = project(vector, definition);
        const nlohmann::json request = {
            {"schema_version", "synthetic-hydropower/v1"},
            {"requests", {{{"case_id", case_id},
                          {"incremental_inflow_m3s", definition.at("incremental_inflow_m3s")},
                          {"target_power_mw", schedule}}}},
        };
        write_line(request.dump());
        const auto response = nlohmann::json::parse(read_line());
        if (response.contains("error")) throw std::runtime_error(response.at("error").at("message"));
        return response.at("results").at(0);
    }

private:
#if defined(_WIN32)
    HANDLE process_ = nullptr;
    HANDLE input_ = nullptr;
    HANDLE output_ = nullptr;
#else
    pid_t process_ = -1;
    int input_ = -1;
    int output_ = -1;
#endif

    static std::vector<std::vector<double>> project(const std::vector<double>& vector,
                                                    const nlohmann::json& definition) {
        const auto periods = definition.at("periods").get<std::size_t>();
        if (vector.size() != 2 * periods) throw std::runtime_error("invalid power vector length");
        const auto minimum = definition.at("power_bounds_mw").at("minimum");
        const auto maximum = definition.at("power_bounds_mw").at("maximum");
        std::vector<std::vector<double>> schedule(2, std::vector<double>(periods));
        for (std::size_t plant = 0; plant < 2; ++plant) {
            const auto lower = minimum.at(plant).get<double>();
            const auto upper = maximum.at(plant).get<double>();
            for (std::size_t period = 0; period < periods; ++period) {
                const auto raw = std::clamp(vector[plant * periods + period], 0.0, upper);
                schedule[plant][period] = raw < lower / 2.0 ? 0.0 : std::max(raw, lower);
            }
        }
        return schedule;
    }

    void start() {
        const char* raw = std::getenv("SYNTHETIC_HYDROPOWER_COMMAND");
        const std::string launcher = raw == nullptr ? "synthetic-hydropower" : raw;
#if defined(_WIN32)
        const auto command = windows_command(launcher);
        SECURITY_ATTRIBUTES attributes{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
        HANDLE child_input = nullptr, child_output = nullptr;
        if (!CreatePipe(&child_output, &output_, &attributes, 0) ||
            !SetHandleInformation(output_, HANDLE_FLAG_INHERIT, 0) ||
            !CreatePipe(&input_, &child_input, &attributes, 0) ||
            !SetHandleInformation(input_, HANDLE_FLAG_INHERIT, 0)) {
            throw std::runtime_error("unable to create hydropower worker pipes");
        }
        STARTUPINFOA startup{};
        startup.cb = sizeof(startup);
        startup.dwFlags = STARTF_USESTDHANDLES;
        startup.hStdInput = child_input;
        startup.hStdOutput = child_output;
        startup.hStdError = child_output;
        PROCESS_INFORMATION info{};
        std::vector<char> mutable_command(command.begin(), command.end());
        mutable_command.push_back('\0');
        if (!CreateProcessA(nullptr, mutable_command.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW,
                            nullptr, nullptr, &startup, &info)) {
            throw std::runtime_error("unable to start hydropower worker");
        }
        CloseHandle(child_input);
        CloseHandle(child_output);
        CloseHandle(info.hThread);
        process_ = info.hProcess;
#else
        int stdin_pipe[2], stdout_pipe[2];
        if (pipe(stdin_pipe) != 0 || pipe(stdout_pipe) != 0) throw std::runtime_error("unable to create worker pipes");
        process_ = fork();
        if (process_ < 0) throw std::runtime_error("unable to fork hydropower worker");
        if (process_ == 0) {
            dup2(stdin_pipe[0], STDIN_FILENO);
            dup2(stdout_pipe[1], STDOUT_FILENO);
            close(stdin_pipe[1]); close(stdout_pipe[0]);
            setenv("PYTHONUNBUFFERED", "1", 1);
            execlp(launcher.c_str(), launcher.c_str(), "worker", static_cast<char*>(nullptr));
            _exit(127);
        }
        close(stdin_pipe[0]); close(stdout_pipe[1]);
        input_ = stdin_pipe[1]; output_ = stdout_pipe[0];
#endif
    }

#if defined(_WIN32)
    static std::string windows_command(const std::string& launcher) {
        if (launcher.size() > 4 && launcher.substr(launcher.size() - 4) == ".cmd") {
            std::filesystem::path path(launcher);
            return "\"" + (path.parent_path() / "python.exe").string() + "\" -u \"" +
                   path.replace_extension("").string() + "\" worker";
        }
        return "\"" + launcher + "\" worker";
    }
#endif

    void write_line(const std::string& value) {
        const std::string line = value + "\n";
#if defined(_WIN32)
        DWORD written = 0;
        if (!WriteFile(input_, line.data(), static_cast<DWORD>(line.size()), &written, nullptr) || written != line.size())
            throw std::runtime_error("unable to write to hydropower worker");
#else
        if (write(input_, line.data(), line.size()) != static_cast<ssize_t>(line.size()))
            throw std::runtime_error("unable to write to hydropower worker");
#endif
    }

    std::string read_line() {
        std::string line;
        char character = '\0';
        while (character != '\n') {
#if defined(_WIN32)
            DWORD count = 0;
            if (!ReadFile(output_, &character, 1, &count, nullptr) || count == 0) break;
#else
            if (read(output_, &character, 1) != 1) break;
#endif
            if (character != '\n') line += character;
        }
        if (line.empty()) throw std::runtime_error("hydropower worker closed without a response");
        return line;
    }

    void stop() noexcept {
#if defined(_WIN32)
        if (input_ != nullptr) CloseHandle(input_);
        if (output_ != nullptr) CloseHandle(output_);
        if (process_ != nullptr) { TerminateProcess(process_, 0); CloseHandle(process_); }
#else
        if (input_ >= 0) close(input_);
        if (output_ >= 0) close(output_);
        if (process_ > 0) { kill(process_, SIGTERM); waitpid(process_, nullptr, 0); }
#endif
    }
};

} // namespace

int main(int argc, char* argv[]) {
    if (argc != 2) throw std::runtime_error("usage: synthetic_hydropower_optimize <definition.json>");
    std::ifstream source(argv[1]);
    const nlohmann::json definition = nlohmann::json::parse(source);
    const auto periods = definition.at("periods").get<std::size_t>();
    std::vector<std::pair<double, double>> bounds;
    for (std::size_t plant = 0; plant < 2; ++plant)
        for (std::size_t time = 0; time < periods; ++time)
            bounds.emplace_back(0.0, definition.at("power_bounds_mw").at("maximum").at(plant));
    const auto settings = definition.at("optimizer");
    givp::GivpConfig config;
    config.max_iterations = settings.at("max_iterations");
    config.vnd_iterations = settings.at("vnd_iterations");
    config.ils_iterations = settings.at("ils_iterations");
    config.num_candidates_per_step = settings.at("num_candidates_per_step");
    config.use_elite_pool = settings.at("use_elite_pool");
    config.use_convergence_monitor = settings.at("use_convergence_monitor");
    config.n_workers = settings.at("n_workers");
    config.seed = definition.at("seed").get<std::uint64_t>();
    Worker worker;
    std::string worker_error;
    const auto baseline = worker.evaluate(std::vector<double>(2 * periods, 0.0), definition, "baseline");
    const auto result = givp::givp([&](const std::vector<double>& candidate) {
        try {
            const auto objective = worker.evaluate(candidate, definition, "candidate")
                                       .at("simulation").at("objective").get<double>();
            if (std::isfinite(objective)) return objective;
            worker_error = "worker returned a non-finite objective";
        } catch (const std::exception& error) {
            worker_error = error.what();
        }
        return std::numeric_limits<double>::infinity();
    }, bounds, config);
    if (!worker_error.empty()) throw std::runtime_error("synthetic hydropower worker failed: " + worker_error);
    const auto physical = worker.evaluate(result.x, definition, "optimized");
    std::cout << nlohmann::json{{"language", "cpp"}, {"scenario", definition.at("scenario")},
        {"baseline_objective", baseline.at("simulation").at("objective")},
        {"optimizer_objective", result.fun},
        {"objective", physical.at("simulation").at("objective")},
        {"energy_mwh", physical.at("simulation").at("energy_mwh")},
        {"level_penalty", physical.at("simulation").at("level_penalty")},
        {"target_power_mw", physical.at("power").at("target_power_mw")}}.dump() << '\n';
}
