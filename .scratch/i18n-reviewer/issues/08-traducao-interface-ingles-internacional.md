# 08: Tradução completa da interface e mensagens para Inglês Internacional

**What to build:** Toda a experiência visível ao usuário do i18n Reviewer passa a ser apresentada em Inglês Internacional natural e consistente antes do empacotamento final. Isso abrange janela principal, barra de ferramentas, filtros, barra de status, banners informativos, cabeçalhos e badges das células da tabela, painel Inspector, todas as 4 seções do menu de contexto, textos da pilha Undo/Redo, todos os diálogos modais (abertura de pacote, resolução de conflitos, pré-envio para produção, restauração de backups, editor expandido, regras customizadas de enrichers e gerenciador de glossário) e todas as mensagens de erro, bloqueio, aviso e validação exibidas ao revisor, preservando intactos os termos técnicos do domínio Foundry e os dados/chaves dos módulos carregados.

**Blocked by:** 07: Corretor ortográfico Hunspell (pyenchant), dicionário pessoal e contorno não-ASCII no Windows

**Status:** done

- [x] A janela principal, barra de ferramentas, combos de filtro e arquivo, campo de busca, mensagens da status bar, banners (diagnóstico do pacote e alteração externa) e confirmações de saída estão 100% em Inglês Internacional.
- [x] A tabela exibe cabeçalhos (`Base`, estado de ausência de ortografia e tooltips), indicadores de ausência/vazio/não-string e badges de célula (`MISSING`, `[empty]`, `= base`, `ORPHAN`, `[non-string]`, `CONFLICT`, `REMOVE`, `EDITED`, `EDITED · OK`, `STALE`, `OK`) em Inglês Internacional.
- [x] O painel Inspector e os comandos do Undo/Redo exibem rótulos de estado, detalhes stale (`Before` / `Now`), diagnósticos e botões de ação em Inglês Internacional.
- [x] Todos os diálogos modais (abertura de pacote, conflitos de merge 3-vias, envio para produção, restauração de backups, editor expandido, regras de enrichers e gerenciador de glossário + popup `Ctrl+Space`) têm títulos, rótulos, botões, cabeçalhos, filtros de arquivo e mensagens inteiramente em Inglês Internacional.
- [x] Todas as 4 seções do menu de contexto e todas as mensagens de validação (erros críticos/avisos, bloqueios de pré-envio, inconsistências de glossário e alertas/sugestões do corretor Hunspell) estão em Inglês Internacional, sem strings residuais em português na interface.
- [x] Nenhum identificador técnico do protocolo Foundry, dado de localização do usuário, esquema do arquivo de projeto nem código fonte de idiomas (`pt-BR`, `es`, `fr`, `de`, `eo`) é alterado pela tradução da interface.
- [x] Verificação automatizada confirma ausência de strings de interface em português e toda a suíte `pytest` + `pytest-qt` e `mypy` passa com as asserções atualizadas para Inglês Internacional.

