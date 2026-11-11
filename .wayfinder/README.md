# Tracker local (Wayfinder)

Tracker em markdown dentro do repositório. Substitui um issue tracker remoto.

## Estrutura

```text
.wayfinder/
├── map.md            # O mapa (label wayfinder:map) — índice, não armazém
├── tickets/          # Um arquivo por ticket (issue filha do mapa)
│   └── NNN-slug.md
└── research/         # Achados dos tickets de research (assets linkados pelos tickets)
```

## Frontmatter do ticket

```yaml
---
id: 3                       # identidade do ticket (nunca reutilizar)
title: Nome legível         # o NOME; sempre referir por ele, não pelo id
type: research              # research | prototype | grilling | task
mode: AFK                   # AFK | HITL
status: open                # open | closed | out-of-scope
assignee:                   # vazio = não reivindicado; preencher ANTES de trabalhar
blocked_by: [1, 4]          # ids dos tickets que bloqueiam este
parent: map
---
```

## Operações de Wayfinding

- **Reivindicar:** preencher `assignee` e salvar antes de qualquer trabalho.
- **Bloqueado:** um ticket está desbloqueado quando todos os ids em `blocked_by` estão `closed`.
- **Fronteira:** tickets `status: open`, desbloqueados e com `assignee` vazio. Ordem = `id` crescente.
- **Resolver:** acrescentar uma seção `## Resolução` ao final do ticket, mudar `status: closed`,
  e adicionar uma linha em *Decisions so far* no `map.md` (nome do ticket com link + gist de uma linha).
- **Fora de escopo:** `status: out-of-scope` + uma linha na seção *Out of scope* do mapa.
- **Novo ticket:** próximo `id` livre; criar primeiro, ligar `blocked_by` depois.

