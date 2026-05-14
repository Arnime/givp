// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT
#pragma once

#include <givp/config.hpp>
#include <givp/detail/impl_core.hpp>
#include <givp/result.hpp>

namespace givp {

/// Run the GRASP-ILS-VND with Path Relinking optimizer.
///
/// @tparam F  Callable with signature `double(const std::vector<double>&)`.
/// @param func     Objective function to minimize (or maximize).
/// @param bounds   Variable bounds as a vector of (lower, upper) pairs.
/// @param config   Algorithm configuration (optional, defaults are reasonable).
/// @return         OptimizeResult with best solution, objective value, and
/// stats.
/// @throws InvalidBounds, InvalidInitialGuess, InvalidConfig on bad input.
template <typename F>
OptimizeResult givp(F &&func, const std::vector<std::pair<double, double>> &bounds,
                    GivpConfig config = {}) {
    return detail::run(std::forward<F>(func), bounds, std::move(config));
}

} // namespace givp
