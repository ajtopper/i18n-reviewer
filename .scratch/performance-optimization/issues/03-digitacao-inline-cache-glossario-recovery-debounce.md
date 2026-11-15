# 03: Digitação inline fluida, cache de glossário na UI e auto-recovery sem travamento

**What to build:** Eliminar microtravamentos durante a digitação e revisão contínua de células na janela principal: aplicar debounce (~120 ms) na revalidação síncrona disparada por digitação no editor inline com repintura restrita apenas à célula em edição e reconstrução seletiva dos botões dinâmicos do inspetor somente quando as ações mudarem; cachear a lista mesclada de glossário na janela principal (invalidando apenas em alterações de glossário global, projeto ou sessão); consolidar os contadores da barra de status em uma única passagem pelas linhas; e aplicar debounce (~500 ms) na escrita do rascunho de auto-recovery após edições contínuas, com flush síncrono garantido antes de salvar projeto, publicar para produção, sincronizar com o disco, abrir/restaurar backups, atualizar glossário/enrichers/exceções e fechar a janela.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Digitar rapidamente em uma célula inline não dispara validação completa, mesclagem de glossário nem recriação de botões do inspetor a cada tecla, mantendo os diagnósticos e botões atualizados após a breve pausa de debounce.
- [ ] Alterações no glossário global ou do projeto invalidam imediatamente o cache de glossário na janela principal para que o editor inline, menu de contexto e inspetor reflitam os termos atualizados.
- [ ] Os contadores exibidos na barra de status permanecem idênticos após carregamento, edição, revisão em lote e finalização da validação.
- [ ] Edições consecutivas não gravam o JSON de auto-recovery sincronamente a cada célula, mas qualquer rascunho pendente é gravado imediatamente antes de salvar, publicar, sincronizar, restaurar backup ou fechar a aplicação.
- [ ] Testes automatizados no seam `MainWindow` + `QtBot` validam o debounce inline, a atualização correta do inspetor e o flush garantido do recovery draft.
