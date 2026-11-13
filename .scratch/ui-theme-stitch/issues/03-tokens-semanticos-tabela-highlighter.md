# 03: Tokens semânticos da `QTableView`, `StatusCellDelegate` e `TokenHighlighter` (Claro/Escuro)

**What to build:** Substituir as cores fixas (apenas modo claro) das células de status da tabela (`OK`, `EDITED`, `STALE`, `EMPTY`, `MISSING`, `ORPHAN`, `CONFLICT`, etc.) e do destaque de tokens/placeholders no editor por tokens semânticos alinhados à paleta Stitch que se adaptam automaticamente ao tema ativo (Claro ou Escuro), com barra de contexto/densidade sobre a tabela e repintura imediata ao trocar de tema.

**Blocked by:** 02: Motor de tema centralizado com paleta Stitch (Claro/Escuro) e `QStyleHints.colorScheme()`

**Status:** done

- [x] Todos os estados de célula (`OK`, `EDITED`, `STALE`, `EMPTY`, `MISSING`, `ORPHAN`, `CONFLICT`, `REMOVE`) mantêm contraste legível de texto e badge nos modos Claro e Escuro.
- [x] O destaque de tokens e placeholders no editor inline e no editor expandido adapta suas cores ao tema ativo sem perder legibilidade.
- [x] Trocar de tema (manual ou via sistema) repinta imediatamente as células visíveis e atualiza o editor aberto sem artefatos visuais.
- [x] Testes automatizados validam o mapeamento de tokens semânticos para Claro e Escuro em todos os estados de célula.

