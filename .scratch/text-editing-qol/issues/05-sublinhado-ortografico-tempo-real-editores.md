# 05: Sublinhado ortográfico em tempo real dentro dos editores de texto

**What to build:** Tornar os erros ortográficos imediatamente visíveis enquanto o tradutor edita o texto, destacando palavras desconhecidas com sublinhado ondulado tanto no editor inline da tabela quanto no Editor Expandido (`Shift+F2`), inclusive na coluna Base quando editável. A detecção deve reutilizar as mesmas regras do corretor offline do app (ignorando spans técnicos, palavras presentes na base, termos do glossário, entradas do dicionário pessoal e avisos ignorados para o texto atual) e operar de forma responsiva durante a digitação sem interferir no destaque colorido de tokens técnicos nem nas cores dos temas Claro e Escuro.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Palavras apontadas pelo corretor ortográfico recebem sublinhado ondulado visual dentro do editor inline da tabela e do Editor Expandido, mantendo simultaneamente o destaque colorido dos tokens técnicos.
- [ ] Spans técnicos, termos do glossário, palavras idênticas à base e palavras adicionadas ao dicionário pessoal não são sublinhados como erro.
- [ ] Ao digitar ou corrigir uma palavra no editor, o sublinhado é atualizado de forma fluida (com debounce/cache) sem travar a digitação nem resetar a posição do cursor.
- [ ] Quando não há dicionário Hunspell disponível para o idioma, o editor continua funcionando normalmente sem falsos sublinhados.
- [ ] Testes automatizados validam marcação de erros ortográficos, exclusão de spans técnicos/glossário e atualização ao editar ou adicionar palavras ao dicionário pessoal.
