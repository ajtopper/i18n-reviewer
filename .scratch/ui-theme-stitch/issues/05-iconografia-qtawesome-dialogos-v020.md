# 05: Iconografia vetorial (`QtAwesome`), polimento dos diálogos e release `v0.2.0`

**What to build:** Padronizar a iconografia da barra de ferramentas, sidebar, Inspector e diálogos com ícones vetoriais adaptativos ao tema Claro/Escuro (`QtAwesome`), substituir estilos inline pontuais de banners e diálogos existentes pelo sistema de tema central, atualizar a versão e o changelog do projeto para `v0.2.0` e validar o pacote completo com `--self-test` e suíte de testes.

**Blocked by:** 03: Tokens semânticos da `QTableView`, `StatusCellDelegate` e `TokenHighlighter` (Claro/Escuro), 04: Redesign da toolbar, sidebar colapsável, barra de contexto e Inspector em cards (estilo Stitch)

**Status:** done

- [x] Toolbar, sidebar e ações principais utilizam ícones vetoriais que se adaptam automaticamente às cores do tema Claro e Escuro.
- [x] Banners de diagnóstico/sincronização externa e todos os diálogos (abertura de pacote, editor expandido, publicação, backup, conflitos, glossário e enrichers) seguem o tema central sem estilos inline quebrados no modo Escuro.
- [x] Versão do projeto e changelog atualizados para `v0.2.0` documentando o novo sistema de design e temas Claro/Escuro.
- [x] Suíte completa de testes, checagem de tipos e `--self-test` executam com sucesso após as mudanças finais.

