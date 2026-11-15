---
title: "Otimização de Desempenho da UI, Redimensionamento e Validação"
labels: [ready-for-agent, spec]
status: open
---

# Especificação: Otimização de Desempenho da UI, Redimensionamento e Validação

## Problem Statement

Ao trabalhar com pacotes grandes no i18n Reviewer (milhares de chaves de localização e textos longos ou multilinha), o usuário percebe lentidão geral no aplicativo e travamentos severos ao redimensionar a janela principal:

1. **Travamento ao redimensionar a janela:** ao arrastar a borda ou canto da janela para aumentar ou diminuir seu tamanho, o computador fica lento e a interface demora segundos para responder. Isso ocorre porque a tabela recalcula sincronamente a altura de todas as linhas do modelo (inclusive milhares de linhas fora da área visível) a cada pixel de mudança na largura da janela, gerando dezenas de milhares de medições de layout e invalidando o cache de alturas a cada passo.
2. **Abertura de pacotes e trocas de zoom/densidade lentas:** ao carregar uma sessão grande, alternar densidade ou ajustar zoom, o recálculo global síncrono de todas as linhas congela a thread da UI por vários segundos.
3. **Lentidão e microtravamentos durante edição e digitação:** digitar em uma célula inline dispara revalidação completa, mesclagem de glossário, repintura total da viewport da tabela e destruição/recriação de botões do inspetor a cada tecla pressionada, enquanto gravações síncronas de auto-recovery em disco e loops redundantes na barra de status ocorrem a cada confirmação de edição.
4. **Contenção de CPU/GIL na validação em segundo plano:** o worker em background recompila expressões regulares de glossário por célula e reprocessa tokens protegidos e termos do idioma base repetidamente para cada idioma alvo da mesma linha, competindo pelo GIL do Python e pelo lock do corretor ortográfico com a thread principal da interface.

## Solution

Tornar a interface e o pipeline de validação fluidos mesmo em pacotes com milhares de chaves:

- Substituir o dimensionamento global síncrono de linhas por **sincronização sob demanda orientada ao viewport** com debounce durante arrasto de janela e redimensionamento de colunas, mantendo quebra automática de linha e altura adaptativa (entre o mínimo da densidade/zoom e o teto de ~5 linhas) para todas as linhas visíveis na tela.
- Eliminar alocações repetidas de objetos gráficos (`QFont`, `QFontMetrics`, `QColor`), cálculos redundantes de layout no delegate e invalidações desnecessárias de restrições dos painéis laterais durante eventos de resize.
- Introduzir debounce leve na avaliação ao vivo durante digitação inline e na persistência de rascunho de auto-recovery (com flush garantido em todas as operações críticas de salvamento, publicação, sincronização e fechamento).
- Pré-compilar matchers de glossário, cachear padrões de fronteira de termos e compartilhar os resultados já extraídos do idioma base e da célula alvo dentro do worker de validação, reduzindo drasticamente o uso de CPU e a contenção com a thread da UI.

## User Stories

1. As a translator/reviewer, I want the main window to resize smoothly and instantaneously when I drag its edges or corners, so that adjusting my workspace does not freeze the application or slow down my machine.
2. As a translator/reviewer, I want resizing individual language columns in the table header to remain responsive even with thousands of keys loaded, so that I can adjust column proportions comfortably.
3. As a translator/reviewer, I want visible multiline or long wrapped rows to automatically adapt their height within the configured minimum and maximum bounds, so that text remains readable without clipping.
4. As a translator/reviewer, I want scrolling vertically through a large package to dynamically adjust newly revealed rows without visible stutter, so that browsing thousands of keys feels fluid.
5. As a translator/reviewer, I want opening a large package or `.i18nproj` session to display the table immediately, so that I can start reviewing without waiting several seconds for off-screen row layout.
6. As a translator/reviewer, I want toggling Compact density to immediately update visible row heights and minimum row bounds proportionally, so that I can switch visual density effortlessly.
7. As a translator/reviewer, I want zooming in and out (`Ctrl++`, `Ctrl+-`, `Ctrl+0`) to rescale columns, fonts, badges, and visible row heights smoothly, so that zoom changes feel snappy.
8. As a translator/reviewer, I want filtering by status, file, or search query (`Ctrl+F`) to update visible row heights accurately after the filter narrows or expands the table, so that filtered views always render cleanly.
9. As a translator/reviewer, I want typing inside an inline table cell editor to feel instantaneous with zero keystroke lag, so that editing long Foundry strings does not drop or delay characters.
10. As a translator/reviewer, I want inline validation alerts and Inspector diagnostics to update shortly after I pause typing without flickering or unnecessarily recreating Inspector action buttons on every keystroke, so that live feedback remains helpful and non-intrusive.
11. As a translator/reviewer, I want committing a cell edit (`Enter` or focus change) or marking cells reviewed (`Ctrl+Enter`) to respond immediately without synchronous disk serialization stalls on every single action, so that rapid keyboard-driven review flows smoothly.
12. As a translator/reviewer, I want my unsaved edits to still be safely persisted to the recovery draft automatically after a short pause and flushed immediately before saving, publishing, syncing, restoring backups, or closing the app, so that optimization never puts draft recovery at risk.
13. As a translator/reviewer, I want background validation, glossary linting, and Hunspell spellchecking on large packages with sizable glossaries to finish quickly without starving UI responsiveness, so that I can navigate and edit cells while validation runs.
14. As a translator/reviewer, I want the Inspector and table badges to reflect completed background validation for visible rows promptly without triggering redundant full-viewport repaints for off-screen batches, so that UI painting stays minimal.
15. As a translator/reviewer, I want all existing cell status badges, severity stripes, word wrap, undo/redo macros, find/replace, and keyboard shortcuts to behave identically after the performance optimizations, so that my workflow requires no relearning.

