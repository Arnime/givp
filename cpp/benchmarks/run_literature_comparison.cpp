// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

#include <givp/givp.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <givp/config.hpp>

namespace {

using Vec = std::vector<double>;
using Bounds = std::vector<std::pair<double, double>>;

struct BenchFunc {
    std::string name;
    double (*func)(const Vec &);
    Bounds (*bounds_fn)(std::size_t);
    double optimum;
    std::string reference;
};

struct TrialResult {
    std::string algorithm;
    std::string function;
    std::uint64_t seed;
    double fun;
    std::size_t nfev;
    double elapsed_s;
};

struct SummaryRow {
    std::string function;
    std::string algorithm;
    std::size_t n_runs;
    double mean;
    double std;
    double best;
    double median;
    double worst;
    double nfev_mean;
};

double sphere(const Vec &x) {
    double s = 0.0;
    for (double v : x)
        s += v * v;
    return s;
}

double rosenbrock(const Vec &x) {
    double s = 0.0;
    for (std::size_t i = 0; i + 1 < x.size(); ++i) {
        const double a = x[i + 1] - x[i] * x[i];
        const double b = 1.0 - x[i];
        s += 100.0 * a * a + b * b;
    }
    return s;
}

double rastrigin(const Vec &x) {
    constexpr double pi = 3.14159265358979323846;
    double s = 10.0 * static_cast<double>(x.size());
    for (double v : x)
        s += v * v - 10.0 * std::cos(2.0 * pi * v);
    return s;
}

double ackley(const Vec &x) {
    constexpr double pi = 3.14159265358979323846;
    const double n = static_cast<double>(x.size());
    double sum_sq = 0.0;
    double sum_cos = 0.0;
    for (double v : x) {
        sum_sq += v * v;
        sum_cos += std::cos(2.0 * pi * v);
    }
    sum_sq /= n;
    sum_cos /= n;
    return -20.0 * std::exp(-0.2 * std::sqrt(sum_sq)) - std::exp(sum_cos) + 20.0 + std::exp(1.0);
}

double griewank(const Vec &x) {
    double sum_sq = 0.0;
    double prod = 1.0;
    for (std::size_t i = 0; i < x.size(); ++i) {
        const double v = x[i];
        sum_sq += v * v;
        prod *= std::cos(v / std::sqrt(static_cast<double>(i + 1)));
    }
    return 1.0 + sum_sq / 4000.0 - prod;
}

double schwefel(const Vec &x) {
    const double n = static_cast<double>(x.size());
    double s = 0.0;
    for (double v : x)
        s += v * std::sin(std::sqrt(std::abs(v)));
    return 418.9829 * n - s;
}

Bounds repeated_bounds(std::size_t d, double lo, double hi) {
    return Bounds(d, std::make_pair(lo, hi));
}

std::vector<BenchFunc> get_functions() {
    return {
        {"Sphere", sphere, [](std::size_t d) { return repeated_bounds(d, -5.12, 5.12); }, 0.0,
         "De Jong (1975)"},
        {"Rosenbrock", rosenbrock,
         [](std::size_t d) { return repeated_bounds(d, -5.0, 10.0); }, 0.0,
         "Rosenbrock (1960)"},
        {"Rastrigin", rastrigin,
         [](std::size_t d) { return repeated_bounds(d, -5.12, 5.12); }, 0.0,
         "Rastrigin (1974)"},
        {"Ackley", ackley, [](std::size_t d) { return repeated_bounds(d, -32.768, 32.768); }, 0.0,
         "Ackley (1987)"},
        {"Griewank", griewank,
         [](std::size_t d) { return repeated_bounds(d, -600.0, 600.0); }, 0.0,
         "Griewank (1981)"},
        {"Schwefel", schwefel,
         [](std::size_t d) { return repeated_bounds(d, -500.0, 500.0); }, 0.0,
         "Schwefel (1981)"},
    };
}

std::string json_escape(const std::string &input) {
    std::string out;
    out.reserve(input.size() + 8);
    for (char c : input) {
        if (c == '\\') {
            out += "\\\\";
        } else if (c == '"') {
            out += "\\\"";
        } else {
            out.push_back(c);
        }
    }
    return out;
}

std::string format_run_json(const TrialResult &row) {
    std::ostringstream out;
    out << std::scientific << std::setprecision(10);
    out << "{\"algorithm\":\"" << json_escape(row.algorithm) << "\",\"function\":\""
        << json_escape(row.function) << "\",\"seed\":" << row.seed << ",\"fun\":" << row.fun
        << ",\"nfev\":" << row.nfev << ",\"time_s\":" << std::fixed << std::setprecision(4)
        << row.elapsed_s << "}";
    return out.str();
}

std::string format_summary_json(const SummaryRow &row) {
    std::ostringstream out;
    out << std::scientific << std::setprecision(10);
    out << "{\"function\":\"" << json_escape(row.function) << "\",\"algorithm\":\""
        << json_escape(row.algorithm) << "\",\"n_runs\":" << row.n_runs << ",\"mean\":"
        << row.mean << ",\"std\":" << row.std << ",\"best\":" << row.best
        << ",\"median\":" << row.median << ",\"worst\":" << row.worst
        << ",\"nfev_mean\":" << row.nfev_mean << "}";
    return out.str();
}

std::vector<SummaryRow> build_summary(
    const std::vector<TrialResult> &rows,
    const std::vector<BenchFunc> &funcs
) {
    std::vector<SummaryRow> summary;
    summary.reserve(funcs.size());
    for (const auto &bf : funcs) {
        std::vector<double> values;
        std::vector<double> nfevs;
        for (const auto &row : rows) {
            if (row.function == bf.name && row.algorithm == "GIVP-full") {
                values.push_back(row.fun);
                nfevs.push_back(static_cast<double>(row.nfev));
            }
        }
        if (values.empty()) {
            continue;
        }
        std::sort(values.begin(), values.end());
        const double mean = std::accumulate(values.begin(), values.end(), 0.0) /
                            static_cast<double>(values.size());
        double sum_sq = 0.0;
        for (double value : values) {
            const double delta = value - mean;
            sum_sq += delta * delta;
        }
        const double std = values.size() > 1
                               ? std::sqrt(sum_sq / static_cast<double>(values.size() - 1))
                               : 0.0;
        const std::size_t mid = values.size() / 2;
        const double median = values.size() % 2 == 0 ? (values[mid - 1] + values[mid]) / 2.0
                                                      : values[mid];
        const double nfev_mean = std::accumulate(nfevs.begin(), nfevs.end(), 0.0) /
                                 static_cast<double>(nfevs.size());
        summary.push_back({bf.name, "GIVP-full", values.size(), mean, std, values.front(),
                           median, values.back(), nfev_mean});
    }
    return summary;
}

void write_json(
    const std::string &path,
    const std::vector<TrialResult> &rows,
    const std::vector<BenchFunc> &funcs,
    std::size_t dims,
    std::size_t n_runs
) {
    std::filesystem::path out_path(path);
    if (!out_path.parent_path().empty()) {
        std::filesystem::create_directories(out_path.parent_path());
    }

    std::ofstream out(path, std::ios::out | std::ios::trunc);
    const auto summary = build_summary(rows, funcs);

    out << "{\n";
    out << "  \"metadata\": {"
        << "\"schema_version\":\"benchmark-schema-v1\"," 
        << "\"givp_version\":\"1.0.0\"," 
        << "\"dims\":" << dims << ","
        << "\"n_runs\":" << n_runs << ","
        << "\"algorithms\":[\"GIVP-full\"],"
        << "\"functions\":[";
    for (std::size_t i = 0; i < funcs.size(); ++i) {
        out << "\"" << json_escape(funcs[i].name) << "\"";
        if (i + 1 < funcs.size()) {
            out << ",";
        }
    }
    out << "],\"problem_references\":{";
    for (std::size_t i = 0; i < funcs.size(); ++i) {
        out << "\"" << json_escape(funcs[i].name) << "\":\""
            << json_escape(funcs[i].reference) << "\"";
        if (i + 1 < funcs.size()) {
            out << ",";
        }
    }
    out << "},\"algo_descriptions\":{\"GIVP-full\":\"GRASP-ILS-VND-PR -- full hybrid pipeline (this work)\"}},\n";
    out << "  \"runs\": [\n";
    for (std::size_t i = 0; i < rows.size(); ++i) {
        out << "    " << format_run_json(rows[i]) << (i + 1 < rows.size() ? "," : "") << "\n";
    }
    out << "  ],\n";
    out << "  \"summary\": [\n";
    for (std::size_t i = 0; i < summary.size(); ++i) {
        out << "    " << format_summary_json(summary[i]) << (i + 1 < summary.size() ? "," : "")
            << "\n";
    }
    out << "  ],\n";
    out << "  \"stats\": [\n";
    for (std::size_t i = 0; i < summary.size(); ++i) {
        out << "    " << format_summary_json(summary[i]) << (i + 1 < summary.size() ? "," : "")
            << "\n";
    }
    out << "  ]\n";
    out << "}\n";
}

} // namespace

