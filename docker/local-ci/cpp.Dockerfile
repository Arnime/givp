# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

FROM ubuntu@sha256:cdb5fd928fced577cfecf12c8966e830fcdf42ee481fb0b91904eeddc2fe5eff

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    clang \
    cmake \
    git \
    lcov \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
