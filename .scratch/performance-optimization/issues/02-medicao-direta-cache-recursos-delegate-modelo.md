# 02: Medição direta de texto e cache de recursos gráficos na renderização da tabela

**What to build:** Otimizar o cálculo de tamanho e a pintura de células no delegate e no modelo da tabela: substituir a delegação genérica a `super().sizeHint()` no delegate por medição direta de quebra de linha via `QFontMetrics.boundingRect` (mantendo o fast-path para strings curtas de linha única e os limites de altura mínima/máxima), alterar o cache de altura do delegate para indexação por `(row, col)` com uma entrada por célula (evitando acúmulo e limpeza em massa durante redimensionamentos), cachear fonte, métricas da faixa de badge e instâncias de `QColor` por tema/zoom no delegate, e cachear instâncias de `QFont` (chave monoespaçada, itálico e tachado) e cor mutada no modelo da tabela evitando consultas e comparações redundantes em `data()`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] O cálculo de `sizeHint` para células multilinha ou com quebra de linha respeita exatamente o padding, a altura da faixa de badge e os limites `min_row_height()` e `max_row_height()` em qualquer nível de zoom e modo `Compact`.
- [x] Variar continuamente a largura de uma coluna não gera crescimento descontrolado do cache de alturas do delegate nem limpezas em cascata durante o arrasto.
- [x] Pintura e consulta de `FontRole`/`ForegroundRole` reutilizam recursos Qt cacheados sem instanciar novas fontes, métricas ou cores por célula pintada/lida.
- [x] Testes automatizados no seam `MainWindow` + `QtBot` verificam preservação visual de fontes, cores, badges e teto de altura nas células, sem regressões na suíte de tema e zoom.
