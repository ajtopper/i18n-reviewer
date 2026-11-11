---
title: "i18n Reviewer — mapa até a spec de implementação"
labels: [wayfinder:map]
status: closed
---

## Destination

Uma **spec de implementação travada** do i18n Reviewer: todas as decisões de comportamento, formato e arquitetura
resolvidas, pronta para ser fatiada em tickets de build (`to-spec` / `to-tickets`). O mapa termina quando não
resta nada a decidir antes de alguém começar a codar.

> **Concluído:** especificação final publicada em [docs/spec-implementacao.md](../docs/spec-implementacao.md) (`labels: [ready-for-agent, spec]`).

## Notes

- **Entrada:** [Especificação Técnica Inicial](../docs/spec-inicial.md). Decisões nos tickets prevalecem sobre ela.
- **Tracker:** local em markdown — ver [README do tracker](README.md). Fronteira = tickets `open`, desbloqueados, sem `assignee`.
- **Idioma:** mapa, tickets e spec em português.
- **Domínio:** arquivos de idioma de módulos/sistemas do Foundry VTT (`lang/*.json`), revisão humana de tradução, escrita segura em produção.
- **Skills por sessão:** grilling + domain-modeling (via `grill-with-docs`) para tickets de grilling; `research` para tickets de research; `prototype` para protótipos.
- **Premissas fixadas no charting (pelo usuário):**
  - A escrita em produção **preserva exatamente o estilo e a ordem de chaves** de cada arquivo (substitui o "unflatten com indent=2" da spec inicial).
  - Os arquivos de idioma são descobertos lendo o **`module.json`/`system.json`** (array `languages`).
  - Corretor ortográfico no dia 1 para **pt-BR, es, fr, de**.
- **Plan, don't do:** produzir decisões, não código de produção. Protótipos são descartáveis.
- **Módulo de exemplo (caso de referência):** `C:\Users\ajtop\OneDrive\Documents\foundry-vtt-dev\Data\modules\hearthbound` (Foundry v14, repo git próprio). Usar só leitura; testes/protótipos trabalham em **cópias**. Fatos levantados no charting:
  - `module.json` → `languages`: `en` (base), `pt-BR`, `es`, `eo` (Esperanto — fora da lista de corretor do dia 1).
  - 4 arquivos com as mesmas 1314 chaves-folha, ~130 KB cada; 100% aninhados (0 chaves pontuadas), indent 2, **CRLF**, newline final, sem BOM, sem `\uXXXX`.
  - `json.dumps(indent=2, ensure_ascii=False)` + CRLF + newline final reproduz os 4 arquivos **byte a byte**.
  - 186 placeholders `{x}` por arquivo; nenhum HTML nem enricher.

## Decisions so far

<!-- uma linha por ticket fechado: [nome do ticket](tickets/NNN-slug.md): gist da resposta -->

