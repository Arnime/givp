# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

FROM rust@sha256:bf7d87666c4da6eace19e06d21bc4859c6e2a5c97a21ac273b0e082112753cf0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    clang \
    cmake \
    curl \
    git \
    lld \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
