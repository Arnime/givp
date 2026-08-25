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

Nenhum resultado é enviado automaticamente. Publicação em nuvem exige escolher
e autorizar explicitamente a conta ou organização de destino.
