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
#include <random>
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

struct BaselineRunConfig {
    std::uint64_t seed;
    std::size_t max_iter;
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

struct AlgoSpec {
    std::string name;
    std::string description;
};

std::vector<AlgoSpec> get_algorithms() {
    return {
        {"GIVP-full", "GRASP-ILS-VND-PR -- full hybrid pipeline (this work)"},
        {"GRASP-only", "GRASP-only baseline (Feo & Resende 1995)"},
        {"DE", "Differential Evolution -- native benchmark implementation (Storn & Price 1997)"},
        {"PSO", "Particle Swarm Optimization -- native benchmark implementation (Kennedy & "
                "Eberhart 1995)"},
        {"GA", "Genetic Algorithm -- native benchmark implementation (Holland 1975)"},
        {"CMA-ES", "CMA-ES style evolution strategy -- native benchmark implementation (Hansen & "
                   "Ostermeier 2001)"},
        {"SA", "Simulated Annealing -- native benchmark implementation (Kirkpatrick et al. 1983)"},
    };
}

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
        {"Rosenbrock", rosenbrock, [](std::size_t d) { return repeated_bounds(d, -5.0, 10.0); },
         0.0, "Rosenbrock (1960)"},
        {"Rastrigin", rastrigin, [](std::size_t d) { return repeated_bounds(d, -5.12, 5.12); }, 0.0,
         "Rastrigin (1974)"},
        {"Ackley", ackley, [](std::size_t d) { return repeated_bounds(d, -32.768, 32.768); }, 0.0,
         "Ackley (1987)"},
        {"Griewank", griewank, [](std::size_t d) { return repeated_bounds(d, -600.0, 600.0); }, 0.0,
         "Griewank (1981)"},
        {"Schwefel", schwefel, [](std::size_t d) { return repeated_bounds(d, -500.0, 500.0); }, 0.0,
         "Schwefel (1981)"},
    };
}

Vec sample_uniform(const Bounds &bounds, std::mt19937_64 &rng) {
    Vec x(bounds.size(), 0.0);
    for (std::size_t i = 0; i < bounds.size(); ++i) {
        std::uniform_real_distribution<double> dist(bounds[i].first, bounds[i].second);
        x[i] = dist(rng);
    }
    return x;
}

void clamp_to_bounds(Vec &x, const Bounds &bounds) {
    for (std::size_t i = 0; i < x.size(); ++i) {
        x[i] = std::clamp(x[i], bounds[i].first, bounds[i].second);
    }
}

double normal01(std::mt19937_64 &rng) {
    static thread_local std::normal_distribution<double> dist(0.0, 1.0);
    return dist(rng);
}

TrialResult run_de(const std::string &algorithm, const BenchFunc &bf, const Bounds &bounds,
                   const BaselineRunConfig &cfg) {
    const auto t0 = std::chrono::steady_clock::now();
    const std::size_t dim = bounds.size();
    const std::size_t pop_size = std::max<std::size_t>(20, 10 * dim);
    std::mt19937_64 rng(cfg.seed);
    std::uniform_real_distribution<double> unit(0.0, 1.0);

    std::vector<Vec> pop(pop_size);
    for (auto &x : pop) {
        x = sample_uniform(bounds, rng);
    }
    std::vector<double> fit(pop_size, 0.0);
    std::size_t nfev = 0;
    for (std::size_t i = 0; i < pop_size; ++i) {
        fit[i] = bf.func(pop[i]);
        ++nfev;
    }

    for (std::size_t it = 0; it < cfg.max_iter; ++it) {
        for (std::size_t i = 0; i < pop_size; ++i) {
            std::size_t r1, r2, r3;
            do {
                r1 = static_cast<std::size_t>(rng() % pop_size);
            } while (r1 == i);
            do {
                r2 = static_cast<std::size_t>(rng() % pop_size);
            } while (r2 == i || r2 == r1);
            do {
                r3 = static_cast<std::size_t>(rng() % pop_size);
            } while (r3 == i || r3 == r1 || r3 == r2);

            const double f = 0.8;
            const double cr = 0.9;
            const std::size_t jrand = static_cast<std::size_t>(rng() % dim);
            Vec trial = pop[i];
            for (std::size_t j = 0; j < dim; ++j) {
                if (unit(rng) < cr || j == jrand) {
                    trial[j] = pop[r1][j] + f * (pop[r2][j] - pop[r3][j]);
                }
            }
            clamp_to_bounds(trial, bounds);
            const double f_trial = bf.func(trial);
            ++nfev;
            if (f_trial < fit[i]) {
                pop[i] = std::move(trial);
                fit[i] = f_trial;
            }
        }
    }

    const double best = *std::min_element(fit.begin(), fit.end());
    const auto t1 = std::chrono::steady_clock::now();
    return {algorithm, bf.name, cfg.seed,
            best,      nfev,    std::chrono::duration<double>(t1 - t0).count()};
}

