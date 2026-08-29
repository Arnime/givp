# Protocolo `synthetic-hydropower/v1`

O protocolo local usa JSON para que R, Julia, Rust e C++ usem exatamente o
motor físico Python de referência. A configuração das duas usinas e as curvas
permanecem congeladas no pacote; somente as afluências incrementais e as
agendas de potência podem variar.

Instale o motor com `python -m pip install "givp[hydropower]"` ou, no checkout,
com `cd python; poetry install -E hydropower`.

`request.schema.json` e `response.schema.json` definem o envelope. Cada lote
tem uma ou mais requisições identificadas por `case_id`, com matrizes `[2][24]`
na ordem A, B. A resposta mantém o identificador e contém todas as séries e
agregados de `PowerScheduleResult` e `SimulationResult`, sem arredondamento.
`zero_schedule_batch.json` e `zero_schedule_response.json` são o par canônico
de entrada e resposta usado pelos clientes de referência.

Execução única:

```powershell
synthetic-hydropower balance `
  --request zero_schedule_batch.json `
  --output response.json
```

Processo persistente:

```text
stdin:  {"schema_version":"synthetic-hydropower/v1","requests":[...]}
stdout: {"schema_version":"synthetic-hydropower/v1","results":[...]}
```

Uma linha vazia é ignorada. Uma linha inválida devolve `error.code` como
`invalid_json`, `invalid_request` ou `evaluation_error`; o worker continua
atendendo as linhas seguintes. Para otimizadores, envie a população inteira em
um único lote para amortizar o custo de comunicação entre processos.
