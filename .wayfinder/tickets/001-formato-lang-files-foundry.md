---
id: 1
title: Formato real dos arquivos de idioma e do manifest no Foundry
type: research
mode: AFK
status: closed
assignee: research-agent
blocked_by: []
parent: map
---

## Question

Como o Foundry VTT (v11–v13) declara e carrega arquivos de idioma, e que formatos esses arquivos assumem na prática?

- Campos da entrada `languages` em `module.json` / `system.json` (`lang`, `name`, `path`, outros?), paths relativos, múltiplos arquivos para o mesmo `lang`, idiomas fornecidos por um módulo **para outro** pacote (`flags`/`system` na entrada).
- Como o core mescla chaves: planas pontuadas (`"A.B.C"`) vs. aninhadas vs. mistas (ex.: `expandObject`/`mergeObject`); o que acontece com chaves duplicadas ou conflito plano×aninhado.
- Padrões observados em pacotes populares (dnd5e, pf2e, módulos de tradução pt-BR): estilo de chave, indentação, BOM, newline final, ordenação.
- Fallback para o idioma base quando falta uma chave no destino.

Achados em `.wayfinder/research/001-formato-lang-files-foundry.md`.



## Resolução

- **Manifest (v14):** cada entrada de `languages` aceita `lang` (validado por `Intl.getCanonicalLocales`, comparado por string exata), `name` (opcional, default = `lang`), `path` (relativo à raiz do pacote, precisa existir, não pode sair da pasta; URL HTTP é aceita), `system`/`module` (carga condicional, mecanismo nativo para traduzir outro pacote) e `flags` (ignorado). Vários arquivos por `lang` são suportados e comuns (pf2e: 4; fvtt-brasil pf2e: 3), mesclados na ordem do manifest.
- **Mescla:** cada arquivo passa por `expandObject` (plano, aninhado e misto são equivalentes; ordem do arquivo importa) e depois `mergeObject` na ordem core → sistema → módulos → world, último vence. Casos quebrados: folha seguida de ramo com o mesmo prefixo faz o Foundry descartar **o arquivo inteiro**; ramo/folha posterior apaga o anterior; duplicatas → vence a última (existem no mundo real: tormenta20 `T20.Immunity`).
- **Fallback:** sempre para o dicionário `en` completo (`_fallback`), depois a própria chave; não existe "idioma base do pacote" (tormenta20 declara `en` apontando para `pt-BR.json`).
- **Formato na prática:** sem BOM, sem `\uXXXX`, UTF-8 literal, indent 2 ou 4, LF ou CRLF, às vezes sem newline final; estilos plano (3ds-atlas, fvtt-brasil), aninhado (pf2e, hearthbound) e misto (dnd5e, core); base e alvo podem divergir de estilo (vision-t20). Vários arquivos populares **não são canônicos** para `json.dumps` (core e dnd5e: topo sem indentação, linhas em branco, objetos inline; crucible/daggerheart: espaçamento irregular) → edição por spans é necessária para preservar estilo. hearthbound (referência) é canônico (indent 2 + CRLF).
- Achados completos, com citações: [research/001-formato-lang-files-foundry.md](../research/001-formato-lang-files-foundry.md).
