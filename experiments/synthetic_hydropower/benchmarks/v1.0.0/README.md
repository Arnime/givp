# Benchmark sintético de cascata hidrelétrica — v1.0.0

Esta é a primeira versão congelada do benchmark acadêmico de duas usinas
fictícias em cascata. Ela contém sete cenários de 24 horas e uma turbina
agregada por usina.

## Conteúdo da versão

- `benchmark_definition.json`: cenários, seeds, horizonte, penalidades e
  hiperparâmetros do GIVP;
- `config/base.json`: cópia imutável dos parâmetros físicos sintéticos;
- `reference_results/`: resultados de referência gerados com esta definição.
- `figures/`: referência visual gerada exclusivamente dos resultados congelados.

Os arquivos em `reference_results/` são:

- `benchmark_summary.csv`, com métricas agregadas por cenário;
- `benchmark_time_series.csv`, com a série horária de cada usina;
- `benchmark_manifest.json`, com a rastreabilidade da execução.

Para cada cenário, `figures/` contém três imagens PNG: potência das duas
usinas, vazões por usina e níveis de montante com seus limites normais. As
imagens são auxiliares de validação visual; CSV e manifesto continuam sendo a
referência numérica do benchmark.

## Regra de imutabilidade

Esta pasta não deve ser alterada depois de publicada. Mudanças nos cenários,
na configuração física, nas equações, no GIVP ou nos resultados devem criar
uma nova versão, como `v1.1.0` ou `v2.0.0`.

## Reprodução

Use o notebook indicado em `benchmark_definition.json`, com as dependências
declaradas em `pyproject.toml`. A configuração e os resultados de referência
devem ter o mesmo checksum SHA-256 registrado no manifesto.

Todos os dados, rótulos, coeficientes e regras operacionais deste benchmark são
fictícios. A estrutura física é didática e não reproduz a operação de ativos
reais.