TrialResult run_pso(const std::string &algorithm, const BenchFunc &bf, const Bounds &bounds,
                    const BaselineRunConfig &cfg) {
    const auto t0 = std::chrono::steady_clock::now();
    const std::size_t dim = bounds.size();
    const std::size_t swarm_size = std::max<std::size_t>(20, 10 * dim);
    std::mt19937_64 rng(cfg.seed);
    std::uniform_real_distribution<double> unit(0.0, 1.0);

    std::vector<Vec> pos(swarm_size), vel(swarm_size, Vec(dim, 0.0)), pbest(swarm_size);
    std::vector<double> pbest_fit(swarm_size, std::numeric_limits<double>::infinity());
    std::size_t nfev = 0;

    for (std::size_t i = 0; i < swarm_size; ++i) {
        pos[i] = sample_uniform(bounds, rng);
        pbest[i] = pos[i];
        pbest_fit[i] = bf.func(pos[i]);
        ++nfev;
    }

    std::size_t gbest_idx = 0;
    for (std::size_t i = 1; i < swarm_size; ++i) {
        if (pbest_fit[i] < pbest_fit[gbest_idx]) {
            gbest_idx = i;
        }
    }
    Vec gbest = pbest[gbest_idx];
    double gbest_fit = pbest_fit[gbest_idx];

    const double w = 0.729;
    const double c1 = 1.494;
    const double c2 = 1.494;
    for (std::size_t it = 0; it < cfg.max_iter; ++it) {
        for (std::size_t i = 0; i < swarm_size; ++i) {
            for (std::size_t d = 0; d < dim; ++d) {
                const double r1 = unit(rng);
                const double r2 = unit(rng);
                vel[i][d] = w * vel[i][d] + c1 * r1 * (pbest[i][d] - pos[i][d]) +
                            c2 * r2 * (gbest[d] - pos[i][d]);
                pos[i][d] += vel[i][d];
            }
            clamp_to_bounds(pos[i], bounds);
            const double fit = bf.func(pos[i]);
            ++nfev;
            if (fit < pbest_fit[i]) {
                pbest[i] = pos[i];
                pbest_fit[i] = fit;
                if (fit < gbest_fit) {
                    gbest = pos[i];
                    gbest_fit = fit;
                }
            }
        }
    }

    const auto t1 = std::chrono::steady_clock::now();
    return {algorithm, bf.name, cfg.seed,
            gbest_fit, nfev,    std::chrono::duration<double>(t1 - t0).count()};
}

