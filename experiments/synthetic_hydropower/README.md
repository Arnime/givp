# Cascata hidrelétrica sintética

Experimento acadêmico reproduzível para estudar o balanço de duas usinas
hidrelétricas sintéticas em cascata. Os notebooks e o benchmark pertencem a
`experiments/`; a implementação reutilizável é disponibilizada como o exemplo
opcional `givp.examples.synthetic_hydropower` do pacote GIVP.

## Independência do material proprietário

Os parâmetros são sintéticos e perturbados, ancorados em faixas publicadas nos
Planos de Ação de Emergência das UHEs Monte Claro e 14 de Julho. As usinas A e
B são aproximações acadêmicas inspiradas nessas faixas públicas; não são
réplicas operacionais. O inventário versionado distingue referências públicas,
transformações sintéticas documentadas e hipóteses inteiramente sintéticas.

Nenhum código, série histórica, tabela operacional ou coeficiente proprietário
do SOG2 foi incorporado. Essa rastreabilidade sustenta uma avaliação de
independência técnica, mas não é parecer jurídico e não substitui a análise das
reivindicações da patente, dos contratos e de eventuais obrigações de sigilo ou
NDA.

## Modelo

Os rótulos A e B não identificam ativos. Os valores não são dados operacionais;
foram arredondados, deslocados ou construídos a partir de faixas públicas para
preservar apenas relações físicas genéricas de uma cascata curta.

### Elementos preservados

- Conservação de massa por período, com volume, afluência, turbinação e
  vertimento.
- Propagação da defluência de A para B com atraso hidráulico configurável.
- Relação volume–nível de montante, relação defluência–nível de jusante e queda
  líquida para o cálculo de potência.
- Limites de potência, de vazão turbinada, de volume e de nível de montante.
- Faixa entre o máximo normal e o maximorum para representar um vertimento
  gradual, penalidade de nível e penalidade de chaveamento na função objetivo.

### Simplificações deliberadas

- Duas usinas fictícias, uma turbina agregada por usina e período horário fixo.
- Afluências sintéticas: `y_B` agrega qualquer contribuição local de B; não há
  modelagem espacial de sub-bacias, previsão hidrológica ou dados observados.
- Polinômios de quarto grau sintéticos e normalizados, construídos para lembrar
  a forma física esperada sem copiar curvas, tabelas ou coeficientes operativos.
- Rendimento constante; não há curvas de colina, perdas hidráulicas explícitas,
  múltiplas máquinas, zonas proibidas, rampas, preços ou custos operativos. A
  permanência de oito horas é apenas uma penalidade suave de chaveamento, não
  uma restrição física de tempo mínimo.
- O vertimento só é ativado quando o nível provisório supera o máximo; portanto,
  é uma regra didática de controle de armazenamento, não uma regra operacional.
- A função objetivo contém benefício de energia, penalidade quadrática de nível
  e penalidades suaves de chaveamento; não inclui preços, contratos ou
  restrições elétricas.

Para cada período, a usina A recebe sua afluência incremental. A usina B recebe
sua própria afluência incremental mais a defluência de A após uma hora. A
afluência incremental de B já agrega todas as contribuições locais que não vêm
da usina A.
A conversão é `3600 / 1_000_000` hm³ por (m³/s).

Os níveis de montante usam polinômios sintéticos normalizados de quarto grau em
toda a faixa `V_min → V_maximorum`: para
`x = (V - V_min) / (V_maximorum - V_min)`,
`n_up = n_min + (n_maximorum - n_min) Σ(a_k x^k)`. Os coeficientes são
construídos para passar por `(V_max, n_max)` e
`(V_maximorum, n_maximorum)`, mantendo a estrutura polinomial sem reutilizar
coeficientes reais.
Para `z = (Q + S) / Q_max`, vale `n_down = a_down + r_down Σ(b_k z^k)`.
Os coeficientes `a_k` e `b_k` foram definidos no experimento em escala
normalizada e não foram copiados de sistemas ou ativos reais.
A queda líquida é `H = max(0, n_up - n_down)`.

