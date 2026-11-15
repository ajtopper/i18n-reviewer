# 04: Substituir Tudo em lote (`Ctrl+H`) com prévia e Undo/Redo em macro única

**What to build:** Estender o fluxo de Localizar e Substituir (`Ctrl+H`) para suportar substituição em lote (*Replace All*) com prévia clara de impacto antes da aplicação. A interface deve mostrar quantas ocorrências e células editáveis serão alteradas — e quantas ocorrências foram ignoradas por estarem dentro de spans técnicos protegidos ou em células somente leitura. Ao confirmar *Replace All*, todas as alterações devem ser aplicadas em uma única macro desfazível/refazível (`Ctrl+Z` / `Ctrl+Y`), rebaixando células revisadas alteradas para `unreviewed`, atualizando o rascunho de recuperação e revalidando todas as linhas modificadas. Registra a funcionalidade na seção `v0.2.5` do changelog.

**Blocked by:** 03: Localizar e Substituir interativo (`Ctrl+H`) com proteção de spans técnicos

**Status:** ready-for-agent

- [ ] A interface exibe contagem prévia em tempo real de células/ocorrências elegíveis e indica quantas ocorrências foram preservadas pela proteção de tokens ou células não editáveis.
- [ ] *Replace All* aplica todas as substituições elegíveis em uma única macro da pilha de Undo/Redo, permitindo desfazer (`Ctrl+Z`) e refazer (`Ctrl+Y`) todo o lote de uma só vez.
- [ ] Células alteradas em lote têm `dirty` atualizado, rebaixam `review_status` para `unreviewed`, acionam revalidação completa e gravam o rascunho de recuperação sem corromper tokens técnicos ou células somente leitura.
- [ ] Changelog atualizado para a versão `v0.2.5` e testes automatizados cobrem contagem prévia, lote com proteção de tokens, rebaixamento de status e Undo/Redo único.
