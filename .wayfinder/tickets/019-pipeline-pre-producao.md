---
id: 19
title: Pipeline de validação pré-produção e escrita atômica
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [7, 9, 10, 13, 15]
parent: map
---

## Question

Qual é a sequência exata executada ao clicar em **Enviar para Produção**, incluindo validações bloqueantes, avisos e falhas de I/O no Windows/OneDrive?

- **Ordem do pipeline:** (1) checagem de hashes SHA-256 no disco (se mudou → aborta envio e abre sincronização/merge 3-vias); (2) diagnóstico estrutural ([015](015-arquivos-malformados.md)) e conflitos estruturais ([006](006-chaves-faltantes-orfas.md)); (3) validação de placeholders/enrichers ([010](010-politica-placeholders.md)); (4) lista de confirmações únicas (avisos de HTML/URL, glossário, chaves duplicadas, células `dirty` ainda `unreviewed`, remoção de órfãs); (5) geração de payload em memória + validação estrita `json.loads`; (6) criação do lote de backup; (7) escrita atômica `.tmp` + `os.replace`.
- **Escopo do envio:** enviar todos os idiomas modificados de uma vez ou permitir escolher no diálogo de resumo quais idiomas publicar?
- **Falhas parciais e Windows/OneDrive:** `PermissionError` em `os.replace` (arquivo bloqueado pelo Foundry/OneDrive/antivírus) — quantas tentativas com backoff curto, e se falhar no arquivo 2 de 3, oferece rollback automático do arquivo 1 ou mantém backup?

## Resolução

- **Ordem do pipeline ao acionar Enviar para Produção:**
  1. **Seleção de escopo:** diálogo de resumo lista os arquivos com `dirty = True` (ou remoção de órfãs) com checkboxes, permitindo publicar apenas os idiomas selecionados e desmarcar idiomas com erros bloqueantes ou rascunhos inacabados.
  2. **Checagem de disco (SHA-256):** verifica todos os arquivos selecionados (e a base); se algum mudou fora do app, interrompe o envio e abre a sincronização/merge 3-vias ([009](009-alteracao-externa-conflito.md)).
  3. **Bloqueios estruturais e críticos:** trava o envio dos arquivos marcados caso tenham JSON inválido/folha-antes-de-ramo ([015](015-arquivos-malformados.md)), conflito estrutural ([006](006-chaves-faltantes-orfas.md)) ou erro crítico de placeholder/`{{hbs}}`/parte técnica de enricher sem exceção registrada ([010](010-politica-placeholders.md)).
  4. **Confirmação única de avisos:** agrupa numa única tela os avisos não-bloqueantes dos arquivos marcados (HTML/URL, glossário, chaves duplicadas, células `dirty` ainda `unreviewed`/`stale` e lista de chaves órfãs a remover).
  5. **Validação em memória do payload final:** após aplicar as edições por spans, executa `json.loads` estrito, simula o `expandObject` do Foundry (garantindo ausência de folha-antes-de-ramo ou sobrescrita estrutural acidental) e verifica que o mapa resultante confere exatamente com as edições/remoções planejadas (fail-safe do writer).
  6. **Backup agrupado (`publish`):** cria o lote em `%APPDATA%\i18n-reviewer\backups\<project_id>\` contendo os `.bak` íntegros apenas dos arquivos selecionados ([013](013-politica-backups.md)).
  7. **Escrita atômica com resiliência Windows/OneDrive:** grava `<alvo>.tmp` no mesmo diretório do destino e aplica `os.replace` com até **5 tentativas** em backoff curto (`100–500 ms`) para contornar locks transitórios de OneDrive/antivírus.
- **Falha parcial no lote:** se algum arquivo falhar após os retries, interrompe os arquivos restantes e oferece ao usuário **reverter imediatamente** os já gravados usando o lote de backup recém-criado ou mantê-los (atualizando no projeto o snapshot/dirty apenas dos arquivos efetivamente gravados).


