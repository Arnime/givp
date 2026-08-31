# Benchmark sintético de cascata hidrelétrica — v1.0.0

Esta é a única versão do benchmark acadêmico. Ela compartilha a mesma cascata,
os mesmos parâmetros físicos e as mesmas sete afluências congeladas entre dois
protocolos complementares.

## Protocolos

### `deterministic_balance`

É a referência física canônica e não executa o GIVP. Para cada cenário, cruza
seis metas constantes de potência em A com seis em B durante 24 horas. São 36
combinações por cenário e 252 casos no total.

O protocolo registra potência solicitada e realizada, déficit, status, vazões,
parcelas de vertimento, defluência, volumes, níveis de montante e jusante,
queda, penalidades e resíduo de massa. Seus CSVs usam seis casas decimais e são
reproduzíveis a partir das afluências congeladas.

#### Verificação pelos clientes de outras linguagens

O protocolo também possui uma rota de verificação de interoperabilidade: os
clientes R, Julia, Rust e C++ enviam as mesmas 252 agendas ao worker Python
`synthetic-hydropower/v1`. Portanto, a física continua única e canônica no
Python; o que se verifica nas demais linguagens é o contrato local de processo,
JSON e transformação dos resultados em tabela.

| Cliente | Casos enviados | Série horária | Resumo |
| --- | ---: | ---: | ---: |
| R | 252 | 12.096 ✓ | 252 ✓ |
| Julia | 252 | 12.096 ✓ | 252 ✓ |
| Rust | 252 | 12.096 ✓ | 252 ✓ |
| C++ | 252 | 12.096 ✓ | 252 ✓ |

Cada resposta é comparada aos CSVs deste diretório com tolerância `1e-6`. Os
arquivos derivados são escritos em `experiments/synthetic_hydropower/output/`
e não fazem parte deste benchmark congelado, de seus checksums ou de seus
`reference_results`. Veja o procedimento em
[`clients/README.md`](../../clients/README.md).

### `givp_optimization`

É um experimento derivado que usa o GIVP para escolher solicitações de vazão.
O balanço hidráulico continua sendo calculado pelo mesmo modelo sintético. Seus
resultados são referências estocásticas e podem apresentar pequenas diferenças
entre ambientes; não definem os resultados canônicos do balanço determinístico.

## Estrutura

```text
v1.0.0/
  benchmark_definition.json
  benchmark_manifest.json
  data_provenance.json
  config/base.json
  inputs/inflows.csv
  protocols/
    deterministic_balance/
      definition.json
      protocol_manifest.json
      inputs/power_schedules.csv
      reference_results/
      figures/
    givp_optimization/
      definition.json
      protocol_manifest.json
      reference_results/
      figures/
```

O manifesto raiz registra o SHA-256 de todos os JSONs, CSVs e PNGs canônicos.
Cada protocolo também possui definição e manifesto próprios para deixar claro
se o resultado veio do equacionamento determinístico ou de uma execução do
GIVP.

## Citação e publicação

Este benchmark é um produto acadêmico distinto do software GIVP. Seus dados,
resultados, figuras e documentação são licenciados sob
[CC BY 4.0](LICENSE-DATA.md); o código-fonte do GIVP continua sob a licença MIT
na raiz do repositório. A citação específica do benchmark está em
[`CITATION.cff`](CITATION.cff).

O Zenodo é o arquivo canônico e o DOI preferencial de citação:
<https://doi.org/10.5281/zenodo.22185079>. O HydroShare receberá um recurso
complementar voltado à comunidade de hidrologia, ligado a esse DOI de versão.

O procedimento, metadados, escopo dos dois pacotes e verificações estão em
[`PUBLICATION.md`](PUBLICATION.md). Ele gera arquivos a partir de um commit Git
exato e valida novamente os checksums deste manifesto dentro dos ZIPs antes de
qualquer envio.

## Proveniência e independência

Os parâmetros são sintéticos e perturbados, ancorados em faixas públicas. As
usinas A e B são aproximações acadêmicas inspiradas em informações publicadas
sobre Monte Claro e 14 de Julho, sem representar sua operação oficial.

Nenhum código, série histórica, tabela operacional ou coeficiente proprietário
do SOG2 foi incorporado. Essa organização documenta independência técnica, mas
não constitui parecer jurídico e não substitui análise de patente, contratos ou
obrigações de confidencialidade.
