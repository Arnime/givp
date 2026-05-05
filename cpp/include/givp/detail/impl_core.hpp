// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT
#pragma once

#include <atomic>
#include <chrono>
#include <cmath>
#include <future>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include "../config.hpp"
#include "../exceptions.hpp"
#include "../result.hpp"
#include "cache.hpp"
#include "convergence.hpp"
#include "elite.hpp"
#include "grasp.hpp"
#include "helpers.hpp"
#include "ils.hpp"
#include "pr.hpp"
#include "vnd.hpp"

namespace givp::detail {

inline std::pair<std::vector<double>, std::vector<double>>
validate_bounds(const std::vector<std::pair<double, double>> &bounds,
                const std::optional<std::vector<double>> &initial_guess) {

    if (bounds.empty())
        throw InvalidBounds("bounds cannot be empty");

    std::vector<double> lower, upper;
    lower.reserve(bounds.size());
    upper.reserve(bounds.size());

    for (std::size_t i = 0; i < bounds.size(); ++i) {
        double lo = bounds[i].first, hi = bounds[i].second;
        if (lo >= hi)
            throw InvalidBounds("lower >= upper at index " + std::to_string(i) + ": " +
                                std::to_string(lo) + " >= " + std::to_string(hi));
        if (!std::isfinite(lo) || !std::isfinite(hi))
            throw InvalidBounds("non-finite bound at index " + std::to_string(i));
        lower.push_back(lo);
        upper.push_back(hi);
    }

    if (initial_guess) {
        if (initial_guess->size() != bounds.size())
            throw InvalidInitialGuess("expected " + std::to_string(bounds.size()) +
                                      " values, got " + std::to_string(initial_guess->size()));
        for (std::size_t i = 0; i < initial_guess->size(); ++i) {
            double v = (*initial_guess)[i];
            if (v < bounds[i].first || v > bounds[i].second)
                throw InvalidInitialGuess("value " + std::to_string(v) + " out of bounds [" +
                                          std::to_string(bounds[i].first) + ", " +
                                          std::to_string(bounds[i].second) + "] at index " +
                                          std::to_string(i));
        }
    }
    return {std::move(lower), std::move(upper)};
}

template <typename F>
static void
do_path_relinking(const F &func, const ElitePool &elite_pool, std::vector<double> &best_solution,
                  double &best_cost, std::size_t half, const std::vector<double> &lower,
                  const std::vector<double> &upper, std::size_t vnd_iterations,
                  std::optional<EvaluationCache> &cache, Rng &rng, const Deadline &deadline) {

    const auto &all = elite_pool.get_all();
    std::size_t max_pairs = std::min(std::size_t{3}, all.size());

    for (std::size_t i = 0; i < max_pairs; ++i) {
        for (std::size_t j = i + 1; j < std::min(all.size(), i + 4); ++j) {
            if (expired(deadline))
                return;

            auto [pr_sol, pr_cost] = bidirectional_path_relinking(func, all[i].first, all[j].first,
                                                                  half, cache, rng, deadline);

            double refined_cost = local_search_vnd(func, pr_sol, pr_cost, half, lower, upper,
                                                   vnd_iterations / 2, cache, rng, deadline);

            if (refined_cost < best_cost) {
                best_cost = refined_cost;
                best_solution = std::move(pr_sol);
            }
        }
    }
}

struct CandidateCost {
    std::vector<double> candidate;
    double cost;
};

struct ProblemShape {
    std::size_t num_vars;
    std::size_t half;
};

template <typename F>
static std::pair<std::vector<double>, double>
initialize_best_solution(const F &wrapped, const GivpConfig &config, const ProblemShape &shape,
                         const std::vector<double> &lower,
                         const std::vector<double> &upper,
                         std::optional<EvaluationCache> &cache, Rng &rng,
                         const Deadline &deadline) {
    if (config.initial_guess) {
        std::vector<double> best_solution = *config.initial_guess;
        normalize_integer_tail(best_solution, shape.half);
        double best_cost = evaluate_with_cache(best_solution, wrapped, cache, shape.half);
        return {std::move(best_solution), best_cost};
    }

    auto child = rng.child();
    const GraspConstructParams init_params{nullptr, config.alpha, shape.half,
                                           config.num_candidates_per_step};
    return construct_grasp(shape.num_vars, lower, upper, wrapped, init_params, cache, child,
                           deadline);
}

template <typename F>
static CandidateCost
run_single_worker_iteration(const F &wrapped, const GivpConfig &config,
                            const ProblemShape &shape, const std::vector<double> &lower,
                            const std::vector<double> &upper,
                            const std::vector<double> *initial_guess_ptr,
                            std::optional<EvaluationCache> &cache, Rng &rng,
                            const Deadline &deadline, double alpha) {
    const GraspConstructParams grasp_params{initial_guess_ptr, alpha, shape.half,
                                            config.num_candidates_per_step};
    auto grasp_result =
        construct_grasp(shape.num_vars, lower, upper, wrapped, grasp_params, cache, rng, deadline);
    std::vector<double> candidate = std::move(grasp_result.first);

    double grasp_eval = evaluate_with_cache(candidate, wrapped, cache, shape.half);
    double vnd_cost = local_search_vnd(wrapped, candidate, grasp_eval, shape.half, lower, upper,
                                       config.vnd_iterations, cache, rng, deadline);
    double ils_cost = ils_search(wrapped, candidate, vnd_cost, shape.half, lower, upper,
                                 config.ils_iterations, config.vnd_iterations,
                                 config.perturbation_strength, cache, rng, deadline);
    return {std::move(candidate), ils_cost};
}

template <typename F>
static CandidateCost
run_multi_worker_iteration(const F &wrapped, const GivpConfig &config,
                           const ProblemShape &shape, const std::vector<double> &lower,
                           const std::vector<double> &upper,
                           const std::vector<double> *initial_guess_ptr, Rng &rng,
                           const Deadline &deadline, double alpha) {
    struct WorkerResult {
        std::vector<double> candidate;
        double cost;
    };

    std::vector<std::future<WorkerResult>> futures;
    futures.reserve(config.n_workers);

    for (std::size_t worker = 0; worker < config.n_workers; ++worker) {
        auto worker_rng = rng.child();
        const std::vector<double> *worker_ig = (worker == 0) ? initial_guess_ptr : nullptr;

        futures.push_back(std::async(
            std::launch::async,
            [&wrapped, &config, &lower, &upper, shape, alpha, deadline, worker_rng,
             worker_ig]() mutable -> WorkerResult {
                std::optional<EvaluationCache> local_cache;
                const GraspConstructParams worker_params{worker_ig, alpha, shape.half,
                                                         config.num_candidates_per_step};

                auto grasp_result =
                    construct_grasp(shape.num_vars, lower, upper, wrapped, worker_params,
                                    local_cache, worker_rng, deadline);
                std::vector<double> local_candidate = std::move(grasp_result.first);

                double grasp_eval =
                    evaluate_with_cache(local_candidate, wrapped, local_cache, shape.half);
                double vnd_cost =
                    local_search_vnd(wrapped, local_candidate, grasp_eval, shape.half, lower,
                                     upper,
                                     config.vnd_iterations, local_cache, worker_rng, deadline);
                double local_cost =
                    ils_search(wrapped, local_candidate, vnd_cost, shape.half, lower, upper,
                               config.ils_iterations, config.vnd_iterations,
                               config.perturbation_strength, local_cache, worker_rng, deadline);

                return WorkerResult{std::move(local_candidate), local_cost};
            }));
    }

    CandidateCost best_worker{{}, std::numeric_limits<double>::infinity()};
    for (auto &f : futures) {
        auto wr = f.get();
        if (wr.cost < best_worker.cost) {
            best_worker.cost = wr.cost;
            best_worker.candidate = std::move(wr.candidate);
        }
    }
    return best_worker;
}

inline std::optional<std::size_t>
update_convergence_monitor(std::optional<ConvergenceMonitor> &conv_monitor,
                           ElitePool &elite_pool, double best_cost, std::size_t &stagnation,
                           std::optional<EvaluationCache> &cache) {
    if (!conv_monitor)
        return std::nullopt;

    auto sig = conv_monitor->update(best_cost, &elite_pool);
    std::optional<std::size_t> no_improve_count = sig.no_improve_count;
    if (!sig.should_restart)
        return no_improve_count;

    elite_pool.keep_top(2);
    conv_monitor->reset_no_improve();
    stagnation = 0;
    no_improve_count = 0;
    if (cache)
        cache->clear();
    return no_improve_count;
}

inline bool should_run_path_relinking(const GivpConfig &config, std::size_t iteration,
                                      const ElitePool &elite_pool) {
    return config.use_elite_pool && iteration > 0 &&
           (iteration % config.path_relink_frequency == 0) && elite_pool.len() >= 2;
}

template <typename F>
static void
apply_stagnation_restart(const F &wrapped, const GivpConfig &config,
                         const ProblemShape &shape, const std::vector<double> &lower,
                         const std::vector<double> &upper,
                         std::optional<EvaluationCache> &cache, Rng &rng,
                         const Deadline &deadline, double alpha, std::size_t &stagnation,
                         std::vector<double> &best_solution, double &best_cost) {
    if (stagnation <= config.max_iterations / 4)
        return;

    auto child = rng.child();
    const GraspConstructParams restart_params{nullptr, alpha, shape.half,
                                              config.num_candidates_per_step};
    auto [rsol, rcost0] =
        construct_grasp(shape.num_vars, lower, upper, wrapped, restart_params, cache, child,
                        deadline);
    double rcost = local_search_vnd(wrapped, rsol, rcost0, shape.half, lower, upper,
                                    config.vnd_iterations, cache, child, deadline);
    rcost = ils_search(wrapped, rsol, rcost, shape.half, lower, upper, config.ils_iterations,
                       config.vnd_iterations, config.perturbation_strength, cache, child,
                       deadline);
    if (rcost < best_cost) {
        best_cost = rcost;
        best_solution = std::move(rsol);
    }
    stagnation = 0;
}

/// Main optimizer loop.
template <typename F>
OptimizeResult run(F &&func, const std::vector<std::pair<double, double>> &bounds,
                   GivpConfig config) {
    config.validate();

    // C++17: structured bindings cannot be captured by lambdas; use
    // regular named variables so the multi-worker lambda can capture them.
    auto bounds_vecs = validate_bounds(bounds, config.initial_guess);
    auto lower = std::move(bounds_vecs.first);
    auto upper = std::move(bounds_vecs.second);
    std::size_t num_vars = bounds.size();

    // When integer_split is not set, treat all variables as continuous
    // (half == num_vars → no integer rounding applied).
    std::size_t half =
        get_half(num_vars, config.integer_split.has_value() ? config.integer_split
                                                            : std::optional<std::size_t>{num_vars});

    bool is_maximize = (config.direction == Direction::Maximize);

    // Atomic counter — wrapped lambda is called from a single thread only,
    // but std::atomic makes the intent explicit.
    std::atomic<std::size_t> nfev{0};
    auto wrapped = [&func, &nfev, is_maximize](const std::vector<double> &x) -> double {
        nfev.fetch_add(1, std::memory_order_seq_cst);
        double v = func(x);
        return is_maximize ? -v : v;
    };

    auto rng = Rng::from_seed(config.seed);
    std::optional<EvaluationCache> cache;
    if (config.use_cache)
        cache.emplace(config.cache_size);

    ElitePool elite_pool{config.elite_size, 0.05, lower, upper};
    std::optional<ConvergenceMonitor> conv_monitor;
    if (config.use_convergence_monitor)
        conv_monitor.emplace(20, 50);

    Deadline deadline;
    if (config.time_limit > 0.0)
        deadline = std::chrono::steady_clock::now() +
                   std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                       std::chrono::duration<double>(config.time_limit));

