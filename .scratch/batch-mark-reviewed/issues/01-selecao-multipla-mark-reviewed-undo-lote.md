# 01: Seleção múltipla de células de idioma + Undo/Redo em lote para `Mark Reviewed`

**What to build:** Garantir seleção múltipla por células na tabela (`Shift+Click`, `Shift+Setas`, `Ctrl+Click`) e fazer `Mark Reviewed` (via `Ctrl+Enter`, botão do Inspector ou menu de contexto) marcar como revisadas todas as células de idioma elegíveis dentro da seleção, ignorando com segurança colunas `Key`/`Base` e células não elegíveis, agrupando toda a operação em uma única macro desfazível (`Ctrl+Z` / `Ctrl+Y`).

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Selecionar múltiplas células com `Shift+Click`, `Shift+Setas` ou `Ctrl+Click` e acionar `Mark Reviewed` marca todas as células de idioma elegíveis selecionadas.
- [x] Células das colunas `Key` e `Base` ou células já revisadas/não elegíveis presentes na seleção são ignoradas sem erro.
- [x] `Ctrl+Z` desfaz a revisão de todo o lote em um único passo, e `Ctrl+Y` refaz todo o lote.
- [x] Testes automatizados cobrem seleção múltipla, filtragem de células elegíveis e Undo/Redo em lote.

