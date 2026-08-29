#include <array>
#include <cstdlib>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#include <nlohmann/json.hpp>

#if defined(_WIN32)
#define popen _popen
#define pclose _pclose
#endif

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
    if (argc != 2) {
        throw std::runtime_error("usage: synthetic_hydropower_client <batch-request.json>");
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
#if defined(_WIN32)
    const std::string command =
        "type " + shell_quote(argv[1]) + " | " + shell_quote(executable) + " worker";
#else
    const std::string command =
        "cat " + shell_quote(argv[1]) + " | " + shell_quote(executable) + " worker";
#endif
    std::array<char, 512> buffer{};
    std::string response_text;
    FILE* worker = popen(command.c_str(), "r");
    if (worker == nullptr) {
        throw std::runtime_error("unable to start synthetic-hydropower worker");
    }
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), worker) != nullptr) {
        response_text += buffer.data();
    }
    pclose(worker);
    const auto response = nlohmann::json::parse(response_text);
    if (response.contains("error")) {
        throw std::runtime_error(
            response.at("error").at("message").get<std::string>()
        );
    }
    std::cout << "received " << response.at("results").size() << " hydraulic result(s)\n";
}
