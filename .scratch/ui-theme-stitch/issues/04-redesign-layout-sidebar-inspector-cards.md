# 04: Redesign da toolbar, sidebar colapsável, barra de contexto e Inspector em cards (estilo Stitch)

**What to build:** Reorganizar a janela principal seguindo a hierarquia visual do Stitch adaptada ao domínio do `i18n-reviewer`: toolbar limpa com busca em destaque e botão primário `Send to Production` em esmeralda, sidebar esquerda colapsável com filtros rápidos de status e lista de arquivos JSON do pacote real, barra de contexto/contagem acima da tabela multi-idioma, e Inspector lateral estruturado em cards (Metadados da Chave, Diagnóstico/Stale/Glossário e rodapé de ações com destaque em `Mark Reviewed + Next`), preservando todos os atalhos e fluxos existentes.

**Blocked by:** 02: Motor de tema centralizado com paleta Stitch (Claro/Escuro) e `QStyleHints.colorScheme()`

**Status:** done

- [x] A sidebar esquerda colapsável permite filtrar rapidamente por status e por arquivo do pacote real, mantendo sincronia com os filtros da toolbar.
- [x] A barra de contexto acima da tabela exibe o arquivo/filtro ativo e a contagem de chaves filtradas em tempo real.
- [x] O Inspector exibe Metadados, Diagnóstico/Stale/Glossário e Ações em cards com hierarquia clara nos modos Claro e Escuro, mantendo todos os botões e atalhos (`Ctrl+Enter`, `Ctrl+Down`, `Shift+F2`, etc.) funcionando.
- [x] Testes de UI verificam a sincronia entre sidebar/filtros, exibição de cards do Inspector e atalhos principais.

