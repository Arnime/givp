# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

FROM julia@sha256:de062e41e38f57b8181ff910cb960bd92f3beff5ef15b30bea1d22faf4470562

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    grep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