O vertimento total combina a parcela sanitária fixa, a parcela por capacidade e
uma resposta de vertedouro por nível: `S = S_sanitário + S_capacidade + S_nível`.
Na faixa entre o nível máximo normal e o maximorum, `S_nível` cresce de forma
não linear com a razão de níveis e é limitado pela capacidade sintética do
vertedouro. Acima do maximorum, uma parcela quadrática de emergência é somada;
ela é alta, mas não retira exatamente o volume excedente em um único período.
Assim, o modelo não calcula um vertimento perfeito para manter o nível no máximo.
Todas as parcelas de vertimento, inclusive a sanitária, só são liberadas quando
o nível provisório de montante supera o limite máximo; a defluência liberada
segue de A para B. A potência é
`P = 0,00981 ηHQ`, com `g = 9,81 m/s²`.
A função usada no experimento de otimização é `-energia_gerada +
penalidade_de_nível + penalidade_de_chaveamento + penalidade_de_troca_antecipada`.
A penalidade física de reservatório é quadrática para níveis de montante abaixo
do mínimo ou acima do máximo. A cada período e para cada usina, o simulador
acumula separadamente `w·max(0, nível_mínimo − nível_final)²` e
`w·max(0, nível_final − nível_máximo)²`; a soma das duas parcelas é a
penalidade de nível. As duas parcelas de chaveamento são preferências suaves do
experimento e não alteram as equações de conservação de massa.

Como há uma turbina agregada por usina, o estado `ligada/desligada` é definido
pela vazão turbinada. Cada mudança entre estados em horas consecutivas recebe a
penalidade suave `w_chaveamento·|z_t - z_(t-1)|`. Assim, um desligamento seguido
de religamento custa duas transições e passa a ser evitado quando alternativas
hidricamente seguras existirem. Além disso, o benchmark 1.0 usa permanência
mínima suave de oito horas: uma troca antes desse prazo recebe a penalidade
adicional `w_antecipada·max(0, 8 - duração_anterior)`. Os pesos sintéticos do
notebook são 250 por troca e 500 por hora de permanência não cumprida. Eles não
são parâmetros operativos reais e podem ser avaliados em estudos de
sensibilidade.

## Executar

### Nova busca global do GIVP

A preparação de tuning usa uma configuração global nos sete cenários, sementes de
triagem `1–3` e seeds de extensão `4–7`. O estudo executa 16 trials de triagem,
reavalia a configuração incumbente e até dois candidatos nos seeds de extensão,
e grava métricas por cenário e seed. Cada execução roda em processo isolado com
timeout externo de 330 s; uma execução que exceda o timeout invalida o trial.
O comando abaixo apenas representa a campanha; não é executado pelos testes.

Execute a partir do diretório `python/`, substituindo os caminhos de saída se
necessário:

```powershell
poetry run python -m benchmarks.tuning.hydropower.multiscenario `
  --benchmark-root ../experiments/synthetic_hydropower/benchmarks/v1.0.0 `
  --scenarios downstream_dominant dry_stable dry_variable flood typical upstream_peak wet_rising `
  --n-trials 16 --n-eval-seeds 3 --eval-seed-start 1 `
  --time-limit 300 --max-iter 80 `
  --study-name givp_global_robust_v1 `
  --storage sqlite:///../experiments/synthetic_hydropower/output/givp_global_robust_v1/study.db `
  --reference-runs ../experiments/synthetic_hydropower/output/givp_global_tuning_pilot/reference.csv `
  --reference-algorithms DE PSO UPSO `
  --seed-config ../experiments/synthetic_hydropower/output/givp_global_tuning_pilot/bestconfig.json `
  --seed-config ../experiments/synthetic_hydropower/interop/v1/tuned_hyperparameters.json `
  --seed-config ../experiments/synthetic_hydropower/interop/v1/tuned_hyperparameters_v2.json `
  --seed-config ../experiments/synthetic_hydropower/interop/v1/tuned_hyperparameters_v4.json `
  --validation-profile-template ../experiments/synthetic_hydropower/output/givp_global_tuning_validation/validation_profile.json `
  --validation-profile-output ../experiments/synthetic_hydropower/output/givp_global_robust_v1/validation_profile.json `
  --trials-csv ../experiments/synthetic_hydropower/output/givp_global_robust_v1/trials.csv `
  --output ../experiments/synthetic_hydropower/output/givp_global_robust_v1/bestconfig.json
```

