# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

suppressPackageStartupMessages(library(givp))

is_full_test_profile <- function() {
  identical(tolower(Sys.getenv("GIVP_R_TEST_PROFILE", "quick")), "full")
}

skip_if_not_full_profile <- function() {
  testthat::skip_if_not(
    is_full_test_profile(),
    "Requires GIVP_R_TEST_PROFILE=full"
  )
}

smoke_config <- function(direction = "minimize") {
  givp_config(
    max_iterations = 4L,
    vnd_iterations = 8L,
    ils_iterations = 2L,
    num_candidates_per_step = 6L,
    path_relink_frequency = 4L,
    direction = direction
  )
}