TrialResult run_ga(const std::string &algorithm, const BenchFunc &bf, const Bounds &bounds,
                   const BaselineRunConfig &cfg) {
    const auto t0 = std::chrono::steady_clock::now();
    const std::size_t dim = bounds.size();
    const std::size_t pop_size = std::max<std::size_t>(30, 12 * dim);
    std::mt19937_64 rng(cfg.seed);
    std::uniform_real_distribution<double> unit(0.0, 1.0);

    auto tournament = [&](const std::vector<double> &fit) {
        const std::size_t a = static_cast<std::size_t>(rng() % fit.size());
        const std::size_t b = static_cast<std::size_t>(rng() % fit.size());
        const std::size_t c = static_cast<std::size_t>(rng() % fit.size());
        std::size_t best = a;
        if (fit[b] < fit[best]) {
            best = b;
        }
        if (fit[c] < fit[best]) {
            best = c;
        }
        return best;
    };

    std::vector<Vec> pop(pop_size);
    for (auto &x : pop) {
        x = sample_uniform(bounds, rng);
    }
    std::vector<double> fit(pop_size, 0.0);
    std::size_t nfev = 0;
    for (std::size_t i = 0; i < pop_size; ++i) {
        fit[i] = bf.func(pop[i]);
        ++nfev;
    }

    for (std::size_t it = 0; it < cfg.max_iter; ++it) {
        std::vector<std::size_t> order(pop_size);
        std::iota(order.begin(), order.end(), 0);
        std::sort(order.begin(), order.end(),
                  [&](std::size_t a, std::size_t b) { return fit[a] < fit[b]; });

        std::vector<Vec> next;
        next.reserve(pop_size);
        next.push_back(pop[order.front()]); // elitism
        while (next.size() < pop_size) {
            const std::size_t p1 = tournament(fit);
            const std::size_t p2 = tournament(fit);
            Vec child(dim, 0.0);
            for (std::size_t d = 0; d < dim; ++d) {
                const double beta = unit(rng);
                child[d] = beta * pop[p1][d] + (1.0 - beta) * pop[p2][d];
                if (unit(rng) < 0.1) {
                    const double scale = (bounds[d].second - bounds[d].first) * 0.1;
                    child[d] += normal01(rng) * scale;
                }
            }
            clamp_to_bounds(child, bounds);
            next.push_back(std::move(child));
        }
        pop = std::move(next);

        for (std::size_t i = 0; i < pop_size; ++i) {
            fit[i] = bf.func(pop[i]);
            ++nfev;
        }
    }

    const double best = *std::min_element(fit.begin(), fit.end());
    const auto t1 = std::chrono::steady_clock::now();
    return {algorithm, bf.name, cfg.seed,
            best,      nfev,    std::chrono::duration<double>(t1 - t0).count()};
}

TrialResult run_cmaes_style(const std::string &algorithm, const BenchFunc &bf, const Bounds &bounds,
                            const BaselineRunConfig &cfg) {
    const auto t0 = std::chrono::steady_clock::now();
    const std::size_t dim = bounds.size();
    const std::size_t lambda = std::max<std::size_t>(
        6, 4 + static_cast<std::size_t>(3.0 * std::log(static_cast<double>(dim))));
    const std::size_t mu = std::max<std::size_t>(2, lambda / 2);
    std::mt19937_64 rng(cfg.seed);

    Vec mean = sample_uniform(bounds, rng);
    double avg_range = 0.0;
    for (const auto &b : bounds) {
        avg_range += (b.second - b.first);
    }
    avg_range /= static_cast<double>(dim);
    double sigma = std::max(1e-8, avg_range * 0.3);
    std::size_t nfev = 0;
    double best = std::numeric_limits<double>::infinity();

    for (std::size_t it = 0; it < cfg.max_iter; ++it) {
        std::vector<std::pair<Vec, double>> pop;
        pop.reserve(lambda);
        for (std::size_t k = 0; k < lambda; ++k) {
            Vec x(dim, 0.0);
            for (std::size_t d = 0; d < dim; ++d) {
                x[d] = mean[d] + sigma * normal01(rng);
            }
            clamp_to_bounds(x, bounds);
            const double f = bf.func(x);
            ++nfev;
            best = std::min(best, f);
            pop.push_back({std::move(x), f});
        }
        std::sort(pop.begin(), pop.end(),
                  [](const auto &a, const auto &b) { return a.second < b.second; });

        Vec new_mean(dim, 0.0);
        double wsum = 0.0;
        for (std::size_t r = 0; r < mu; ++r) {
            const double w =
                std::log(static_cast<double>(mu) + 0.5) - std::log(static_cast<double>(r + 1));
            wsum += w;
            for (std::size_t d = 0; d < dim; ++d) {
                new_mean[d] += w * pop[r].first[d];
            }
        }
        for (double &v : new_mean) {
            v /= wsum;
        }
        mean = std::move(new_mean);
        sigma *= (pop.front().second <= best ? 1.03 : 0.97);
        sigma = std::clamp(sigma, 1e-12, std::max(1e-12, avg_range));
    }

    const auto t1 = std::chrono::steady_clock::now();
    return {algorithm, bf.name, cfg.seed,
            best,      nfev,    std::chrono::duration<double>(t1 - t0).count()};
}

