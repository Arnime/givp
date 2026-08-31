#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#include <nlohmann/json.hpp>

namespace {

std::string shell_quote(const std::string& value) {
#if defined(_WIN32)
    std::string quoted{"\""};
    for (const char character : value) {
        quoted += character == '"' ? "\\\"" : std::string(1, character);
    }
    return quoted + "\"";
#else
    std::string quoted{"'"};
    for (const char character : value) {
        quoted += character == '\'' ? "'\\''" : std::string(1, character);
    }
    return quoted + "'";
#endif
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc < 2 || argc > 3) {
        throw std::runtime_error(
            "usage: synthetic_hydropower_client <batch-request.json> [response.json]"
        );
    }
    std::ifstream input(argv[1]);
    if (!input) {
        throw std::runtime_error("unable to read the batch request");
    }
    nlohmann::json request;
    input >> request;
    if (request.at("schema_version") != "synthetic-hydropower/v1") {
        throw std::runtime_error("unsupported hydropower protocol version");
    }
    const char* command_path = std::getenv("SYNTHETIC_HYDROPOWER_COMMAND");
    const std::string executable =
        command_path == nullptr ? "synthetic-hydropower" : command_path;
    const bool keep_response = argc == 3;
    const auto response_path = keep_response
        ? std::filesystem::path(argv[2])
        : std::filesystem::temp_directory_path() /
            ("synthetic_hydropower_response_" +
             std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) +
             ".json");
    const auto output_parent = response_path.parent_path();
    if (!output_parent.empty()) {
        std::filesystem::create_directories(output_parent);
    }
    const std::string command = shell_quote(executable) + " balance --request " +
        shell_quote(argv[1]) + " --output " + shell_quote(response_path.string());
    if (std::system(command.c_str()) != 0) {
        throw std::runtime_error("synthetic-hydropower balance evaluation failed");
    }
    std::ifstream response_input(response_path);
    if (!response_input) {
        throw std::runtime_error("unable to read the worker response");
    }
    nlohmann::json response;
    response_input >> response;
    if (!keep_response) {
        std::error_code remove_error;
        std::filesystem::remove(response_path, remove_error);
    }
    if (response.contains("error")) {
        throw std::runtime_error(
            response.at("error").at("message").get<std::string>()
        );
    }
    std::cout << "received " << response.at("results").size() << " hydraulic result(s)\n";
}
