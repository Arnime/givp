# Clientes multilíngues

Estes exemplos consomem o motor de referência Python pelo protocolo local
`synthetic-hydropower/v1`. Eles não contêm equações de balanço hídrico nem
parâmetros das usinas. Os demos `optimize` usam o GIVP nativo de cada
linguagem para escolher 48 potências horárias e devolvem o objetivo físico
canônico calculado pelo worker Python.

Instale primeiro o motor:

```powershell
cd python
poetry install -E hydropower
```

O arquivo `../interop/v1/optimization_definition.json` define o cenário
`typical`, a seed, a ordem A→B das 48 decisões, a projeção para potência
desligada ou mínima–máxima e a configuração reduzida do GIVP. Para integrar
um otimizador, mantenha o processo `synthetic-hydropower worker` ativo; uma
linha JSON recebida no `stdin` produz uma linha JSON no `stdout`.

| Linguagem | Dependência de JSON | Demo de otimização |
| --- | --- | --- |
| Python | pacote GIVP | `python/optimize.py` |
| R | `jsonlite`, `processx` | `r/optimize.R` |
| Julia | `JSON` | `julia/optimize.jl` |
| Rust | `serde_json` | `rust/src/optimize.rs` |
| C++ | `nlohmann_json` | `cpp/optimize.cpp` |

Os clientes são exemplos acadêmicos e não pertencem às APIs publicadas dos
pacotes GIVP de cada linguagem. No Windows, os adaptadores iniciam
`python.exe -u synthetic-hydropower worker` diretamente para não depender do
wrapper `.cmd`. Chamadas unitárias a processos externos são inadequadas para
experimentos grandes; cada demo mantém um worker ativo durante a otimização.

## Validar o balanço determinístico completo

O protocolo `deterministic_balance` congelado contém 252 agendas: os sete
cenários de afluência cruzados com as seis potências constantes de A e as seis
de B. R, Julia, Rust e C++ podem avaliar o lote completo, mas suas saídas são
**artefatos derivados de interoperabilidade**, nunca novos `reference_results`.
Cada cliente chama a mesma referência física Python e grava uma resposta JSON;
o script Python transforma essa resposta nas tabelas canônicas e a compara com
os CSVs congelados em tolerância `1e-6`.

Partindo da raiz do checkout, crie o lote JSON Lines uma vez:

```powershell
cd python
$protocol = Resolve-Path "..\experiments\synthetic_hydropower\benchmarks\v1.0.0\protocols\deterministic_balance"
$version = Split-Path (Split-Path $protocol -Parent) -Parent
poetry run python ..\experiments\synthetic_hydropower\scripts\validate_deterministic_interop.py `
  --inflows (Join-Path $version "inputs\inflows.csv") `
  --schedules (Join-Path $protocol "inputs\power_schedules.csv") `
  --request-output ..\experiments\synthetic_hydropower\output\interop\deterministic_balance\request.json `
  --reference-dir (Join-Path $protocol "reference_results") `
  --output-dir ..\experiments\synthetic_hydropower\output\interop\deterministic_balance\python
