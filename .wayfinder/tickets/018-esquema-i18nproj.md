---
id: 18
title: Esquema e portabilidade do arquivo .i18nproj
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [6, 7, 8, 9, 10, 11, 13, 16]
parent: map
---

## Question

Qual é o esquema exato e a portabilidade do arquivo `.i18nproj`?

- **Caminhos dos arquivos:** armazenar caminhos **relativos** ao `.i18nproj` (portável quando o projeto fica na pasta do módulo/git), relativos à pasta do pacote (`package_root`), ou absolutos com fallback?
- **Estrutura de seções no `.i18nproj`:** `schema_version`, `project_id` (para backups em `%APPDATA%`), `package` (manifest + base + `base_external_path` opcional + destinos + mapeamento de arquivos para `missing`), `snapshots` (SHA-256 + mapa de valores da base e de cada destino), `drafts` (edições locais e remoções de órfãs pendentes), `review_state` (`review_status` + `previous_base` p/ `stale`), `ignored_warnings` (placeholders/glossário), `custom_enrichers`, `project_glossary`.
- **Salvamento e versionamento:** salvar automaticamente ao fechar ou apenas manual (`Salvar` / `Ctrl+S` com indicador de não salvo + recuperação de crash)? Política de `schema_version` ao abrir versão antiga/futura.

## Resolução

- **Caminhos e portabilidade:**
  - Armazena `package_root_rel` (relativo ao diretório do `.i18nproj`, quando no mesmo drive) + `package_root_abs` como fallback. Ao abrir: tenta relativo primeiro, depois absoluto; se nenhum existir, exibe diálogo *"Relocalizar pasta do pacote"*.
  - Os arquivos de idioma são referenciados **relativos ao `package_root`** (ex.: `lang/pt-BR.json`); eventual `base_external_path` (ticket [016](016-base-e-multiplos-arquivos.md)) usa o mesmo par relativo + absoluto.
- **Onde fica salvo:** escolha livre do usuário no *"Salvar Projeto"*, sugerindo por padrão uma pasta fora do repo git do módulo (ex.: `%APPDATA%\i18n-reviewer\projects\` ou Documentos), mas permitindo salvar dentro do pacote caso deseje versionar no git.
- **Ciclo de salvamento:** **manual explícito** (`Salvar` / `Ctrl+S`, marcador `*` de alterações não salvas na janela + confirmação ao fechar), acompanhado de **rascunho automático de recuperação de crash** em `%APPDATA%\i18n-reviewer\recovery\<project_id>.json` (apagado ao salvar ou fechar normalmente).
- **Esquema JSON v1 (gravado com `indent=2, ensure_ascii=False` e `os.replace`):**
  - `schema_version`: `1`
  - `project_id`: UUID estável (vincula backups em `%APPDATA%` e recovery)
  - `package`: `{manifest_type, package_id, package_root_rel, package_root_abs, base_lang, base_external_path, target_langs[], files[] (lang, path, conditional, enabled), missing_target_mapping}`
  - `snapshots`: `{files: {rel_path: {sha256, entries: {key_path: str}}}}` (estado conhecido em disco na última carga/sincronização/publicação)
  - `drafts`: `{edits: {lang: {key_path: str}}, deletions: {lang: [key_path]}}` (apenas diferenças locais não enviadas)
  - `review_state`: `{lang: {key_path: {status: "unreviewed"|"reviewed"|"stale", previous_base?: str}}}`
  - `ignored_warnings`: lista de `{key_path, lang, rule_id, reason?, value_hash}`
  - `custom_enrichers`: regras/regex extras do projeto ([010](010-politica-placeholders.md))
  - `project_glossary`: entradas de glossário locais do projeto ([011](011-modelo-glossario.md))
- **Política de `schema_version`:** versões anteriores migram automaticamente criando antes uma cópia de segurança do `.i18nproj`; `schema_version` maior que a suportada pelo app recusa abrir com mensagem orientando atualizar o i18n Reviewer.


