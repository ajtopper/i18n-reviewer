# 01: Redimensionamento fluido da janela e dimensionamento sob demanda no viewport

**What to build:** Substituir o recálculo síncrono global de alturas da tabela (`ResizeToContents`) pelo modo `Interactive` com altura padrão igual à altura mínima configurada para a densidade e zoom atuais, sincronizando a altura (`setRowHeight`) apenas das linhas visíveis no viewport mais uma pequena margem de overscan — com debounce durante o arrasto da janela ou de colunas horizontais, atualização imediata ao carregar pacote, rolar verticalmente, filtrar, alternar `Compact` ou ajustar zoom, e ajuste pontual na linha ao editar uma célula. Além disso, evitar que o handler de redimensionamento da janela reaplique limites mínimos/máximos nos painéis laterais (`sidebar` e `inspector`) quando os valores em pixels não mudarem.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Redimensionar a janela principal continuamente em uma sessão com 3.000+ chaves com textos longos/multilinha mantém a UI responsiva (10 eventos consecutivos de resize concluem dentro do orçamento definido nos testes, sem travamento).
- [ ] Carregar uma sessão grande exibe a tabela rapidamente sem recalcular alturas de linhas fora da tela.
- [ ] Linhas visíveis no viewport com texto quebrado ou multilinha adaptam sua altura entre o mínimo da densidade/zoom e o teto máximo (~110 px escalado por zoom), inclusive após rolagem vertical, troca de filtro, alternância de densidade `Compact`, zoom (`Ctrl++`/`Ctrl+-`/`Ctrl+0`) e edição pontual de célula.
- [ ] O redimensionamento da janela não dispara invalidações extras de layout nos painéis laterais quando suas larguras mínimas/máximas calculadas permanecem inalteradas.
- [ ] Testes automatizados ponta a ponta no seam `MainWindow` + `QtBot` validam o orçamento de tempo de resize e o comportamento correto das alturas visíveis, mantendo toda a suíte existente verde.