```

Os clientes aceitam agora `client <request.json> [response.json]`. Passe o
segundo argumento para gravar a resposta em
`experiments/synthetic_hydropower/output/interop/deterministic_balance/<linguagem>/`.
Depois valide-a com o mesmo comando, trocando `--request-output` por
`--response .../<linguagem>/response.json` e `--output-dir` pela pasta da
linguagem. O resultado esperado é `validated 12348 rows`: 12.096 observações
horárias e 252 linhas-resumo.

No Windows, execute o R com `Rscript --vanilla` e a biblioteca do `renv` já
ativada para evitar carregar `.Rprofile` duas vezes. Rust e C++ devem usar os
comandos WSL abaixo. O cliente C++ lê o lote por redirecionamento de entrada;
assim, o tamanho das 252 agendas não fica sujeito ao limite de argumentos do
shell.

## Executar uma demonstração por linguagem

Todos os comandos abaixo usam apenas a definição congelada `typical`: são 24
períodos e 48 decisões (as 24 potências de A, seguidas das 24 de B). O JSON
final contém o objetivo do baseline desligado, o objetivo do otimizador, a
reavaliação física canônica, a energia, a penalidade de nível e a agenda final.
Os melhores vetores e valores podem divergir entre linguagens por causa das
trajetórias metaheurísticas próprias, mas cada resultado deve melhorar ou
igualar o baseline e coincidir com sua reavaliação física em `1e-6`.

### R e Julia no Windows

Execute a partir da raiz do checkout. A instalação do R deve usar o `renv/` do
projeto e o GIVP R precisa estar instalado, conforme o README de `r/`.

```powershell
$env:PYTHONPATH = (Resolve-Path ".\python\src").Path
$env:SYNTHETIC_HYDROPOWER_COMMAND = (Resolve-Path ".\python\.venv\Scripts\synthetic-hydropower.cmd").Path
$env:RENV_PROJECT = (Resolve-Path ".\r").Path

Rscript .\experiments\synthetic_hydropower\clients\r\optimize.R `
  .\experiments\synthetic_hydropower\interop\v1\optimization_definition.json

julia --project=.\julia `
  .\experiments\synthetic_hydropower\clients\julia\optimize.jl `
  .\experiments\synthetic_hydropower\interop\v1\optimization_definition.json
```

### Rust e C++ no WSL

Use o WSL para Rust e C++. Isso evita a limitação local do Cargo no Windows
com Schannel e usa um processo Python Linux para o worker bidirecional. Uma vez
por ambiente WSL, prepare a venv de referência, o compilador C++ e o Rustup:

```bash
sudo apt-get update
sudo apt-get install --yes cmake g++ nlohmann-json3-dev python3-venv
cd "/mnt/d/Projetos Pessoais/GIVP"
python3 -m venv "$HOME/.venvs/givp-hydropower"
"$HOME/.venvs/givp-hydropower/bin/pip" install --upgrade pip
"$HOME/.venvs/givp-hydropower/bin/pip" install -e "./python[hydropower]"
curl --proto '=https' --tlsv1.2 --fail --silent --show-error https://sh.rustup.rs | sh -s -- -y --profile minimal
source "$HOME/.cargo/env"
```

Depois, ainda no WSL e na raiz Linux do checkout, execute os dois clientes:

```bash
cd "/mnt/d/Projetos Pessoais/GIVP"
export SYNTHETIC_HYDROPOWER_COMMAND="$HOME/.venvs/givp-hydropower/bin/synthetic-hydropower"

cargo run --manifest-path experiments/synthetic_hydropower/clients/rust/Cargo.toml \
  --bin synthetic-hydropower-optimize -- \
  experiments/synthetic_hydropower/interop/v1/optimization_definition.json

cmake -S experiments/synthetic_hydropower/clients/cpp -B /tmp/givp-hydropower-cpp
cmake --build /tmp/givp-hydropower-cpp --parallel 2
/tmp/givp-hydropower-cpp/synthetic_hydropower_optimize \
  experiments/synthetic_hydropower/interop/v1/optimization_definition.json
```

O `PYTHONUNBUFFERED=1` é configurado internamente pelos clientes POSIX. Não é
necessário iniciar o worker à parte nem copiar qualquer equação hidráulica para
as outras linguagens.

### Notebooks

Os notebooks `optimization_python.ipynb`, `optimization_r.ipynb`,
`optimization_julia.ipynb`, `optimization_rust.ipynb` e
`optimization_cpp.ipynb` são demonstrações da mesma definição. Para os
notebooks Rust e C++ no Windows, prefira os comandos WSL acima até que haja um
kernel Jupyter integrado ao WSL configurado; a física e o resultado são os
mesmos.