TrialResult run_sa(const std::string &algorithm, const BenchFunc &bf, const Bounds &bounds,
                   const BaselineRunConfig &cfg) {
    const auto t0 = std::chrono::steady_clock::now();
    const std::size_t dim = bounds.size();
    std::mt19937_64 rng(cfg.seed);
    std::uniform_real_distribution<double> unit(0.0, 1.0);

    Vec x = sample_uniform(bounds, rng);
    double fx = bf.func(x);
    double best = fx;
    std::size_t nfev = 1;
    const std::size_t steps = std::max<std::size_t>(100, cfg.max_iter * 30);
    const double t_init = 1.0;
    const double t_final = 1e-3;

    for (std::size_t k = 0; k < steps; ++k) {
        const double frac = static_cast<double>(k) / static_cast<double>(steps);
        const double temp = t_init * std::pow(t_final / t_init, frac);
        Vec y = x;
        for (std::size_t d = 0; d < dim; ++d) {
            const double scale = (bounds[d].second - bounds[d].first) * 0.1;
            y[d] += normal01(rng) * scale;
        }
        clamp_to_bounds(y, bounds);
        const double fy = bf.func(y);
        ++nfev;
        const double delta = fy - fx;
        if (delta <= 0.0 || unit(rng) < std::exp(-delta / std::max(1e-12, temp))) {
            x = std::move(y);
            fx = fy;
            best = std::min(best, fx);
        }
    }

    const auto t1 = std::chrono::steady_clock::now();
    return {algorithm, bf.name, cfg.seed,
            best,      nfev,    std::chrono::duration<double>(t1 - t0).count()};
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
        << json_escape(row.algorithm) << "\",\"n_runs\":" << row.n_runs << ",\"mean\":" << row.mean
        << ",\"std\":" << row.std << ",\"best\":" << row.best << ",\"median\":" << row.median
        << ",\"worst\":" << row.worst << ",\"nfev_mean\":" << row.nfev_mean << "}";
    return out.str();
}

