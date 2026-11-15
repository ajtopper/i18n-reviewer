# 02: Escalonamento proporcional de tabela, badges, painéis e responsividade no zoom

**What to build:** Garantir que a tabela de tradução e a disposição dos painéis permaneçam proporcionais, legíveis e responsivas em qualquer nível de zoom. Ao alterar o zoom, a fonte monospace das chaves, as métricas de cálculo de altura das linhas (inclusive o fast-path e o modo compacto), a altura máxima das linhas, a faixa e a fonte dos badges de status desenhados nas células, o editor inline da tabela e as larguras proporcionais dos painéis laterais (sidebar, inspector, campo de busca e colunas) devem se adaptar automaticamente sem cortar textos, sobrepor badges ou espremer a tabela principal. Também atualiza a versão de lançamento para `v0.2.5` e registra as melhorias de zoom no changelog.

**Blocked by:** 01: Escala global de tema, fontes, atalhos de zoom (`Ctrl++`/`Ctrl+-`/`Ctrl+0`) e persistência

**Status:** done

- [x] A fonte da coluna de chaves, o editor inline e o texto exibido nas células da tabela acompanham o fator de zoom, com invalidação de cache de altura e recálculo imediato da altura das linhas (respeitando o modo normal e compacto).
- [x] Os badges de status e margens internas das células escalam proporcionalmente ao zoom sem cortar rótulos nem invadir o texto da tradução.
- [x] Sidebar, Inspector, barra de contexto, campo de busca e larguras iniciais de colunas ajustam suas restrições de tamanho de forma proporcional e responsiva, preservando usabilidade em janelas menores e maiores mesmo com zoom ampliado (ex.: 150%–200%).
- [x] Changelog atualizado para a versão `v0.2.5` e testes automatizados verificam recálculo de altura, proporção de badges/fontes e ausência de regressões de layout em diferentes níveis de zoom.
