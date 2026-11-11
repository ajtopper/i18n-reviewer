---
id: 11
title: Modelo do glossário
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: []
parent: map
---

## Question

Como o glossário é modelado e aplicado?

- Escopo: global por usuário, por projeto, ou ambos com precedência (projeto sobrescreve global)?
- Direcionalidade: entradas por par de idiomas (`en→pt-BR`, `en→es`), um termo com várias traduções aceitas, termos "não traduzir" (nomes próprios, marcas).
- Matching: case-sensitive?, limites de palavra, plural/flexão ("Spell Slots" casa com "Spell Slot"? "Espaços de Magia" satisfaz "Espaço de Magia"?), termos sobrepostos (o mais longo vence?).
- Formato do `glossary.json` e formatos de importação/exportação (CSV, TBX?).
- Sugestão via `Ctrl+Space`: o que exatamente é inserido e onde.
- O linter ignora spans técnicos (placeholders, partes técnicas de enrichers como `&Reference[Perception]`) e só checa texto/rótulos?

## Resolução

- **Escopo em 2 níveis:** glossário **Global** do usuário (`glossary.json` nos dados do app) + glossário **Por Projeto** (dentro do `.i18nproj`); entradas do projeto **sobrescrevem** entradas do global com o mesmo termo-fonte.
- **Modelo da entrada:**
  - `term` (+ `source_variants` opcionais para plurais/flexões na base), `case_sensitive` (padrão `false`), `do_not_translate` (padrão `false`, exige manter o termo original intacto na tradução), `notes` opcional.
  - `translations: {lang: [preferida, ...aceitas]}` — direcionado por idioma de destino; a 1ª entrada é a preferida (sugerida no `Ctrl+Space`) e todas (incluindo flexões explícitas como `"Espaço de Magia"` / `"Espaços de Magia"`) satisfazem o linter.
- **Regras de matching e mascaramento:**
  - Reutiliza o extrator do [ticket 010](010-politica-placeholders.md) para **ignorar spans técnicos** (`{x}`, `{{hbs}}`, partes técnicas de enrichers como `&Reference[Perception]`, URLs, tags HTML/XML), checando apenas texto natural e rótulos traduzíveis.
  - Limite de palavra (`\b`) com **termo mais longo vencendo sobreposições** (`"Spell Slot"` vence `"Spell"`).
  - Não dispara falso alerta em células `missing` ou vazias.
- **Severidade e exceções:** inconsistência de glossário é sempre **aviso visual** (alimenta o filtro *Inconsistências de Glossário*, nunca bloqueia Enviar para Produção) e aceita *"Ignorar este alerta"* por `(chave, idioma, termo)` salvo no `.i18nproj`.
- **Ações rápidas na UI:** `Ctrl+Space` no editor abre popup com os termos do glossário detectados na string base e insere a tradução escolhida no cursor (ou preenche a célula se vazia); menu de contexto oferece *"Adicionar ao glossário"* pré-preenchido.
- **Formatos:** `glossary.json` nativo + importação/exportação em **CSV** (compatível com Excel/Planilhas).


