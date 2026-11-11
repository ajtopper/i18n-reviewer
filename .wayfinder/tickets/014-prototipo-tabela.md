---
id: 14
title: Protótipo da tabela multilíngue de revisão
type: prototype
mode: HITL
status: closed
assignee: coordinator
blocked_by: [8]
parent: map
---

## Question

Como a tela principal deve parecer e se comportar para revisar centenas/milhares de chaves em vários idiomas ao mesmo tempo?

Protótipo descartável em PySide6 (dados falsos) para reagir a:

- Layout de N colunas de destino com strings longas/multilinha: largura, quebra de linha, altura de linha.
- Badges de status (verde/amarelo/borda de alerta) conforme a máquina de estados do ciclo de status.
- Painel lateral vs. rodapé para contagem de caracteres, placeholders e sugestões.
- Fluxo de revisão por teclado: navegar, editar (`F2`), marcar revisado, pular para a próxima pendente.

## Resolução

- **Protótipo validado:** [proto_014.py](file:///C:/Users/ajtop/.gemini/antigravity/brain/7362d1f6-13de-43a8-a414-89bc2c833cc8/scratch/proto_014.py) e captura [proto_014_preview.png](file:///C:/Users/ajtop/.gemini/antigravity/brain/7362d1f6-13de-43a8-a414-89bc2c833cc8/proto_014_preview.png).
- **Layout da tabela (`QTableView` + `QAbstractTableModel` + `QStyledItemDelegate`):**
  - Coluna 0 `KEY_PATH` (somente leitura, monoespaçada), Coluna 1 idioma base (somente leitura, quebra de linha), Colunas 2+ idiomas de destino (editáveis com duplo clique / `F2` via `QPlainTextEdit` multilinha).
  - Toolbar inclui checkboxes de visibilidade por idioma de destino (e permite focar em 1 idioma por vez quando houver 3+ destinos) + busca rápida (`Ctrl+F`) e filtros.
  - Altura automática (`ResizeToContents`) com quebra de linha; para strings gigantes (HTML/lore longos), aplicar teto visual na tabela e edição confortável no editor/painel.
- **Renderização de status e alertas no delegate:**
  - Margem superior reservada (~18 px) para o badge no canto superior direito nunca sobrepor a primeira linha de texto.
  - Cores de fundo + badges alinhados ao [ticket 008](008-ciclo-de-vida-status.md): verde suave (`OK` = `reviewed` sem `dirty`), amarelo suave (`EDITADO` = `dirty` e `unreviewed`; `EDITADO · OK` quando `dirty` e `reviewed`), lilás (`STALE`), cinza itálico (`MISSING`).
  - Faixa lateral esquerda de 4 px indica severidade de validação: **vermelho** = erro crítico bloqueante ([ticket 010](010-politica-placeholders.md)), **âmbar** = aviso (glossário, ortografia ou HTML).
- **Painel lateral (Inspector) + Rodapé:**
  - Painel fixo à direita (retrátil) exibe chave/idioma, estado (`review_status` + `dirty`), contagem de caracteres Base vs. Destino, comparativo *Antes × Agora* quando `stale`, tokens protegidos clicáveis/faltantes, avisos de glossário e sugestões ortográficas.
  - Barra de status (rodapé) exibe o resumo numérico do projeto (`revisadas/total`, `editadas`, `erros críticos`, `avisos`).
- **Fluxo por teclado:** `F2` (editar), `Ctrl+Space` (popup de glossário no cursor), `Ctrl+Enter` (marcar revisado e avançar para a próxima pendente), `Ctrl+Down` (pular para próxima pendente), `Ctrl+F` (busca).


