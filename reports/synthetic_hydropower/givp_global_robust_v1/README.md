# Busca global robusta do GIVP e validação pareada

Este pacote guarda a evidência versionável da busca de hiperparâmetros e da validação final independente nos sete cenários do benchmark `synthetic_hydropower` v1.0.0.

## Sequência experimental

1. **Triagem global:** 16 configurações comuns aos sete cenários, seeds de otimizador 1–3, limite de 300 s por execução e máximo de 15.000 avaliações. A seleção considerou o score normalizado balanceado entre os grupos de cenários prioritários e protegidos e o risco médio dos dois piores cenários.
2. **Extensão:** a configuração incumbente e até dois candidatos elegíveis foram reavaliados com seeds 4–7. Scores antigos do Optuna não foram reutilizados como observações novas. Para avançar, cada cenário deveria ficar no máximo 0,05 acima da incumbente em gap normalizado.
3. **Seleção:** o trial 15 foi selecionado após a extensão (trial 19), com score robusto combinado **0,4381**, frente a **0,9425** da incumbente. O trial 5 teve o menor score na triagem, mas falhou a regra de não regressão com os seeds de extensão e não foi escolhido.
4. **Validação independente:** GIVP, DE, PSO e UPSO foram comparados de forma pareada nos sete cenários e seeds 49–58. Foram concluídas 70 execuções por algoritmo, 280 no total; cada execução tinha teto de 300 s e 15.000 avaliações.

O banco contém também uma extensão concluída do trial 10, criada por um estado anterior da retomada. A seleção final documentada usa apenas a incumbente (trial 0) e os dois finalistas elegíveis (trials 5 e 15); a extensão extra não entrou na decisão.

## Hiperparâmetros GIVP selecionados

- `alpha=0.2070315`, `adaptive_alpha=true`, `alpha_min=0.1263864`, `alpha_max=0.2751714`
- `vnd_iterations=62`, `ils_iterations=8`, `perturbation_strength=8`
- `use_elite_pool=false`, `num_candidates_per_step=16`
- `max_iterations=80`, `early_stop_threshold=80`, monitor de convergência desligado
- `time_limit_seconds=300`, `max_evaluations=15000`

O perfil congelado de todos os algoritmos está em `validation_profile.json`.

## Resultado da validação

O relatório calcula gaps normalizados pareados como **GIVP menos baseline**; valores negativos favorecem o GIVP. Os intervalos de confiança bootstrap reamostram blocos completos de seeds; os valores de p recebem correção de Holm para as três comparações.

| Baseline | Gap médio ponderado | IC 95% por seed | p de Holm | Sem regressão > 0,05 por cenário? | Leitura |
|---|---:|---:|---:|---|---|
| DE | −4,1505 | [−4,5534; −3,7450] | 0,00586 | sim | GIVP superior nesta validação |
| PSO | −0,6366 | [−1,0276; −0,2550] | 0,03125 | sim | GIVP superior nesta validação |
| UPSO | +0,4156 | [+0,1578; +0,6801] | 0,03125 | não | GIVP não superou UPSO |

A conclusão fica limitada a este benchmark, objetivo, perfis dos baselines e dez seeds independentes avaliadas. Não se deve generalizar a superioridade para outros problemas ou distribuições de seeds. Médias e desvios padrão do objetivo e do tempo de execução por cenário estão em `validation/scenario_summary.csv`.

## Arquivos

- `tuning/study.db`, `tuning/trials.csv`, `tuning/bestconfig.json`, `tuning/selection.json`: estudo Optuna, registros por trial, configuração escolhida emitida pelo comando e decisão final.
- `tuning/reference.csv`, `tuning/reference_sources.json`: resultados e proveniência usados para normalizar o score de tuning.
- `tuning/seed_configs/`: cópias das quatro configurações warm start, com nomes indicando origem.
- `pilot/`: estudo global piloto usado como fonte da incumbente.
- `validation/runs.csv`: 280 resultados individuais da validação.
- `validation/campaign_metadata.json`, `validation/report.json`: ambiente/perfil executado e análise estatística.
- `validation/scenario_summary.csv`: médias e desvios padrão por cenário e algoritmo.
- `validation/best_solutions.jsonl.gz`: vetores de solução retornados pelas 280 execuções, comprimidos sem perda.
- `checksums.sha256`: SHA-256 para verificar integridade dos artefatos.

A primeira execução da campanha parou após gravar 252 linhas por um erro transitório de leitura de arquivo; a campanha foi retomada usando o CSV existente. A validação final contém exatamente uma linha para cada combinação de cenário, seed e algoritmo.

## Recalcular o relatório

A partir da pasta `python/`:

```powershell
poetry run python -m benchmarks.tuning.hydropower.validation `
  --runs ../reports/synthetic_hydropower/givp_global_robust_v1/validation/runs.csv `
  --reference-runs ../reports/synthetic_hydropower/givp_global_robust_v1/tuning/reference.csv `
  --profile ../reports/synthetic_hydropower/givp_global_robust_v1/validation_profile.json `
  --output ../reports/synthetic_hydropower/givp_global_robust_v1/validation/report.json
```