## Implementation Decisions

- **Dimensionamento de linhas orientado ao viewport na tabela (`MainWindow`):**
  - Configurar o cabeçalho vertical da tabela em modo `Interactive` (em vez de `ResizeToContents`) com `defaultSectionSize` e `minimumSectionSize` alinhados à altura mínima da densidade/zoom atual.
  - Introduzir um sincronizador de alturas apenas para a faixa visível do viewport mais uma pequena margem de overscan, acionado com debounce (~40–60 ms) durante eventos de redimensionamento da janela ou de colunas, e imediatamente (ou no próximo tick do loop de eventos) após carregamento de sessão, rolagem vertical, troca de densidade, alteração de zoom, troca de filtro ou edição pontual de célula.
  - Ao atualizar linhas, chamar `setRowHeight` apenas quando a altura calculada divergir da altura atual da linha; para edições pontuais de uma célula, recalcular apenas a linha afetada quando visível no proxy.
  - Em `_update_responsive_panel_bounds`, memorizar a última tupla de limites mínimos/máximos calculados para sidebar e inspector e só aplicar alterações nos widgets quando os valores em pixels efetivamente mudarem.

- **Medição direta e cache de recursos no delegate e no modelo (`StatusCellDelegate`, `TranslationTableModel`):**
  - Substituir a delegação genérica a `super().sizeHint()` no `StatusCellDelegate` por medição direta de quebra de linha via `QFontMetrics.boundingRect` com largura disponível descontando paddings, mantendo o fast-path para strings curtas de linha única e respeitando o intervalo `[min_row_height, max_row_height]`.
  - Alterar o cache de alturas do delegate para indexação por `(row, col)` armazenando `(width, zoom, compact, text, height)` (1 entrada por célula medida), evitando acúmulo de entradas descartáveis para larguras intermediárias durante arrasto de janela.
  - Pré-calcular e cachear no delegate a fonte/métricas da faixa de badge e um cache de `QColor` por código hexadecimal (invalidado em mudança de zoom/tema), evitando instanciar `QFont`, `QFontMetrics` e `QColor` em cada chamada de `sizeHint` e `paint`.
  - No `TranslationTableModel`, cachear instâncias de `QFont` (chave monoespaçada, itálico, tachado) e `QColor` mutado por nível de zoom, evitando chamadas duplicadas a `get_cell` e comparações redundantes de `Enum` no método `data`.

- **Pipeline de glossário, validação e ortografia (`validator`, `glossary`, `SpellService`, `ValidationRunnable`):**
  - Aplicar cache LRU (`@lru_cache`) em `term_boundary_pattern` para evitar recompilação contínua de expressões regulares descartáveis.
  - Introduzir uma estrutura de glossário compilado (`CompiledGlossary`) que pré-compila padrões por idioma e aplica pré-filtragem rápida por substring antes de executar expressões regulares, mantendo compatibilidade retroativa com as assinaturas públicas existentes de detecção, mascaramento e lint de glossário.
  - Permitir que a validação de tradução e o corretor ortográfico aceitem tokens protegidos, máscaras técnicas e conjuntos de palavras do idioma base pré-computados por linha/célula, eliminando recomputações múltiplas do mesmo texto dentro de `ValidationRunnable`.
  - No `SpellService`, validar disponibilidade do dicionário antes de mascarar texto e agrupar consultas de `_word_cache` / dicionário por célula sob uma única aquisição de lock em vez de adquirir o `RLock` por palavra individual.
  - Cachear o resultado de `merged_glossary()` e seu `CompiledGlossary` em `MainWindow`, invalidando apenas quando o glossário global, a sessão ativa ou o glossário do projeto mudarem.

