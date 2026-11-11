---
id: 3
title: Sintaxes embutidas em strings de localização do Foundry
type: research
mode: AFK
status: closed
assignee: research-agent
blocked_by: []
parent: map
---

## Question

Quais sintaxes aparecem dentro dos valores de localização do Foundry e quebram (ou mudam de significado) se forem alteradas pela tradução?

- Placeholders de `game.i18n.format` (`{name}`), pluralização/`localize` aninhado, `{{handlebars}}` em templates.
- Enrichers de texto: `@UUID[...]{label}`, `@Compendium`, `@Embed`, `[[/r 1d20]]`, `[[/check]]`, `&Reference[...]`, e enrichers específicos de sistemas populares (dnd5e, pf2e: `@Check[...]`, `@Damage[...]`).
- HTML embutido (`<strong>`, `<p>`), entidades, `%s`-style, quebras de linha.
- Para cada sintaxe: regex/gramática para extração, o que pode ser traduzido dentro dela (ex.: o `{label}` do `@UUID`) e o que deve ser idêntico à base.

Achados em `.wayfinder/research/003-sintaxes-embutidas-foundry.md`.

## Resolução

- Na v14 (build 370), `format` é alias de `localize(stringId, data)`. A substituição é `/{[^}]+}/g` → `data[nome]`, e um nome ausente vira o texto literal `"undefined"`. Sem `data`, nada é substituído. O padrão é formatar primeiro e enriquecer depois, então o `{rótulo}` de enrichers e chaves literais em prosa colidem com placeholders (caso real: crucible `ACTION.DelayHint`).
- As regex exatas do core (`@UUID`/legados, `@Embed`, `[[...]]` inline rolls, URLs) e de dnd5e (`[[/check…]]`, `[[lookup]]`, `&Reference`) e pf2e (`@Check/@Damage/@Template/@Localize`, `[[/act]]`) foram extraídas do código instalado. Elas rodam só sobre nós de texto, e `CONFIG.TextEditor.enrichers` é aberto e varia por sistema.
- Regra geral: a parte técnica fica idêntica à base (tipo, UUID/alvo, config/params, fórmula, comando, chave do `@Localize`, nomes de tags e atributos técnicos). São traduzíveis o `{rótulo}`, o `#flavor` de rolagens, o `name:` do `@Check` pf2e, o `caption="..."` do `@Embed` e o texto entre tags. Valores "parecidos com texto" como `&Reference[Perception]` não podem ser traduzidos.
- Pluralização é por sufixo de chave (`Intl.PluralRules` do idioma do jogo). pt-BR/es/fr têm a categoria `many`, que não existe em en, e uma categoria ausente faz a UI mostrar a chave crua. Não existe `%s` nem `localize` aninhado no core.
- HTML/entidades só renderizam se o chamador usar `{{{ }}}`/`innerHTML`/`enrichHTML`. `{{localize}}` escapa. Isso não é visível no arquivo de idioma.
- Caso hearthbound: só placeholders `{identificador}` (186 por arquivo, 51 nomes), consistentes em en/pt-BR/es/eo. O módulo usa um wrapper sobre `game.i18n.format` (151 chamadas) e tem 61 chaves dinâmicas.
- Achados completos: [003-sintaxes-embutidas-foundry.md](../research/003-sintaxes-embutidas-foundry.md)