std::vector<SummaryRow> build_summary(const std::vector<TrialResult> &rows,
                                      const std::vector<BenchFunc> &funcs) {
    std::vector<SummaryRow> summary;
    summary.reserve(funcs.size() * 2);
    std::vector<std::string> algorithms;
    for (const auto &row : rows) {
        if (std::find(algorithms.begin(), algorithms.end(), row.algorithm) == algorithms.end()) {
            algorithms.push_back(row.algorithm);
        }
    }
    for (const auto &bf : funcs) {
        for (const auto &algorithm : algorithms) {
            std::vector<double> values;
            std::vector<double> nfevs;
            for (const auto &row : rows) {
                if (row.function == bf.name && row.algorithm == algorithm) {
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
            const double median =
                values.size() % 2 == 0 ? (values[mid - 1] + values[mid]) / 2.0 : values[mid];
            const double nfev_mean = std::accumulate(nfevs.begin(), nfevs.end(), 0.0) /
                                     static_cast<double>(nfevs.size());
            summary.push_back({bf.name, algorithm, values.size(), mean, std, values.front(), median,
                               values.back(), nfev_mean});
        }
    }
    return summary;
}

void write_json(const std::string &path, const std::vector<TrialResult> &rows,
                const std::vector<BenchFunc> &funcs, std::size_t dims, std::size_t n_runs,
                const std::vector<std::string> &algorithms) {
    std::filesystem::path out_path(path);
    if (!out_path.parent_path().empty()) {
        std::filesystem::create_directories(out_path.parent_path());
    }

    std::ofstream out(path, std::ios::out | std::ios::trunc);
    const auto summary = build_summary(rows, funcs);

    out << "{\n";
    out << "  \"metadata\": {" << "\"schema_version\":\"benchmark-schema-v1\","
        << "\"givp_version\":\"1.0.0\"," << "\"dims\":" << dims << "," << "\"n_runs\":" << n_runs
        << "," << "\"algorithms\":[";
    for (std::size_t i = 0; i < algorithms.size(); ++i) {
        out << "\"" << json_escape(algorithms[i]) << "\"";
        if (i + 1 < algorithms.size()) {
            out << ",";
        }
    }
    out << "]," << "\"functions\":[";
    for (std::size_t i = 0; i < funcs.size(); ++i) {
        out << "\"" << json_escape(funcs[i].name) << "\"";
        if (i + 1 < funcs.size()) {
            out << ",";
        }
    }
    out << "],\"problem_references\":{";
    for (std::size_t i = 0; i < funcs.size(); ++i) {
        out << "\"" << json_escape(funcs[i].name) << "\":\"" << json_escape(funcs[i].reference)
            << "\"";
        if (i + 1 < funcs.size()) {
            out << ",";
        }
    }
    const auto specs = get_algorithms();
    out << "},\"algo_descriptions\":{";
    bool first_algo = true;
    for (const auto &algorithm : algorithms) {
        for (const auto &spec : specs) {
            if (spec.name == algorithm) {
                if (!first_algo) {
                    out << ",";
                }
                out << "\"" << json_escape(spec.name) << "\":\"" << json_escape(spec.description)
                    << "\"";
                first_algo = false;
                break;
            }
        }
    }
    out << "}},\n";
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
    std::size_t max_iter = 50;
    double time_limit = 0.0;
    std::vector<std::string> algorithms = {"GIVP-full", "DE", "PSO", "GA", "CMA-ES", "SA"};
    std::string output = "cpp/benchmarks/literature_comparison.json";
    bool verbose = false;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--n-runs" && i + 1 < argc) {
            n_runs = static_cast<std::size_t>(std::stoul(argv[++i]));
        } else if (arg == "--dims" && i + 1 < argc) {
            dims = static_cast<std::size_t>(std::stoul(argv[++i]));
        } else if (arg == "--max-iter" && i + 1 < argc) {
            max_iter = static_cast<std::size_t>(std::stoul(argv[++i]));
        } else if (arg == "--time-limit" && i + 1 < argc) {
            time_limit = std::stod(argv[++i]);
        } else if (arg == "--algorithms") {
            algorithms.clear();
            while (i + 1 < argc) {
                const std::string next = argv[i + 1];
                if (next.rfind("--", 0) == 0) {
                    break;
                }
                algorithms.push_back(next);
                ++i;
            }
            if (algorithms.empty()) {
                algorithms = {"GIVP-full", "DE", "PSO", "GA", "CMA-ES", "SA"};
            }
        } else if (arg == "--output" && i + 1 < argc) {
            output = argv[++i];
        } else if (arg == "--verbose") {
            verbose = true;
        }
    }

    std::cout << "GIVP Literature Comparison (C++)\n";
    std::cout << "  dims=" << dims << "  runs/function=" << n_runs << "  algorithms=";
    for (std::size_t i = 0; i < algorithms.size(); ++i) {
        std::cout << algorithms[i] << (i + 1 < algorithms.size() ? "," : "");
    }
    std::cout << "\n";
    std::cout << "  output -> " << output << "\n\n";

    const auto funcs = get_functions();
    std::vector<TrialResult> rows;
    rows.reserve(funcs.size() * n_runs * algorithms.size());

    const auto specs = get_algorithms();
    std::vector<std::string> active_algorithms;
    for (const auto &algorithm : algorithms) {
        bool known = false;
        for (const auto &spec : specs) {
            if (spec.name == algorithm) {
                known = true;
                active_algorithms.push_back(algorithm);
                break;
            }
        }
        if (!known) {
            std::cerr << "[warn] unknown algorithm '" << algorithm << "': skipping\n";
        }
    }

    for (const auto &algorithm : active_algorithms) {
        for (const auto &bf : funcs) {
            const Bounds bounds = bf.bounds_fn(dims);
            std::vector<double> best_values;
            best_values.reserve(n_runs);

            for (std::size_t s = 0; s < n_runs; ++s) {
                TrialResult trial;
                const BaselineRunConfig baseline_cfg{static_cast<std::uint64_t>(s), max_iter};
                if (algorithm == "DE") {
                    trial = run_de(algorithm, bf, bounds, baseline_cfg);
                } else if (algorithm == "PSO") {
                    trial = run_pso(algorithm, bf, bounds, baseline_cfg);
                } else if (algorithm == "GA") {
                    trial = run_ga(algorithm, bf, bounds, baseline_cfg);
                } else if (algorithm == "CMA-ES") {
                    trial = run_cmaes_style(algorithm, bf, bounds, baseline_cfg);
                } else if (algorithm == "SA") {
                    trial = run_sa(algorithm, bf, bounds, baseline_cfg);
                } else {
                    givp::GivpConfig cfg;
                    cfg.max_iterations = max_iter;
                    cfg.seed = static_cast<std::uint64_t>(s);
                    cfg.integer_split = dims;
                    cfg.time_limit = time_limit;

                    if (algorithm == "GRASP-only") {
                        cfg.adaptive_alpha = false;
                        cfg.vnd_iterations = 1;
                        cfg.ils_iterations = 1;
                        cfg.perturbation_strength = 1;
                        cfg.use_elite_pool = false;
                        cfg.use_convergence_monitor = false;
                        cfg.early_stop_threshold = max_iter;
                    }

                    const auto t0 = std::chrono::steady_clock::now();
                    const auto result = givp::givp(bf.func, bounds, cfg);
                    const auto t1 = std::chrono::steady_clock::now();
                    trial = {
                        algorithm,  bf.name,     static_cast<std::uint64_t>(s),
                        result.fun, result.nfev, std::chrono::duration<double>(t1 - t0).count()};
                }

                rows.push_back(trial);
                best_values.push_back(trial.fun);

                if (verbose) {
                    std::cout << "  " << algorithm << " " << bf.name << " seed=" << s
                              << " best=" << std::scientific << trial.fun << " nfev=" << trial.nfev
                              << " " << std::fixed << std::setprecision(2) << trial.elapsed_s
                              << "s\n";
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

            std::cout << "  " << algorithm << " " << bf.name << " mean=" << std::scientific << mean
                      << " std=" << stddev << " best=" << best
                      << " gap=" << std::abs(best - bf.optimum) << "\n";
        }
    }

    write_json(output, rows, funcs, dims, n_runs, active_algorithms);
    std::cout << "\nResults written to " << output << "\n";
    return 0;
} catch (const std::exception &e) {
    std::cerr << "literature comparison fatal error: " << e.what() << "\n";
    return 1;
} catch (...) {
    std::cerr << "literature comparison fatal error: unknown exception\n";
    return 1;
}