- [Formato real dos arquivos de idioma e do manifest no Foundry](tickets/001-formato-lang-files-foundry.md): `languages[]` = lang/name/path (+ system/module condicionais), vários arquivos por lang; o core expande plano≡aninhado≡misto e mescla core→sistema→módulos (último vence), fallback para `en`; vários arquivos reais (core, dnd5e, daggerheart) não são canônicos → preservação exata exige escrita por spans; hearthbound é canônico.
- [Sintaxes embutidas em strings de localização do Foundry](tickets/003-sintaxes-embutidas-foundry.md): na v14 `format`≡`localize` (`{nome}` ausente vira "undefined"); enrichers (`@UUID`, `@Embed`, `[[...]]`, `&Reference`, `@Check`…) e HTML seguem "parte técnica idêntica, rótulo traduzível"; o conjunto de enrichers é aberto e varia por sistema, e o arquivo não revela se o valor é formatado ou renderizado como HTML.
- [Round-trip fiel de JSON em Python](tickets/002-round-trip-json-python.md): stdlib com estilo detectado só é byte a byte em arquivos canônicos; round-trip garantido exige edição cirúrgica por spans (tree-sitter-json ou scanner próprio) ou json-five; duplicadas detectáveis com `object_pairs_hook`.
- [Compatibilidade da stack com o Python instalado](tickets/005-compatibilidade-stack-python.md): alvo CPython 3.14.x 64-bit com PySide6-Essentials 6.12.0, pyspellchecker 0.9.1 e PyInstaller 6.22.3 (build `--onedir --windowed` validado); `--collect-data spellchecker` é obrigatório.
- [pyspellchecker para pt-BR, es, fr, de](tickets/004-pyspellchecker-idiomas.md): pyspellchecker inadequado (`pt` é pt-PT, `es` sem flexões, fr/de falham em elisões/compostos, sem eo; 4,4%/24,5% de falsos alarmes no hearthbound vs. 0,7%/2,1% do Hunspell) → recomendação: pyenchant (Hunspell) + dicionários LibreOffice atrás de interface própria.
- [Empacotamento de dicionários Hunspell](tickets/017-empacotamento-dicionarios-hunspell.md): viável congelar `pyenchant` no `--onedir` Windows (120 MB cru → ~39 MB enxuto removendo DLLs MSYS2/GPLv3 ociosas); requer `ENCHANT_CONFIG_DIR` gravável, contorno para bug silencioso em caminhos não-ASCII e atenção à licença GPL de `de_DE_frami`/`eo`.
- [Ciclo de vida do status por chave](tickets/008-ciclo-de-vida-status.md): modelo em 2 eixos (`review_status`: `unreviewed`/`reviewed`/`stale` + `dirty` derivado por comparação ao snapshot, `missing` derivado); aprovação explícita, edição rebaixa para `unreviewed`, Enviar para Produção limpa `dirty` (confirma se houver `dirty` não revisadas) e preserva `review_status` no `.i18nproj`.
- [Detecção de alteração externa e resolução de conflito](tickets/009-alteracao-externa-conflito.md): detecção por SHA-256 na abertura, antes do envio e passiva via watcher/foco; merge 3 vias por chave (`snapshot × disco × rascunho`) com diálogo lado a lado bloqueando envio até resolver; mudança na base marca destinos `reviewed` como `stale` guardando `previous_base`.
- [Política de placeholders e conteúdo protegido](tickets/010-politica-placeholders.md): extração em cascata (embutido core/dnd5e/pf2e + heurística genérica + regras no `.i18nproj`); erros críticos (nomes únicos `{x}`, `{{hbs}}`, parte técnica de enricher) bloqueiam envio salvo exceção no `.i18nproj`; avisos (repetições, HTML, URL) pedem confirmação; defeito na base só informa; editor normal com destaque colorido e reinserção rápida.
- [Modelo do glossário](tickets/011-modelo-glossario.md): dois níveis (Global `glossary.json` + Projeto no `.i18nproj`, projeto sobrescreve); entrada com `do_not_translate`, variantes/flexões explícitas por idioma (1ª = preferida); matching por `\b`, mais longo vence, ignorando spans técnicos; apenas aviso (com exceção ignorável); `Ctrl+Space` com popup no cursor; import/export JSON + CSV.
- [Política do corretor ortográfico](tickets/012-politica-corretor.md): troca `pyspellchecker` por `pyenchant` (Hunspell) atrás de interface própria, empacotando `pt_BR`, `es_ES`, `fr_FR`, `de_DE` + pasta `%APPDATA%\i18n-reviewer\enchant\hunspell\` p/ usuário; PWL global + glossário do projeto; mascara spans técnicos, MAIÚSCULAS, números, ≤2 letras e iguais à base; `check()` assíncrono/lazy + `suggest()` sob demanda; contorno ASCII/8.3 + sentinela no Windows.
- [Política de backups e restauração](tickets/013-politica-backups.md): backups em `%APPDATA%\i18n-reviewer\backups\<project_id>\` (fora do git do módulo), agrupados por envio (`publish`/`pre-restore`, só arquivos alterados, restaurável por lote ou arquivo); retenção padrão 30 lotes + manual; restauração cria `pre-restore`, usa `os.replace` e deixa escolher entre sincronizar (merge 3-vias) ou descartar rascunhos locais.
- [Protótipo da tabela multilíngue de revisão](tickets/014-prototipo-tabela.md): layout aprovado (`QTableView` com checkboxes por idioma, badge no topo direito com margem reservada, faixa esquerda vermelha/âmbar por severidade, cores por estado + `EDITADO · OK`, editor `QPlainTextEdit`, Inspector retrátil à direita, rodapé numérico e atalhos `F2`/`Ctrl+Space`/`Ctrl+Enter`/`Ctrl+Down`/`Ctrl+F`).
- [Política para arquivos de idioma malformados](tickets/015-arquivos-malformados.md): nunca corrige estrutura automaticamente; duplicatas abrem na última ocorrência com aviso no envio; JSON inválido e folha-antes-de-ramo abrem em modo diagnóstico bloqueando envio; colisões multi-arquivo alertam quem vence; valores não-string ficam somente-leitura `[não-string]`.
- [Escolha da base e múltiplos arquivos por idioma](tickets/016-base-e-multiplos-arquivos.md): pré-seleciona `en` com opção de troca ou base externa; visão unificada para N arquivos por `lang` (rastreando arquivo de origem e espelho/principal p/ novas chaves); carrega condicionais `system`/`module` por padrão; alerta caixa não-BCP-47; ignora `path` HTTP.
- [Chaves faltantes e órfãs entre base e destinos](tickets/006-chaves-faltantes-orfas.md): `missing` só cria ao traduzir e insere na posição relativa da base; órfãs exibidas com badge `ÓRFÃ` e removíveis só por ação confirmada; reconhece/sugere plurais CLDR (`.many` em pt-BR/es/fr); `""` alerta `[vazia]` em Pendentes e igual-à-base usa `= base` até `reviewed`; conflito estrutural fica somente-leitura sem escrita automática.
- [Estratégia do writer com preservação de estilo](tickets/007-writer-preservacao-estilo.md): scanner JSON próprio estrito em Python puro + spans exatos e `json.loads` pré-gravação; caminho lógico expandido + span (última ocorrência em duplicatas); inserção segue estilo do destino (indent/EOL do destino); `ensure_ascii=True` só se o arquivo todo for escapado; remoção de órfãs poda pais vazios.
- [Esquema e portabilidade do arquivo .i18nproj](tickets/018-esquema-i18nproj.md): `schema_version=1` gravado com `os.replace`; `package_root` relativo+absoluto (relocalizável), lang files relativos ao pacote; salvamento manual (`Ctrl+S`) + rascunho de crash recovery em `%APPDATA%`; migração automática p/ versões antigas (c/ backup) e recusa p/ futuras; esquema inclui `project_id`, `package`, `snapshots`, `drafts`, `review_state`, `ignored_warnings`, `custom_enrichers` e `project_glossary`.
- [Pipeline de validação pré-produção e escrita atômica](tickets/019-pipeline-pre-producao.md): diálogo seleciona arquivos por checkbox → SHA-256 → bloqueios ([006](tickets/006-chaves-faltantes-orfas.md)/[010](tickets/010-politica-placeholders.md)/[015](tickets/015-arquivos-malformados.md)) → confirmação única de avisos → validação em memória (`json.loads` + simulação `expandObject` + conferência do diff) → backup agrupado → `.tmp` + `os.replace` (5 retries 100–500 ms p/ OneDrive); falha parcial interrompe e oferece rollback do lote.
- [Interações finas da UI e escala em pacotes grandes](tickets/020-interacoes-ui-escala.md): teto de ~5 linhas (~110 px) na tabela + Editor Expandido (`Shift+F2`) lado a lado; menu de contexto em 4 seções fixas; busca debounce 150 ms, lint/ortografia em `QThreadPool` priorizando visíveis e altura cacheada; `QUndoStack` (`Ctrl+Z`/`Ctrl+Y`) p/ ações na tabela.
- [Dados do app, build PyInstaller e distribuição Windows](tickets/021-dados-build-distribuicao.md): `%APPDATA%\i18n-reviewer\` (`settings.json`, `glossary.json`, `enchant\hunspell\`, `backups\`, `recovery\`); CPython 3.14.x + `PySide6-Essentials 6.12.0` + `pyenchant 3.3.0` + `PyInstaller 6.22.3`; `.spec` enxuto (exclui Qt ocioso e DLLs MSYS2/nuspell, `module_collection_mode='py'`, pasta `licenses/`); contorno 8.3/ASCII + sentinela; entrega `.zip` portátil (+ Inno Setup opcional).
- [Estratégia de testes e critérios de aceitação](tickets/022-estrategia-testes.md): `pytest` + `pytest-qt` com fixtures autocontidas em `tests/fixtures/` (+ integração opcional em cópia do `hearthbound`); cobertura de round-trip byte a byte, merge 3-vias, pipeline pré-produção + `PermissionError`, serviços + contorno não-ASCII, UI/Undo + benchmark 10k chaves; `--self-test` pós-build no `.exe` congelado.

## Not yet specified

*(Toda a névoa foi graduada em tickets na fronteira; não há mais itens não especificados pendentes.)*

## Out of scope

<!-- trabalho conscientemente excluído deste esforço; nunca gradua -->

- **Traduções de compêndio do Babele (`lang/*/compendium/*.json`):** arquivos JSON não declarados no array `languages[]` do manifest ficam fora do escopo do i18n Reviewer ([ticket 016](tickets/016-base-e-multiplos-arquivos.md)).
- **Arquivos remotos (`path` HTTP/HTTPS em `languages[]`):** listados apenas como não-editáveis/ignorados na criação do projeto ([ticket 016](tickets/016-base-e-multiplos-arquivos.md)).

