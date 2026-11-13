# 01: Protótipo comparativo ao vivo com identidade Stitch (Qt 6 Nativo vs `qt-material`)

**What to build:** Um protótipo executável e isolado que apresenta uma amostra representativa da interface do `i18n-reviewer` (barra de ferramentas com busca e ação principal, sidebar colapsável de arquivos/filtros, tabela multi-idioma com badges de status, editor de texto com destaque de tokens e Inspector em cards) usando a paleta esmeralda/neutra do mockup do Stitch, com um seletor ao vivo para alternar entre **Qt 6 Nativo (`Fusion` + `QPalette` + `QStyleHints.colorScheme()` + QSS)** e **`qt-material`** nos modos Claro e Escuro.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] O protótipo abre de forma independente sem alterar o fluxo ou o estado do app principal.
- [x] É possível alternar ao vivo entre o motor **Qt 6 Nativo** (Claro/Escuro) e **`qt-material`** (Claro/Escuro) sem reiniciar o protótipo.
- [x] A amostra exibe tabela multi-idioma com badges de status legíveis, sidebar de filtros/arquivos, toolbar com busca e botão `Send to Production`, e Inspector em cards com `Mark Reviewed + Next`.
- [x] O contraste de texto, badges e controles é legível tanto no modo Claro quanto no modo Escuro em ambos os motores.

