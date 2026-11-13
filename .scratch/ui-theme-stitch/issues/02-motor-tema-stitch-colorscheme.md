# 02: Motor de tema centralizado com paleta Stitch (Claro/Escuro) e `QStyleHints.colorScheme()`

**What to build:** Aplicar na inicialização do app o motor de tema validado no protótipo com os tokens de cor e estilo derivados do Stitch (Light e Dark), detectando e reagindo automaticamente às mudanças de esquema de cores do sistema operacional via `QStyleHints.colorScheme()`, além de oferecer ao usuário um seletor manual (Auto / Claro / Escuro) com preferência persistida entre sessões.

**Blocked by:** 01: Protótipo comparativo ao vivo com identidade Stitch (Qt 6 Nativo vs `qt-material`)

**Status:** done

- [x] O app inicia com o tema centralizado aplicado de forma consistente em toda a janela principal, barra de ferramentas, menus, inputs e barras de status.
- [x] Quando configurado em modo Auto, alternar o tema Claro/Escuro do sistema operacional atualiza a interface imediatamente sem reiniciar.
- [x] O usuário consegue escolher manualmente entre Auto, Claro e Escuro na interface, e a escolha é preservada ao reabrir o aplicativo.
- [x] Testes automatizados cobrem a resolução de tema (Auto/Claro/Escuro) e a inicialização limpa da aplicação.