Depois da busca, o perfil gerado congela DE, PSO e UPSO do template e fixa o
holdout em `49–58`. A validação só começa quando for explicitamente iniciada:

```powershell
poetry run python -m benchmarks.comparison.hydropower.campaign `
  --benchmark-root ../experiments/synthetic_hydropower/benchmarks/v1.0.0 `
  --profile ../experiments/synthetic_hydropower/output/givp_global_robust_v1/validation_profile.json `
  --output-dir ../experiments/synthetic_hydropower/output/givp_global_robust_v1/validation `
  --algorithms DE PSO UPSO GIVP --replications 10

poetry run python -m benchmarks.tuning.hydropower.validation `
  --runs ../experiments/synthetic_hydropower/output/givp_global_robust_v1/validation/runs.csv `
  --reference-runs ../experiments/synthetic_hydropower/output/givp_global_tuning_pilot/reference.csv `
  --profile ../experiments/synthetic_hydropower/output/givp_global_robust_v1/validation_profile.json `
  --output ../experiments/synthetic_hydropower/output/givp_global_robust_v1/validation/report.json
```

O relatório calcula diferenças normalizadas com peso igual entre os dois grupos
de cenários, intervalos bootstrap reamostrando seeds em bloco, testes exatos de
troca de sinal com ajuste de Holm e gaps médios por cenário. A campanha final
não é iniciada pelo comando de tuning.

Na triagem, o score é `0,75 × média balanceada dos grupos + 0,25 × média dos
dois piores gaps`; cada grupo (prioritário e protegido) recebe metade da média
balanceada. Finalistas precisam ficar até `0,05` acima da incumbente em cada
cenário protegido. As execuções individuais registram cenário, seed, objetivo,
número de avaliações e iterações, duração, status e motivo de término.

O arquivo empacotado
`python/src/givp/examples/synthetic_hydropower/configs/base.json` contém
exclusivamente os parâmetros das duas usinas sintéticas. Horizonte, cenários,
seeds e protocolo pertencem às definições versionadas em `benchmarks/`; os
parâmetros do GIVP aparecem somente na seção opcional do notebook.

Os parâmetros finais documentados para o GIVP na dissertação são usados no
notebook: 40 iterações, $\alpha=0{,}17$, VND=15, ILS=5, perturbação=8,
15 candidatos por passo, conjunto elite de tamanho 4 e PR a cada 10 iterações.
O cache de 10.000 avaliações e o monitor de convergência seguem o protocolo
descrito. Para a campanha de comparação, o perfil versionado inclui também o
orçamento de 900 s, $\alpha_{min}=0{,}10$, $\alpha_{max}=0{,}18$, limiar de
parada 36 e dois trabalhadores, conforme a configuração Optuna do SOG usada
como referência histórica.

### Comparação com os algoritmos do SOG

DE, PSO e UPSO são executados exatamente como o SOG os executa hoje, a partir de
uma transcrição do comportamento dos invólucros do SOG (sem importar código,
dados ou coeficientes do SOG). A rastreabilidade de cada parâmetro está em
[`docs/SOG_ALGORITHM_MAPPING.md`](docs/SOG_ALGORITHM_MAPPING.md):

- **DE**: `scipy.optimize.differential_evolution` com `best1bin`, população
  20 × D, 100 iterações, mutação (0,5; 1), recombinação 0,9, inicialização
  `latinhypercube`, atualização `deferred`, `tol=0,09` e sem polimento.
