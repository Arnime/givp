# Benchmarks Python

Ferramentas internas e reproduzíveis para comparar o GIVP com algoritmos da
literatura. Esta árvore não faz parte do wheel publicado.

## Instalação

```powershell
cd python
poetry install --with dev,benchmarks
```

## Comparação científica

```powershell
poetry run python -m benchmarks.comparison \
  --dims 10 --n-runs 30 --traces \
  --algorithms GIVP-full DE PSO GA CMA-ES SA \
  --output benchmarks/.results/comparison/results.json
```

O comando preserva o schema `benchmark-schema-v1`, aceita retomada com
`--resume` e pode carregar uma configuração produzida pelo tuning com
`--tune-config`.

## Tuning

```powershell
poetry run python -m benchmarks.tuning \
  --n-trials 50 --dims 5 --functions Sphere Rastrigin \
  --output benchmarks/.results/tuning/best_config.json
```

Hydropower-specific tuning lives in the `benchmarks.tuning.hydropower` package.
Use `python -m benchmarks.tuning.hydropower` for one scenario and
`python -m benchmarks.tuning.hydropower.multiscenario` for one shared
configuration across several scenarios. Configuration construction, trial
evaluation, and reference loading are separated into their own modules.

The seven-scenario global pilot uses a clean reference CSV containing DE from
the historical campaign and PSO plus the real unified UPSO from the latest
campaign. Each trial evaluates all scenarios with the same optimizer seed (seed
0 for the pilot); validation seeds 44–48 remain held out. Each GIVP execution
has a 300-second limit and a 15,000-evaluation cap.

```powershell
poetry run python -m benchmarks.tuning.hydropower.multiscenario `
  --benchmark-root ..\experiments\synthetic_hydropower\benchmarks\v1.0.0 `
  --scenarios dry_stable dry_variable typical upstream_peak downstream_dominant wet_rising flood `
  --n-trials 10 --n-eval-seeds 1 --eval-seed-start 0 `
  --max-iter 80 --time-limit 300 --sampler-seed 42 `
  --study-name givp_global_tuning_pilot `
  --storage sqlite:///../experiments/synthetic_hydropower/output/givp_global_tuning_pilot/study.db `
  --reference-runs ..\experiments\synthetic_hydropower\output\givp_global_tuning_pilot\reference.csv `
  --reference-algorithms DE PSO UPSO `
  --seed-config ..\experiments\synthetic_hydropower\interop\v1\tuned_hyperparameters.json `
  --seed-config ..\experiments\synthetic_hydropower\interop\v1\tuned_hyperparameters_v2.json `
  --seed-config ..\experiments\synthetic_hydropower\interop\v1\tuned_hyperparameters_v4.json `
  --trials-csv ..\experiments\synthetic_hydropower\output\givp_global_tuning_pilot\trials.csv `
  --output ..\experiments\synthetic_hydropower\output\givp_global_tuning_pilot\bestconfig.json
```

The pilot takes up to 5 h 50 min at the configured per-evaluation limit. Three
archived configurations are re-evaluated as warm starts; the remaining seven
trials explore new configurations. Historical objective values are not reused.

## Relatórios

```powershell
poetry run python -m benchmarks.reporting \
  --input benchmarks/.results/comparison/results.json \
  --format both \
  --output-dir benchmarks/.results/comparison/report
```

O relatório inclui estatísticas descritivas, Wilcoxon, correção de Holm,
Friedman, Markdown, LaTeX, boxplots e curvas de convergência quando disponíveis.

## Publicação na documentação

```powershell
poetry run python -m benchmarks.publishing \
  --repo-root .. \
  --artifact Python=python/benchmarks/artifacts/reference/quick/results.json \
  --output-dir ../docs/examples/benchmark-reports
```

## Desempenho

O microbenchmark é opt-in e não pertence à suíte funcional padrão:

```powershell
poetry run pytest -m performance tests/benchmark/test_performance.py \
  --benchmark-only --benchmark-autosave
```

Os resultados locais e de CI ficam em `benchmarks/.results/`, ignorado pelo
Git. A referência científica versionada fica em
`benchmarks/artifacts/reference/quick/`.
