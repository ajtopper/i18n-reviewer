# 01: Escala global de tema, fontes, atalhos de zoom (`Ctrl++`/`Ctrl+-`/`Ctrl+0`) e persistência

**What to build:** Permitir que o usuário aumente, reduza ou redefina o zoom da interface (`Ctrl++` / `Ctrl+=`, `Ctrl+-` e `Ctrl+0`, incluindo teclado numérico) em passos previsíveis (ex.: 80% a 200%, passos de 10%, padrão 100%). Toda a folha de estilos do tema (fontes base, cabeçalhos de seção, chips de chave, badges em pílula, campos de texto, botões, menus e diálogos como o Editor Expandido) deve escalar proporcionalmente sem estilos fixos que impeçam o crescimento do texto. O nível de zoom atual deve ser exibido na interface (barra de status ou controle discreto de zoom) e persistido nas configurações do usuário entre sessões, mantendo todos os rótulos da UI em inglês internacional.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Atalhos `Ctrl++` / `Ctrl+=` (teclado principal e numérico) aumentam o zoom, `Ctrl+-` reduz e `Ctrl+0` restaura para 100%, respeitando os limites mínimo e máximo definidos.
- [ ] Fontes, espaçamentos e controles de janela principal, menus, barra de ferramentas e diálogos (incluindo o Editor Expandido) escalam imediatamente com o fator de zoom tanto no modo Claro quanto no Escuro.
- [ ] O nível de zoom atual fica visível para o usuário e a preferência é salva e restaurada automaticamente nas configurações do aplicativo ao reabrir.
- [ ] Testes automatizados cobrem limites de zoom, atalhos, aplicação de tema escalado e persistência da preferência.
