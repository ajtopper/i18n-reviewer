---
id: 22
title: Estratégia de testes e critérios de aceitação
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [7, 18, 19, 20]
parent: map
---

## Question

Quais testes automatizados e critérios de aceitação garantem que a implementação atende todas as decisões do mapa?

- **Suite e ferramentas:** `pytest` + `pytest-qt` + fixtures em cópias (nunca modificando `hearthbound` original).
- **Testes obrigatórios de núcleo:**
  - Round-trip byte a byte com o `json_handler`: sem edições → bytes idênticos; edições pontuais em arquivos não-canônicos (linhas em branco, objetos inline, `"k" : "v"`, `\uXXXX`, CRLF/LF, BOM, sem newline final) → diff apenas nas linhas tocadas.
  - Inserção relativa à base (plano, aninhado, misto) e remoção de órfãs podando objetos pais vazios.
  - Merge 3-vias + `stale` + conflitos estruturais + arquivos malformados (duplicadas, folha-antes-de-ramo).
  - Pipeline pré-produção + escrita atômica (incluindo simulação de `PermissionError` / falha parcial + restauração de backup + `pre-restore`).
  - Extrator de placeholders/enrichers (core + dnd5e + pf2e + genéricos), glossário e `SpellService` (incluindo palavra-sentinela e caminhos com acento).
- **Smoke test de build:** script pós-PyInstaller verificando que o `.exe` congelado abre headless/autoteste e valida os 4 idiomas sem depender do Python instalado.

## Resolução

- **Suite e fixtures (`tests/`):** `pytest` + `pytest-qt` em `requirements-dev.txt`. Fixtures autocontidas em `tests/fixtures/` cobrindo todos os cenários reais (canônico, não-canônico com linhas em branco/objetos inline/`"k" : "v"`, misto, duplicadas, folha-antes-de-ramo, `\uXXXX` + BOM + CRLF/LF, plano×aninhado, multi-arquivo e plurais CLDR), mais testes de integração opcionais em cópia do `hearthbound` (pulados se o caminho local não existir).
- **Cobertura obrigatória de `core/`:**
  - `json_handler`: round-trip byte a byte sem edições; diff mínimo em edições pontuais sobre arquivos não-canônicos; inserção relativa à base (plano/aninhado/misto); remoção de órfãs podando pais vazios; detecção de duplicadas e erros fatais.
  - `project_manager`: `.i18nproj` v1, portabilidade relativo/absoluto + relocalização, crash recovery, merge 3-vias, `stale` com `previous_base`, conflito estrutural e `.many`.
  - `backup_manager` & pipeline pré-produção: seleção parcial de idiomas, bloqueios críticos, simulação `expandObject`, retries de `PermissionError` (OneDrive), falha parcial + rollback do lote e restauração com `pre-restore`.
  - Serviços de validação: extrator em cascata (core/dnd5e/pf2e/genéricos/exceções), glossário 2 níveis + CSV + `\b`/mascaramento, e `SpellService` (incluindo contorno não-ASCII e palavra-sentinela).
- **Cobertura de UI (`pytest-qt`) e escala:** filtros/busca (debounce), `QUndoStack` (`Ctrl+Z`/`Ctrl+Y`), atalhos (`Ctrl+Enter`, `Ctrl+Down`, `Ctrl+Space`), resolução de conflitos e smoke de desempenho com fixture sintética de **10 000 chaves**.
- **Smoke test do executável (`--self-test`):** `app/main.py` expõe modo `--self-test` para rodar após o `pyinstaller spec/build.spec`, verificando inicialização Qt offscreen e carregamento + sentinela de `pt_BR`, `es_ES`, `fr_FR` e `de_DE` no `.exe` congelado (`exit 0`).


