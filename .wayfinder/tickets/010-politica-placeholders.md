---
id: 10
title: Política de placeholders e conteúdo protegido
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [3]
parent: map
---

## Question

Com base nas sintaxes levantadas, quais divergências entre base e tradução a ferramenta verifica, e com que severidade?

- Quais sintaxes são checadas (placeholders `{x}`, enrichers, HTML, inline rolls) e o que conta como divergência (faltando, sobrando, alterado, ordem trocada).
- Severidade: **bloqueia** Enviar para Produção, exige confirmação, ou só alerta na célula?
- Proteção na edição: placeholders destacados/não editáveis no editor da célula, ou só validação posterior?
- Permitir exceção por chave ("ignorar este alerta") e onde ela é persistida.
- **Registro de enrichers:** lista embutida (core + dnd5e + pf2e) com heurística genérica `@Nome[...]`/`&Nome[...]`/`[[/nome ...]]`, ou regras configuráveis por projeto no `.i18nproj` (o conjunto é aberto; tormenta20 substitui a lista inteira)?
- **Defeitos na própria base:** colisão placeholder × rótulo de enricher `{label}` (vira "undefined" — caso real crucible `ACTION.DelayHint`). Sinalizar mesmo quando base e tradução coincidem, ou só comparar contra a base?

> Insumo: [research 003](../research/003-sintaxes-embutidas-foundry.md).

## Resolução

- **Pipeline de extração (ordem fixa):** `{{handlebars}}` → enrichers conhecidos (lista embutida: core v14 + `dnd5e` + `pf2e`) + regras extras do projeto + heurística genérica (`@Nome[...]`, `&Nome[...]`, `[[/nome ...]]`) → URLs (`https?://...`) → tags HTML/XML e entidades → placeholders simples `{nome}` no texto restante. Partes traduzíveis de enrichers (`{rótulo}`, `#flavor` em rolagens, `name:` do `@Check` no pf2e, `caption="..."` em `@Embed`) são liberadas para tradução.
- **Regras e severidade em 2 níveis:**
  - **Erro crítico** *(bloqueia Enviar para Produção para o arquivo, salvo exceção explícita)*:
    - Conjunto de nomes únicos de placeholders `{nome}` divergente da base (faltando, sobrando ou renomeado).
    - `{{handlebars}}` alterado, faltando ou sobrando.
    - Parte técnica de enricher (tipo, alvo/UUID, fórmula, config/params) alterada ou ausente quando presente na base.
  - **Aviso** *(alerta visual na célula + exige confirmação ao Enviar para Produção)*:
    - Contagem diferente de repetições do mesmo `{nome}` quando o conjunto de nomes únicos bate (a **ordem** é totalmente livre e nunca alerta).
    - Tags HTML/XML ou atributos técnicos divergentes da base (ou tag desbalanceada).
    - URL alterada ou omitida.
  - **Aviso informativo na base** *(nunca bloqueia)*: defeitos na própria string de referência, como colisão `{rótulo}` de enricher + `{placeholder}` ou chaves soltas em prosa.
- **Proteção na edição:** editor de texto normal com destaque visual (cor) nos spans protegidos, validação em tempo real na célula e no painel lateral, e inserção rápida de tokens faltantes via clique no painel/atalho (sem travar digitação em blocos rígidos).
- **Exceções ("Ignorar este alerta"):** permitidas por `(chave, idioma, regra)` com justificativa opcional, persistidas no `.i18nproj` (incluindo referência ao valor para que o alerta volte se a string mudar).
- **Extensibilidade de enrichers:** lista embutida (core + `dnd5e` + `pf2e`) + heurística genérica + campo opcional de regras/regex extras no `.i18nproj`.