int main(int argc, char **argv) try {
    std::size_t n_runs = 30;
    std::size_t dims = 10;
    std::string output = "cpp/benchmarks/literature_comparison.json";
    bool verbose = false;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--n-runs" && i + 1 < argc) {
            n_runs = static_cast<std::size_t>(std::stoul(argv[++i]));
        } else if (arg == "--dims" && i + 1 < argc) {
            dims = static_cast<std::size_t>(std::stoul(argv[++i]));
        } else if (arg == "--output" && i + 1 < argc) {
            output = argv[++i];
        } else if (arg == "--verbose") {
            verbose = true;
        }
    }

    std::cout << "GIVP Literature Comparison (C++)\n";
    std::cout << "  dims=" << dims << "  runs/function=" << n_runs << "\n";
    std::cout << "  output -> " << output << "\n\n";

    const auto funcs = get_functions();
    std::vector<TrialResult> rows;
    rows.reserve(funcs.size() * n_runs);

    for (const auto &bf : funcs) {
        const Bounds bounds = bf.bounds_fn(dims);
        std::vector<double> best_values;
        best_values.reserve(n_runs);

        for (std::size_t s = 0; s < n_runs; ++s) {
            givp::GivpConfig cfg;
            cfg.max_iterations = 50;
            cfg.seed = static_cast<std::uint64_t>(s);
            cfg.integer_split = dims;

            const auto t0 = std::chrono::steady_clock::now();
            const auto result = givp::givp(bf.func, bounds, cfg);
            const auto t1 = std::chrono::steady_clock::now();
            const double elapsed = std::chrono::duration<double>(t1 - t0).count();

            rows.push_back({"GIVP-full", bf.name, static_cast<std::uint64_t>(s), result.fun,
                            result.nfev, elapsed});
            best_values.push_back(result.fun);

            if (verbose) {
                std::cout << "  " << bf.name << " seed=" << s << " best=" << std::scientific
                          << result.fun << " nfev=" << result.nfev << " " << std::fixed
                          << std::setprecision(2) << elapsed << "s\n";
            }
        }

        double mean = 0.0;
        for (double v : best_values)
            mean += v;
        mean /= static_cast<double>(best_values.size());

        double var = 0.0;
        for (double v : best_values) {
            const double d = v - mean;
            var += d * d;
        }
        var /= static_cast<double>(best_values.size());
        const double stddev = std::sqrt(var);

        double best = std::numeric_limits<double>::infinity();
        for (double v : best_values)
            best = std::min(best, v);

        std::cout << "  " << bf.name << " mean=" << std::scientific << mean << " std=" << stddev
                  << " best=" << best << " gap=" << std::abs(best - bf.optimum) << "\n";
    }

    write_json(output, rows, funcs, dims, n_runs);
    std::cout << "\nResults written to " << output << "\n";
    return 0;
} catch (const std::exception &e) {
    std::cerr << "literature comparison fatal error: " << e.what() << "\n";
    return 1;
} catch (...) {
    std::cerr << "literature comparison fatal error: unknown exception\n";
    return 1;
}