- **Edição ao vivo, auto-recovery e barra de status (`MainWindow`):**
  - Adicionar debounce (~120 ms) no tratamento de texto digitado ao vivo (`_on_inline_text_changed`) para revalidação e atualização de diagnósticos no inspetor; repintar apenas o índice da célula em edição em vez de toda a viewport, e só reconstruir os botões dinâmicos do inspetor quando o conjunto de ações exibidas realmente mudar.
  - Adicionar debounce (~500 ms) na escrita do rascunho de recuperação (`write_recovery_draft`) acionada por edições contínuas, garantindo flush síncrono imediato antes de salvar projeto, publicar para produção, sincronizar com o disco, abrir/restaurar backups, atualizar glossário/enrichers/exceções e fechar a janela.
  - Consolidar o cálculo de contadores da barra de status em um único loop sobre as linhas da sessão.
  - Nos lotes emitidos pelo worker de validação em background, só disparar repintura da viewport se alguma linha do lote estiver visível no viewport atual (ou ao concluir o processamento).

## Testing Decisions

- **Princípio dos testes:** testar apenas comportamento observável externamente através dos seams de alto nível (interface `MainWindow` via `QtBot`, APIs públicas de `glossary`/`SpellService` e execução do `ValidationRunnable`), nunca acoplando asserções a caches internos, nomes de timers privados ou contadores internos de chamadas.
- **Módulos testados e seams:**
  1. **Seam `MainWindow` + `QtBot`:**
     - Carregar sessões com 3.000+ chaves contendo textos longos/multilinha e executar múltiplos `resize()` consecutivos: verificar que o tempo total fica abaixo de um orçamento de regressão rígido e que todas as linhas visíveis com texto multilinha recebem altura maior que `min_row_height()` e limitada a `max_row_height()`.
     - Verificar fluxo completo de alternância de densidade (`Compact`), zoom (`ThemeManager`), filtro por texto/status, edição inline com debounce atualizando o inspetor, e persistência garantida do recovery draft após flush/salvamento/fechamento.
  2. **Seam `ValidationRunnable` / `glossary` / `SpellService`:**
     - Verificar que os diagnósticos produzidos com `CompiledGlossary` e pré-computação por linha/célula são idênticos aos produzidos pelas chamadas diretas padrão (`detect_base_glossary_matches`, `mask_glossary_phrases`, `lint_translation_glossary`, `validate_translation` e `lint_cell_spelling`).
- **Arte prévia no codebase:** os testes existentes de UI, escala de zoom e benchmark em `tests/test_main_window.py`, `tests/test_zoom.py`, `tests/test_theme.py` e `tests/test_glossary.py` servem de modelo para fixtures sintéticas e validações via `QtBot`.

## Out of Scope

- Virtualização completa de modelo em disco ou paginação artificial de linhas (o modelo em memória atual suporta 10.000+ chaves sem necessidade de mudança de arquitetura de dados).
- Reescrita de QSS para remover estilização global ou migração de engine gráfica (ex.: Qt Quick/QML).
- Alterações no formato `.i18nproj`, no formato de backup ou no algoritmo cirúrgico de escrita em JSON.
- Mudanças em regras funcionais de validação, glossário ou correção ortográfica.

## Further Notes

- **Baseline observado antes da otimização (3.000 linhas, `cProfile`):**
  - `load+show`: `4,102 s`
  - `10 resizes` com `ResizeToContents`: `11,664 s` (`198.000` chamadas a `sizeHint`, `339.594` a `headerData`, `343.700` a `data`)
  - Protótipo isolado com `verticalHeader` em `Interactive`: `set_session+show` em `0,039 s` e `10 resizes` em `0,221 s`.
- Como linhas fora da tela mantêm `defaultSectionSize` até entrarem na janela visível, pequenas variações no tamanho do thumb da barra de rolagem vertical são esperadas e aceitáveis em troca de redimensionamento fluido a ~60fps.
