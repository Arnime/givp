# Cascata hidrelétrica sintética

Experimento acadêmico reproduzível para otimizar a geração de duas usinas
hidrelétricas fictícias em cascata. Os notebooks e o benchmark pertencem a
`experiments/`; a implementação reutilizável é disponibilizada como o exemplo
opcional `givp.examples.synthetic_hydropower` do pacote GIVP.

## Independência do material proprietário

Este experimento não reutiliza código, planilhas, coeficientes, estatísticas,
nomes de ativos ou regras operacionais do SOG2/CERAN. Todos os parâmetros,
cenários e relações físicas são fictícios e foram definidos apenas para fins
didáticos e reprodutíveis.

## Modelo

Os rótulos A e B, os valores e as séries não representam ativos reais. O
experimento preserva apenas relações físicas genéricas necessárias para estudar
uma cascata curta, sem pretensão de reproduzir a operação de qualquer ativo.

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
- Polinômios de quarto grau sintéticos e normalizados, sem calibração contra
  curvas reais, tabelas operativas ou coeficientes proprietários.
- Rendimento constante; não há curvas de colina, perdas hidráulicas explícitas,
  múltiplas máquinas, zonas de operação, tempos mínimos de operação, rampas ou
  custos.
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
A função minimizada é `-energia_gerada + penalidade_de_nível`: a única
penalidade é quadrática para níveis de montante abaixo do mínimo ou acima do
máximo. A cada período e para cada usina, o simulador acumula separadamente
`w·max(0, nível_mínimo − nível_final)²` e
`w·max(0, nível_final − nível_máximo)²`; a soma das duas parcelas é a
penalidade de nível usada pela função objetivo.

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
exclusivamente os parâmetros fictícios das duas usinas. O horizonte, os sete
cenários sintéticos e os parâmetros do GIVP ficam declarados no notebook para
tornar explícita a configuração do experimento.

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
poetry run pytest tests/examples/synthetic_hydropower
```

Abra e execute o notebook para rodar os cenários. Antes da otimização, sua
célula de configuração informa quantos cenários serão executados e seus nomes.
Após cada cenário concluído, o notebook atualiza os resultados em `output/`:
`benchmark_summary.csv`, `benchmark_time_series.csv` e
`benchmark_manifest.json`. O manifesto registra as seeds e o checksum da
configuração física fictícia usada.

## Notebook

Abra `experiments/synthetic_hydropower/notebooks/hydropower_two_plant_synthetic.ipynb`.
Ele importa o modelo pelo namespace `givp.examples.synthetic_hydropower`, usa
automaticamente a configuração-base empacotada e cria
`experiments/synthetic_hydropower/output/` para os resultados locais.

O módulo experimental `notebooks/figures.py` concentra a geração das três
figuras de cada cenário (potência, vazões e níveis). Ele permanece junto ao
notebook porque transforma os resultados apenas para apresentação e não faz
parte da API nem do wheel do GIVP.

O mesmo modelo pode ser executado sem notebook, sempre com caminhos explícitos:

```powershell
cd python
poetry run synthetic-hydropower --config src/givp/examples/synthetic_hydropower/configs/base.json --output-dir ../experiments/synthetic_hydropower/output --seed 42
```

Por segurança, o comando reproduz somente o caso oficial do benchmark: o
`base.json` empacotado e a pasta `output/` acima formam uma lista explícita de
caminhos permitidos. Experimentos com outros arquivos podem usar diretamente
`load_experiment_config` e `optimize_scenario` pela API Python, sob controle do
programa chamador.

## Benchmark público e preservação

Os resultados locais são deliberadamente ignorados pelo Git para não confundir
execuções parciais com uma referência científica. O procedimento para promover
uma execução completa a benchmark versionado e publicá-la em nuvem está em
[`benchmarks/README.md`](benchmarks/README.md). A publicação em uma release
imutável e em um repositório de dados com DOI requer a conta de destino e uma
autorização explícita.
