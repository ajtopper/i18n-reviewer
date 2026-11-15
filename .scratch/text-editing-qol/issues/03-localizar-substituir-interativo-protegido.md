# 03: Localizar e Substituir interativo (`Ctrl+H`) com proteção de spans técnicos

**What to build:** Disponibilizar um fluxo de Localizar e Substituir (`Ctrl+H`) para revisão de texto sobre as linhas atualmente visíveis na tabela (respeitando filtros de status, arquivo e pesquisa ativos). O usuário deve poder escolher o idioma/coluna alvo (pré-selecionando a coluna atual quando aplicável), alternar opções de *Case-sensitive*, *Palavra inteira* e *Proteger tokens técnicos* (ativada por padrão para impedir substituições dentro de placeholders, handlebars, enrichers do Foundry, URLs ou tags HTML), navegar até a próxima ocorrência correspondente e substituir a célula/ocorrência atual com registro individual na pilha de Undo/Redo e revalidação imediata da linha.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] `Ctrl+H` abre a interface de Localizar e Substituir (com rótulos em inglês internacional), pré-selecionando o idioma/coluna ativo quando aplicável e mantendo coerência com o tema Claro/Escuro e o zoom atual.
- [x] A busca respeita o escopo visível da tabela (filtros de status, arquivo e pesquisa) e aplica corretamente as opções de diferenciação de maiúsculas/minúsculas e palavra inteira.
- [x] Com a proteção de tokens técnicos ativa, ocorrências dentro de spans protegidos nunca são substituídas, preservando intactos placeholders, handlebars, enrichers, URLs e tags HTML.
- [x] *Find Next* navega até a próxima célula correspondente e *Replace* aplica a substituição na célula editável atual via pilha de Undo/Redo (`Ctrl+Z` / `Ctrl+Y`), revalidando ortografia, glossário e placeholders.
- [x] Testes automatizados cobrem busca/substituição unitária, proteção de tokens técnicos, respeito aos filtros visíveis e Undo/Redo.