- **PSO**: `pyswarm` 0.6 com 200 partículas, 250 iterações, inércia 0,5 e
  $c_1=c_2=1{,}0$.
- **UPSO rotulado pelo SOG**: os notebooks atuais usam o mesmo invólucro
  `pyswarm.pso` do PSO, com $c_1=0{,}6$, $c_2=0{,}4$ e inércia 0,5. Os perfis
  históricos de reprodução preservam esse comportamento, que não é um UPSO
  unificado.
- **UPSO unificado**: a campanha específica usa a combinação de velocidades
  global e local, melhor local em anel, fator de unificação 0,3,
  $c_1=0{,}6$, $c_2=0{,}4$ e inércia linear de 0,9 a 0,6. É uma variante
  experimental distinta, não atribuída ao SOG.
- **GIVP**: a configuração Optuna do SOG descrita acima.

Como no SOG, cada execução fixa uma vez a seed global do NumPy antes de chamar o
SciPy e o `pyswarm`. Por isso o `pyswarm` está fixado na versão 0.6: as versões
1.x são uma reescrita compilada com gerador próprio, que não reproduz as
trajetórias do SOG.

Os perfis de comparação usam as seeds pareadas `44` a `48`, os sete cenários
congelados, o mesmo vetor de 48 potências e a mesma projeção física:

| Perfil | Uso | Parada |
|---|---|---|
| [`interop/v1/sog_reproduction.json`](interop/v1/sog_reproduction.json) | descreve o comportamento das configurações do SOG | critérios nativos e limite de 900 s por execução para todos |
| [`interop/v1/budget_matched.json`](interop/v1/budget_matched.json) | comparação estatística | teto exato de 15.000 avaliações físicas e limite de 900 s por execução para todos |
| [`interop/v1/budget_matched_300s.json`](interop/v1/budget_matched_300s.json) | comparação com teto de cinco minutos por execução | teto de 15.000 avaliações físicas e limite de 300 s por execução para todos |
| [`interop/v1/budget_matched_300s_givp_80.json`](interop/v1/budget_matched_300s_givp_80.json) | piloto controlado do GIVP | mesmas condições do perfil de 300 s; `max_iterations` do GIVP aumentado de 40 para 80 |
| [`interop/v1/budget_matched_300s_upso_w03_c1wmin_c2wmax.json`](interop/v1/budget_matched_300s_upso_w03_c1wmin_c2wmax.json) | análise exploratória de sensibilidade do UPSO | mesmas condições do perfil de 300 s; hipótese `c1=0,6`, `c2=0,9`, `omega=0,3`; não confirmada como configuração do SOG |
| [`interop/v1/budget_matched_300s_true_upso.json`](interop/v1/budget_matched_300s_true_upso.json) | comparação direta de PSO com UPSO unificado real | PSO e UPSO usam os mesmos seeds, até 15.000 avaliações e limite de 300 s |

O perfil `budget_matched_300s.json` preserva o wrapper PSO que os notebooks do
SOG chamam de UPSO. Para uma comparação entre **PSO e UPSO unificado**, use
`budget_matched_300s_true_upso.json`; nesse perfil o campo `engine` seleciona
explicitamente a implementação UPSO local/global.

Nos perfis `budget-matched`, a chamada que ultrapassaria o teto é interrompida
antes de chegar ao simulador, e o algoritmo devolve o melhor ponto já avaliado
com término `evaluation_limit`; ao atingir o prazo, os algoritmos devolvem o
melhor ponto avaliado com término `time_limit`. O limite de tempo configurado
no bloco GIVP é compartilhado pelos quatro adaptadores. Uma avaliação física já
iniciada pode terminar depois do prazo antes de o otimizador ser interrompido.
Os acertos de cache do GIVP não contam como avaliação física. A reavaliação
final do vetor projetado é pós-processamento e não entra no orçamento. Cada
execução registra em `runs.csv` o perfil, as
avaliações, as iterações, o tempo, o motivo do término e as métricas hidráulicas
(energia, déficit, vertimento e níveis finais). O `campaign_metadata.json`
registra seeds, perfil efetivo com os limites compartilhados, versões das
bibliotecas e os commits do GIVP e do SOG de referência. Diretórios de saída
criados antes da aplicação do limite a todos os algoritmos devem ser substituídos
por um novo `--output-dir`; a campanha os recusa para evitar misturar resultados.

