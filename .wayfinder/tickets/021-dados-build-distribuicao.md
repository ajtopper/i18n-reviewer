---
id: 21
title: Dados do app, build PyInstaller e distribuição Windows
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [5, 12, 13, 17]
parent: map
---

## Question

Como ficam organizados os dados persistentes do aplicativo, o arquivo `spec/build.spec` e o pacote final de distribuição no Windows?

- **Estrutura em `%APPDATA%\i18n-reviewer\`:** `glossary.json` (global), `enchant\hunspell\` + PWLs, `backups\<project_id>\`, `settings.json` (preferências da UI, projetos recentes, retenção de backups).
- **Contorno não-ASCII do Hunspell no Windows:** copiar dicionários empacotados/usuário ou resolver `ENCHANT_CONFIG_DIR` via caminho curto 8.3 (e fallback para `%TEMP%\i18n-reviewer-hunspell` caso 8.3 esteja desabilitado no volume) + autoverificação com palavra-sentinela.
- **Enxugamento do `.spec` e `requirements.txt`:** `PySide6-Essentials`, `pyenchant`, `pyinstaller`; excluir módulos Qt não usados (`QtWebEngine`, `QtQml`, `Qt3D` etc.) e DLLs MSYS2 ociosas (ex.: `readline`, `gettext-tools`, `nuspell`/ICU) reduzindo de ~120 MB para ~39 MB só de enchant; `module_collection_mode={'enchant': 'py'}` pela LGPL-2.1.
- **Licenciamento e distribuição:** licença do app vs. `de_DE_frami` (GPL — inclui pasta `licenses/` com textos e indicação de fonte), formato de entrega (`.zip` portátil vs. instalador Inno Setup), ícone.

## Resolução

- **Estrutura persistente em `%APPDATA%\i18n-reviewer\`:**
  - `settings.json`: preferências de UI, projetos recentes, retenção padrão de backups (30 lotes), eventual pasta ASCII alternativa do Hunspell.
  - `glossary.json`: glossário global do usuário.
  - `enchant\hunspell\` + `<lang>.dic/.exc` (PWLs globais): definido via `ENCHANT_CONFIG_DIR` antes de importar `enchant`.
  - `backups\<project_id>\`: lotes de backup agrupados por projeto ([013](013-politica-backups.md)).
  - `recovery\<project_id>.json`: rascunho de recuperação de crash ([018](018-esquema-i18nproj.md)).
- **Alvo Python e dependências (`requirements.txt` / `requirements-build.txt`):**
  - Alvo oficial de build: **CPython 3.14.x 64-bit** (substitui `3.11+` + `pyspellchecker` da spec inicial).
  - Runtime: `PySide6-Essentials==6.12.0`, `shiboken6==6.12.0`, `pyenchant==3.3.0`.
  - Build: `pyinstaller==6.22.3`, `pyinstaller-hooks-contrib==2026.10`.
- **Build `spec/build.spec` (`--onedir --windowed`):**
  - Excluir módulos Qt não utilizados (`QtWebEngine*`, `QtQml`, `QtQuick`, `Qt3D*`, `QtMultimedia*`, `QtPdf*`).
  - Filtrar `enchant`: manter apenas `libenchant-2`, `enchant_hunspell` e suas 8 DLLs dependentes (excluindo `nuspell`/ICU e as ~38 DLLs MSYS2/GPLv3 não usadas, caindo a parte do enchant de ~120 MB para ~39 MB); empacotar apenas `en_US` + `pt_BR`, `es_ES`, `fr_FR`, `de_DE`.
  - Configurar `module_collection_mode={'enchant': 'py'}` (conformidade LGPL-2.1) e incluir pasta `licenses/` com todos os avisos, licenças e links para as formas-fonte dos dicionários e do Enchant/Hunspell.
- **Contorno não-ASCII do Hunspell no Windows:** se o caminho dos dicionários empacotados ou `ENCHANT_CONFIG_DIR` contiver caracteres não-ASCII, resolver via `GetShortPathNameW` (8.3); se o volume não gerar 8.3, usar pasta ASCII configurada em `settings.json` — validando sempre com **palavra-sentinela** na carga para nunca falhar silenciosamente.
- **Entrega:** `.zip` portátil da pasta `dist/i18n-reviewer/` (com script Inno Setup opcional no repositório e ícone `.ico`), acompanhado da pasta `licenses/` (app MIT com dicionários externos substituíveis, ou GPL-3.0 caso prefira zero ambiguidade sobre `de_DE_frami`).


