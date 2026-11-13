# 02: Feedback contextual na UI e avanço inteligente pós-lote

**What to build:** Exibir na UI (Inspector e barra de status) quantas células elegíveis estão selecionadas para revisão em lote, garantir que `Mark Reviewed + Next (Ctrl+Enter)` avance para a próxima célula pendente após o fim do bloco selecionado, e registrar a melhoria no changelog e nos testes de UI.

**Blocked by:** 01: Seleção múltipla de células de idioma + Undo/Redo em lote para `Mark Reviewed`

**Status:** ready-for-agent

- [ ] Quando 2 ou mais células elegíveis estão selecionadas, o botão de ação no Inspector indica a revisão em lote (ex.: quantidade de células elegíveis) e a barra de status confirma quantas células foram marcadas após a ação.
- [ ] Ao executar `Mark Reviewed + Next` sobre uma seleção em lote, o cursor avança para a próxima célula pendente após a última célula do intervalo selecionado.
- [ ] Changelog atualizado e suíte de testes + checagem de tipos passando.

