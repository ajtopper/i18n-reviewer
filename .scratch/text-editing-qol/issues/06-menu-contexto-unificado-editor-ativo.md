# 06: Menu de contexto unificado dentro do editor ativo (ortografia, PWL, tokens e glossário)

**What to build:** Substituir o menu de contexto padrão exibido ao clicar com o botão direito dentro do editor de texto ativo (no editor inline da tabela e no Editor Expandido) por um menu unificado orientado à tradução. O menu deve preservar as ações padrão de edição (Desfazer, Refazer, Recortar, Copiar, Colar, Selecionar Tudo) e incluir no topo as ações contextuais do app: sugestões de correção ortográfica para a palavra sob o cursor com substituição direta preservando a posição de edição, `Add '<word>' to dictionary` com limpeza imediata do sublinhado, inserção no cursor de tokens protegidos faltantes e aplicação de tradução do glossário ou envio do trecho selecionado para o cadastro do glossário. Também atualiza a versão do projeto para `v0.2.5` e documenta a melhoria no changelog.

**Blocked by:** 05: Sublinhado ortográfico em tempo real dentro dos editores de texto

**Status:** ready-for-agent

- [ ] Clicar com o botão direito sobre uma palavra sublinhada no editor inline ou no Editor Expandido exibe sugestões ortográficas do Hunspell e a opção de adicionar a palavra ao dicionário pessoal global.
- [ ] Escolher uma sugestão substitui apenas a palavra-alvo no cursor mantendo o editor ativo e revalidando imediatamente; adicionar ao dicionário pessoal remove o sublinhado na hora e revalida a sessão.
- [ ] O mesmo menu de contexto oferece inserção no cursor de tokens protegidos faltantes e aplicação/cadastro de termos do glossário (pré-preenchendo com o texto selecionado quando houver seleção), além das ações padrão de texto (Recortar, Copiar, Colar, Selecionar Tudo).
- [ ] Changelog e versão do aplicativo atualizados para `v0.2.5`, com testes automatizados cobrindo substituição ortográfica no cursor, adição ao dicionário pessoal e inserção de tokens/glossário dentro do editor ativo.
