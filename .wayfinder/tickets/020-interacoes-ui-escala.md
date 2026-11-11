---
id: 20
title: Interações finas da UI e escala em pacotes grandes
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [10, 11, 12, 14]
parent: map
---

## Question

Quais detalhes finos de UX e desempenho garantem fluidez tanto no `hearthbound` (1.3k chaves) quanto em sistemas grandes (`dnd5e` 4k+ chaves, `pf2e` 5.8k+, `3ds-atlas` 12k+)?

- **Strings longas/HTML na tabela:** teto de altura da linha na tabela (ex.: máx. 5 linhas / ~110 px) + modal/editor expandido no Inspector ou janela dedicada para textos longos/HTML?
- **Menu de contexto combinado:** ordem e organização quando a mesma célula tem erro ortográfico + inconsistência de glossário + erro de placeholder + ação de revisão.
- **Escala (5k–12k chaves):** debounce na busca (ex.: 150 ms), indexação em memória, cálculo de lint/ortografia incremental/assíncrono (apenas linhas modificadas + lote em background) e atualização de `ResizeToContents` sem travar a UI.
- **Desfazer/Refazer (`Ctrl+Z` / `Ctrl+Y`):** histórico de ações na sessão (edição, marcar revisado, aplicar sugestão).

## Resolução

- **Strings longas e HTML:** altura de linha na tabela limitada a um teto (~5 linhas / ~110 px com corte visual); edição inline (`F2`) para textos curtos/médios + **Editor Expandido** (`Shift+F2` ou botão no Inspector) exibindo Base × Tradução lado a lado com destaque de placeholders/HTML para textos extensos.
- **Menu de contexto combinado (ordem fixa por seção):**
  1. Revisão e célula (*Marcar como Revisado*, *Reverter para produção*, *Copiar da base*, *Ignorar alerta...*, *Abrir editor expandido*)
  2. Placeholders/tokens faltantes (*Inserir `{token}`*)
  3. Glossário (*Aplicar tradução preferida*, *Adicionar ao glossário...*)
  4. Ortografia (*Substituir palavra...*, *Adicionar ao dicionário*)
- **Escala para pacotes grandes (5k–12k+ chaves):**
  - Busca com **debounce de 150 ms** sobre texto pré-normalizado em memória.
  - Validação de placeholders/glossário/ortografia inicial em **worker assíncrono (`QThreadPool`)** priorizando linhas visíveis, com reavaliação síncrona imediata apenas na célula editada.
  - Cálculo de altura de linha **cacheado por largura de coluna** (evitando recálculo síncrono de 12k linhas ao redimensionar).
- **Histórico na sessão (`Ctrl+Z` / `Ctrl+Y`):** `QUndoStack` cobrindo edição de célula, aplicação de sugestão de glossário/ortografia, mudança de `review_status`, reversão de célula e marcação/desmarcação de remoção de órfãs.


