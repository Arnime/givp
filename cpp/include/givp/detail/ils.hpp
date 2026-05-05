// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <cmath>
#include <numeric>
#include <utility>
#include <vector>

#include "cache.hpp"
#include "grasp.hpp"
#include "helpers.hpp"
#include "vnd.hpp"

namespace givp::detail {

struct IlsIterations {
    std::size_t value;
};

template <typename RngT> struct IlsRunContext {
    const std::vector<double> &lower;
    const std::vector<double> &upper;
    std::size_t half;
    IlsIterations ils_iterations;
    VndMaxIterations vnd_iterations;
    PerturbStrength perturbation_strength;
    std::optional<EvaluationCache> &cache;
    RngT &rng;
    const Deadline &deadline;
};

template <typename RngT>
static std::vector<double>
perturb_solution(const std::vector<double> &solution, std::size_t half, PerturbStrength strength,
                 const std::vector<double> &lower, const std::vector<double> &upper, RngT &rng) {

    std::size_t n = solution.size();
    std::size_t num_perturb = std::max(std::size_t{1}, std::min(strength.value, n / 5));
    std::vector<double> perturbed = solution;
    std::vector<std::size_t> indices(n);
    std::iota(indices.begin(), indices.end(), std::size_t{0});

    for (std::size_t i = 0; i < num_perturb; ++i) {
        std::size_t j = rng.uniform_index(i, n - 1);
        std::swap(indices[i], indices[j]);
    }

    for (std::size_t k = 0; k < num_perturb; ++k) {
        std::size_t idx = indices[k];
        if (idx >= half) {
            double step = std::max(static_cast<double>(strength.value) / 2.0, 1.0);
            double delta = rng.uniform(-step, step);
            perturbed[idx] = std::round(clamp_val(perturbed[idx] + delta, lower[idx], upper[idx]));
        } else {
            double span = upper[idx] - lower[idx];
            double delta = rng.uniform(-0.15, 0.15) * span;
            perturbed[idx] = clamp_val(perturbed[idx] + delta, lower[idx], upper[idx]);
        }
    }

    normalize_integer_tail(perturbed, half);
    return perturbed;
}

/// Iterated Local Search.
template <typename F, typename RngT>
double ils_search(const F &func, std::vector<double> &solution, double current_cost,
                  IlsRunContext<RngT> &ctx) {

    double best_cost = current_cost;
    std::vector<double> best_sol = solution;

    for (std::size_t i = 0; i < ctx.ils_iterations.value; ++i) {
        if (expired(ctx.deadline))
            break;

        // Progressive adaptive strength
        double progress = static_cast<double>(i) /
                          static_cast<double>(std::max(ctx.ils_iterations.value, std::size_t{1}));
        std::size_t effective_strength =
            std::max(ctx.perturbation_strength.value,
                     static_cast<std::size_t>(static_cast<double>(ctx.perturbation_strength.value) *
                                              (1.0 + progress)));

        auto candidate = perturb_solution(best_sol, ctx.half, PerturbStrength{effective_strength},
                                          ctx.lower, ctx.upper, ctx.rng);
        double perturbed_cost = evaluate_with_cache(candidate, func, ctx.cache, ctx.half);
        VndContext<RngT> vnd_ctx{ctx.lower, ctx.upper, ctx.cache, ctx.half, ctx.rng,
                                 ctx.deadline};
        double vnd_cost = local_search_vnd(func, candidate, perturbed_cost, ctx.vnd_iterations,
                                           vnd_ctx);

        if (vnd_cost < best_cost) {
            best_cost = vnd_cost;
            best_sol = candidate;
        } else if (vnd_cost < best_cost * 1.25 && ctx.rng.random_double() < 0.1) {
            // Accept slightly worse with 10% probability (diversification)
            best_sol = candidate;
            best_cost = vnd_cost;
        }
    }

    solution = std::move(best_sol);
    return best_cost;
}

} // namespace givp::detail
