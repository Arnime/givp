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
