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
do mínimo ou acima do máximo. A cada período e para cada usina, o simulador acumula separadamente
`w·max(0, nível_mínimo − nível_final)²` e
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

O arquivo empacotado
`python/src/givp/examples/synthetic_hydropower/configs/base.json` contém
exclusivamente os parâmetros das duas usinas sintéticas. Horizonte, cenários,
seeds e protocolo pertencem às definições versionadas em `benchmarks/`; os
parâmetros do GIVP aparecem somente na seção opcional do notebook.

Os parâmetros finais documentados para o GIVP na dissertação são usados no
notebook: 40 iterações, $\alpha=0{,}17$, VND=15, ILS=5, perturbação=8,
15 candidatos por passo, conjunto elite de tamanho 4 e PR a cada 10 iterações.
O cache de 10.000 avaliações e o monitor de convergência seguem o protocolo
descrito. O orçamento de 900 s dos experimentos completos do SOG não é
transportado para esta instância sintética de 24 períodos; os valores finais de
$\alpha_{min}$, $\alpha_{max}$, limiar de parada e número de trabalhadores não
foram publicados na tabela de resultados e permanecem nos padrões do GIVP.

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
  --request experiments/synthetic_hydropower/interop/v1/zero_schedule_batch.json `
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
`deterministic_balance` do benchmark v1.0.0, sem chamar o GIVP. Ele informa os sete cenários e apresenta a matriz
6×6 de potência de cada um. A comparação com o GIVP fica em uma seção opcional
e não modifica os CSVs canônicos.

## Notebook

Abra `experiments/synthetic_hydropower/notebooks/hydropower_two_plant_synthetic.ipynb`.
Ele importa o modelo pelo namespace `givp.examples.synthetic_hydropower`, usa
automaticamente a configuração-base empacotada e cria
`experiments/synthetic_hydropower/output/` para os resultados locais.

O módulo experimental `notebooks/figures.py` concentra as figuras dos protocolos
`givp_optimization` e `deterministic_balance` do benchmark v1.0.0. Ele permanece junto ao
notebook porque transforma os resultados apenas para apresentação e não faz
parte da API nem do wheel do GIVP.

O cálculo determinístico pode ser refeito sem notebook pela API
`givp.examples.synthetic_hydropower.benchmark`, usando explicitamente os
caminhos de `benchmarks/v1.0.0/config/base.json`,
`protocols/deterministic_balance/definition.json` e `inputs/inflows.csv`.

## Benchmark público e preservação

Os resultados locais são deliberadamente ignorados pelo Git para não confundir
execuções parciais com uma referência científica. O procedimento para promover
uma execução completa a benchmark versionado e publicá-la em nuvem está em
[`benchmarks/README.md`](benchmarks/README.md). A publicação em uma release
imutável e em um repositório de dados com DOI requer a conta de destino e uma
autorização explícita.
