# Publicação de benchmarks

Os arquivos produzidos em `output/` são resultados locais de uma execução e
ficam fora do versionamento. Cada versão publicada, como
[`v1.0.0`](v1.0.0/), congela definição, configuração e resultados de referência.
Uma nova execução não pode substituir os arquivos já publicados.

Os três artefatos de referência são:

- `benchmark_summary.csv`: comparação agregada entre cenários;
- `benchmark_time_series.csv`: série horária em formato longo, por usina;
- `benchmark_manifest.json`: seeds, horizonte e checksum de `configs/base.json`.
- `figures/`: gráficos PNG produzidos a partir da série horária congelada.

Antes de publicar, execute os testes e confirme que o manifesto lista os sete
cenários esperados. Use `promote_benchmark_version` para copiar os artefatos:
ela valida o checksum da configuração e se recusa a sobrescrever uma versão.

Para preservação em nuvem, a recomendação é publicar essa pasta em uma release
imutável do repositório Git e arquivá-la em um repositório de dados com DOI,
como Zenodo. A release deve incluir o hash do commit, a versão do Python, a
versão do GIVP e o manifesto. O DOI é a referência a ser usada por terceiros;
o repositório continua sendo a fonte do código e das configurações.

Nenhum resultado é enviado automaticamente: a publicação exige escolher e
autorizar a conta/organização de destino.