    // ── Initialise best solution ─────────────────────────────────────────────
    const ProblemShape shape{num_vars, half};
    auto [best_solution, best_cost] =
        initialize_best_solution(wrapped, config, shape, lower, upper, cache, rng, deadline);

    if (config.use_elite_pool)
        elite_pool.add(best_solution, best_cost);

    std::size_t stagnation = 0;
    std::size_t iterations_executed = 0;
    std::string message;

    // ── Main loop ─────────────────────────────────────────────────────────────
    for (std::size_t iteration = 0; iteration < config.max_iterations; ++iteration) {
        if (expired(deadline)) {
            message = "time limit reached";
            break;
        }
        iterations_executed = iteration + 1;

        double alpha = get_current_alpha(AlphaScheduleParams{iteration, config.max_iterations,
                                                             config.alpha_min, config.alpha_max,
                                                             config.adaptive_alpha, config.alpha});

        const std::vector<double> *ig =
            (iteration == 0 && config.initial_guess) ? &(*config.initial_guess) : nullptr;

        CandidateCost iteration_result =
            (config.n_workers <= 1)
                ? run_single_worker_iteration(wrapped, config, shape, lower, upper, ig,
                                              cache, rng, deadline, alpha)
                : run_multi_worker_iteration(wrapped, config, shape, lower, upper, ig, rng,
                                             deadline, alpha);

        std::vector<double> candidate = std::move(iteration_result.candidate);
        double ils_cost = iteration_result.cost;

        // Update best
        if (ils_cost < best_cost) {
            best_cost = ils_cost;
            best_solution = candidate;
            stagnation = 0;
        } else {
            ++stagnation;
        }

        if (config.use_elite_pool)
            elite_pool.add(candidate, ils_cost);

        // Convergence monitor — single update per iteration
        std::optional<std::size_t> no_improve_count =
            update_convergence_monitor(conv_monitor, elite_pool, best_cost, stagnation, cache);

        // Path relinking
        if (should_run_path_relinking(config, iteration, elite_pool)) {
            auto child = rng.child();
            do_path_relinking(wrapped, elite_pool, best_solution, best_cost, half, lower, upper,
                              config.vnd_iterations, cache, child, deadline);
        }

        // Stagnation restart
        apply_stagnation_restart(wrapped, config, shape, lower, upper, cache, rng,
                                 deadline, alpha, stagnation, best_solution, best_cost);

        // Early stop — reuse the same convergence signal from this iteration.
        if (no_improve_count.has_value() && *no_improve_count >= config.early_stop_threshold) {
            message = "early stop due to stagnation";
            break;
        }

        if (iteration == config.max_iterations - 1)
            message = "max iterations reached";
    }

    // ── Build result ─────────────────────────────────────────────────────────
    double final_cost = is_maximize ? -best_cost : best_cost;

    OptimizeResult result;
    result.x = std::move(best_solution);
    result.fun = final_cost;
    result.nit = iterations_executed;
    result.nfev = nfev.load(std::memory_order_seq_cst);
    result.success = std::isfinite(final_cost);
    result.message = message;
    result.direction = config.direction;
    result.termination = termination_from_message(message);
    return result;
}

} // namespace givp::detail
