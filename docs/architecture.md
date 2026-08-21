<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->

# Architecture

This page describes the cross-language architecture contract for `givp`.
All ports must keep algorithm semantics and module responsibilities aligned.

## Core execution flow

```mermaid
flowchart LR
    A[API entry point] --> B[Config validation]
    B --> C[GRASP construction]
    C --> D[VND local search]
    D --> E[ILS perturbation loop]
    E --> F{Path relinking trigger}
    F -->|yes| G[PR walk over elite pairs]
    F -->|no| H[Elite and convergence update]
    G --> H
    H --> I{Termination checks}
    I -->|continue| C
    I -->|stop| J[OptimizeResult]
```

## Module contract

Each language implementation mirrors the same logical modules:

| Module | Responsibility |
|---|---|
| `config` | Hyper-parameters and validation |
| `result` | Result container and termination reason |
| `exceptions` | Domain error hierarchy rooted at GivpError |
| `grasp` | Greedy randomized construction and RCL logic |
| `vnd` | Local search neighborhoods and adaptive ordering |
| `ils` | Perturbation and restart strategy |
| `pr` | Path relinking between elite solutions |
| `impl` / core | Top-level orchestration loop |
| `cache` | LRU evaluation cache |
| `elite` | Elite pool update and diversity policy |
| `convergence` | Stagnation detection and stop criteria |
| `helpers` | RNG, bounds handling, shared math |
| `api` | Public wrapper API |
| `examples.benchmark` | Reproducible benchmark functions and seed sweeps |

## Module interaction map

```mermaid
flowchart TD
    API[api]
    CFG[config]
    CORE[impl/core]
    GRASP[grasp]
    VND[vnd]
    ILS[ils]
    PR[pr]
    ELITE[elite]
    CACHE[cache]
    CONV[convergence]
    HELP[helpers]
    RESULT[result]
    EXC[exceptions]

    API --> CFG
    API --> CORE
    CORE --> GRASP
    CORE --> VND
    CORE --> ILS
    CORE --> PR
    CORE --> ELITE
    CORE --> CACHE
    CORE --> CONV
    CORE --> HELP
    CORE --> RESULT
    API --> EXC
```

## One iteration sequence

```mermaid
sequenceDiagram
    participant User
    participant API as api
    participant Core as impl/core
    participant G as grasp
    participant V as vnd
    participant I as ils
    participant P as pr
    participant E as elite+convergence

    User->>API: givp(func, bounds, config)
    API->>Core: validate config and start run
    loop until stop condition
        Core->>G: construct candidate (RCL)
        G-->>Core: candidate
        Core->>V: local search
        V-->>Core: improved candidate
        Core->>I: perturb and restart
        I-->>Core: iterated candidate
        alt relinking frequency reached
            Core->>P: relink elite paths
            P-->>Core: relinked candidate
        end
        Core->>E: update elite and convergence
        E-->>Core: stop or continue
    end
    Core-->>API: OptimizeResult
    API-->>User: result
```

## Language parity matrix

| Capability | Python | Julia | Rust | C++ | R |
|---|---|---|---|---|---|
| Public API wrapper | yes | yes | yes | yes | yes |
| GRASP + ILS + VND + PR | yes | yes | yes | yes | yes |
| Evaluation cache | yes | yes | yes | yes | yes |
| Elite pool and convergence | yes | yes | yes | yes | yes |
| Literature comparison pipeline | yes | yes | in progress | yes | partial |

## Invariants to preserve

1. Parameter names and semantics must remain aligned across language ports.
2. Termination reason mapping should be equivalent across public APIs.
3. Benchmark protocol should use the same objective set and seed strategy.
4. Changes in one port that alter behavior should be mirrored in others.

## Where to look first

1. Start at each language public API entry point.
2. Follow the call chain into the orchestrator (`impl`/core).
3. Confirm call order of GRASP -> VND -> ILS -> PR.
4. Validate that result and termination fields match the shared contract.
