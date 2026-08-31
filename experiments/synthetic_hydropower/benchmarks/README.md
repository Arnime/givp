# Publicação do benchmark hidrelétrico

O diretório [`v1.0.0`](v1.0.0/) é a única versão canônica do benchmark. Uma
versão representa o conjunto físico e seus dados compartilhados; as diferentes
formas de execução ficam separadas internamente como protocolos.

- `deterministic_balance`: balanço físico calculado diretamente, sem GIVP;
- `givp_optimization`: experimento de otimização derivado, executado com GIVP.

As afluências congeladas e a configuração das usinas são compartilhadas. Cada
protocolo mantém suas próprias definições, entradas específicas, resultados,
figuras e manifesto. O manifesto raiz cobre todos os artefatos canônicos.

Resultados locais permanecem em `output/` e são ignorados pelo Git. Antes de
publicar uma release ou depositar o conjunto em um repositório com DOI, execute
os testes de reprodução, valide os checksums e registre o hash do commit e as
versões do Python e do GIVP.

## Validação de interoperabilidade

Além da reprodução Python do benchmark, R, Julia, Rust e C++ podem encaminhar
os 252 casos de `deterministic_balance` ao mesmo worker físico Python. Esse
procedimento valida o contrato JSON, a ordem das agendas, o transporte dos
resultados e a conversão para tabelas canônicas — não é uma segunda
implementação das equações hidráulicas em cada linguagem.

As respostas de cada linguagem ficam em
`output/interop/deterministic_balance/<linguagem>/` e são comparadas em
tolerância `1e-6` contra os dois CSVs congelados. A validação completa deve
informar 12.348 linhas: 12.096 observações horárias e 252 linhas-resumo. Esses
artefatos são deliberadamente derivados e ignorados pelo Git; nunca devem ser
movidos para `reference_results/` nem incluídos nos manifests canônicos.

O procedimento e os comandos para cada ambiente estão em
[`clients/README.md`](../clients/README.md).

Nenhum resultado é enviado automaticamente. Publicação em nuvem exige escolher
e autorizar explicitamente a conta ou organização de destino.