O experimento completo tem 140 execuções por perfil (sete cenários, quatro
algoritmos e cinco seeds). Uma interrupção pode ser retomada sem recalcular as
execuções já concluídas. Os resultados ficam em `output/`, fora do benchmark
congelado e ignorados pelo Git.

```powershell
cd python
poetry run python -m benchmarks.comparison.hydropower.campaign `
  --benchmark-root ../experiments/synthetic_hydropower/benchmarks/v1.0.0 `
  --profile ../experiments/synthetic_hydropower/interop/v1/budget_matched.json `
  --replications 5 `
  --output-dir ../experiments/synthetic_hydropower/output/sog_budget_matched

poetry run python -m benchmarks.comparison.hydropower.reporting `
  --runs ../experiments/synthetic_hydropower/output/sog_budget_matched/runs.csv `
  --output-dir ../experiments/synthetic_hydropower/output/sog_budget_matched/report
```

Para o perfil de reprodução, troque o perfil por `sog_reproduction.json` e use
outro diretório, por exemplo `output/sog_reproduction`.

O renderizador produz tabelas CSV e LaTeX, intervalos de confiança de 95%,
ranking, boxplots de objetivo, energia, déficit, vertimento e níveis finais,
mapa de calor, taxas de vitória e Wilcoxon pareado unilateral com correção de
Holm. O cenário `flood` também é relatado separadamente como guarda de robustez.

> **Resultados anteriores são testes técnicos.** Os diretórios já existentes em
> `output/` (`synthetic_hydropower_algorithm_comparison*`,
> `givp_tuned_7scenarios_5replications`, `structural_comparison_preliminary`)
> foram gerados com o perfil legado `hyperparameters.json` e os perfis
> `balanced_*`/`tuned_*` (schema v1). Neles, o PSO usava o `pyswarm` 1.x e o
> UPSO era um enxame unificado que não existe no SOG. Esses resultados não
> servem como resultados da dissertação. Resultados UPSO de campanhas sem o
> mesmo limite temporal dos demais algoritmos são excluídos das comparações.
> Os perfis SOG que rotulam o wrapper PSO como UPSO não devem ser apresentados
> como resultados de UPSO unificado. Para esse algoritmo, use a campanha
> `budget_matched_300s_true_upso.json`.

As cinco variantes da ablação podem ser executadas nos cenários de triagem sem
editar o perfil. Use diretórios de saída diferentes para `current`, `groups`,
`repair`, `multiscale` e `combined`:

```powershell
cd python
poetry run python -m benchmarks.comparison.hydropower.campaign `
  --benchmark-root ../experiments/synthetic_hydropower/benchmarks/v1.0.0 `
  --profile ../experiments/synthetic_hydropower/interop/v1/budget_matched.json `
  --algorithms GIVP --scenarios dry_stable typical flood `
  --replications 3 --givp-variant combined `
  --output-dir ../experiments/synthetic_hydropower/output/ablation/combined
```

O tuning usa seeds `0`, `1` e `2`; as seeds `44` a `48` ficam reservadas para
a comparação final e não participam da seleção de hiperparâmetros.

```powershell
cd python
poetry install -E hydropower -E notebooks
poetry run pytest tests/givp/examples/synthetic_hydropower
```

## Interface multilíngue

O balanço físico de referência continua sendo implementado somente em Python,
mas pode ser chamado localmente por R, Julia, Rust e C++ pelo protocolo
`synthetic-hydropower/v1`. O comando em lote recebe uma agenda de afluências e
potências sintéticas e grava a resposta JSON completa, sem depender do GIVP:

```powershell
synthetic-hydropower balance `
  --request experiments/synthetic_hydropower/interop/v1/zero_schedule_batch.json`
  --output response.json
