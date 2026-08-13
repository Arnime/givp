# Componentes reutilizáveis da CI

As ações compostas em `.github/actions/` concentram os pins e defaults usados
pela CI. Um workflow deve fazer checkout antes de chamar uma ação local.

- `setup-python`: recebe `python-version` (padrão `3.13`) e
  `allow-prereleases`.
- `setup-rust`: recebe `toolchain`, `components`, `cache` e `workspaces`.
- `setup-julia`: recebe `version`, `project`, `cache` e
  `delete-old-caches`.
- `setup-r`: recebe `r-version`, `working-directory`, `extra-packages` e
  `cache`.
- `publish-pypi`: recebe `packages-dir`, `repository-url`, `skip-existing` e
  `attestations`. O workflow chamador mantém o ambiente protegido e a
  permissão `id-token: write`, necessários ao Trusted Publisher.
- `release-assets`: recebe a tag, os arquivos e os campos opcionais de uma
  release, como nome, corpo, arquivo de corpo e pre-release.

Para uma automação nova, reutilize primeiro um desses componentes. Não copie
o pin de uma action centralizada para um workflow. A checagem
`check-centralized-actions.sh` impede essa regressão nos workflows de CI e
release das linguagens.

Pins de `actions/checkout` e integrações de segurança ou especializadas
(CodeQL, Sonar, Scorecard e SLSA) permanecem explícitos nos workflows. O
Dependabot, configurado para `github-actions`, abre PRs semanais para manter
esses pins e os componentes atualizados.