```

Para algoritmos que avaliam várias soluções, `synthetic-hydropower worker`
mantém o processo Python ativo e usa uma linha JSON de entrada e uma de saída
por lote. Os schemas, um exemplo canônico e clientes mínimos ficam em
`interop/v1/` e `clients/`. Eles chamam o modelo de referência; não duplicam
equações nem incorporam parâmetros físicos aos outros pacotes GIVP.

O mesmo protocolo permite validar os 252 casos do balanço determinístico por
R, Julia, Rust e C++, sem criar quatro referências concorrentes. As respostas
derivadas são gravadas somente em `output/` (ignorado pelo Git) e comparadas aos
CSVs congelados em tolerância `1e-6`. O procedimento e os comandos por linguagem
estão em [`clients/README.md`](clients/README.md).

## Otimização multilíngue

`interop/v1/optimization_definition.json` estabelece uma execução comum do
GIVP para Python, R, Julia, Rust e C++. Ela usa o cenário congelado `typical`,
seed 44 e 48 potências horárias (A nas primeiras 24 posições e B nas demais).
Cada potência candidata é projetada para desligada ou para o intervalo mínimo–
máximo antes de ser enviada ao worker. O valor retornado ao otimizador é o
objetivo físico canônico: energia entregue, penalidades de níveis, chaveamento
e permanência mínima.

Os notebooks `optimization_*.ipynb` demonstram a execução por linguagem. Eles
precisam dos kernels Jupyter `ipykernel`, IRkernel, IJulia, evcxr e xeus-cling,
respectivamente. Defina `GIVP_ROOT` como a raiz do checkout e
`SYNTHETIC_HYDROPOWER_COMMAND` como o executável instalado antes de executá-los.
Os notebooks podem salvar análises locais em `output/`; elas não alteram o
benchmark congelado.

Abra e execute o notebook para carregar primeiro o protocolo
`deterministic_balance` do benchmark v1.0.0, sem chamar o GIVP. Ele informa os
sete cenários e apresenta a matriz 6×6 de potência de cada um. A comparação com
o GIVP fica em uma seção opcional e não modifica os CSVs canônicos.

## Notebook

Abra `experiments/synthetic_hydropower/notebooks/hydropower_two_plant_synthetic.ipynb`.
Ele importa o modelo pelo namespace `givp.examples.synthetic_hydropower`, usa
automaticamente a configuração-base empacotada e cria
`experiments/synthetic_hydropower/output/` para os resultados locais.

O módulo experimental `notebooks/figures.py` concentra as figuras dos protocolos
`givp_optimization` e `deterministic_balance` do benchmark v1.0.0. Ele permanece
junto ao notebook porque transforma os resultados apenas para apresentação e não
faz parte da API nem do wheel do GIVP.

O cálculo determinístico pode ser refeito sem notebook pela API
`givp.examples.synthetic_hydropower.benchmark`, usando explicitamente os
caminhos de `benchmarks/v1.0.0/config/base.json`,
`protocols/deterministic_balance/definition.json` e `inputs/inflows.csv`.

## Benchmark público e preservação

Os resultados locais são deliberadamente ignorados pelo Git para não confundir
execuções parciais com uma referência científica. O procedimento para promover
uma execução completa a benchmark versionado e publicar a referência congelada
está em [`benchmarks/README.md`](benchmarks/README.md). A publicação usa o
Zenodo como arquivo canônico
(<https://doi.org/10.5281/zenodo.22185079>) e o HydroShare como recurso
hidrológico complementar (<https://doi.org/10.4211/hs.4d1e221b0638437f98847addc3e709c6>);
detalhes, licenças e metadados estão em
[`benchmarks/v1.0.0/PUBLICATION.md`](benchmarks/v1.0.0/PUBLICATION.md).
