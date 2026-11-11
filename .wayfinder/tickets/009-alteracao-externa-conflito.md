---
id: 9
title: Detecção de alteração externa e resolução de conflito
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [8]
parent: map
---

## Question

Se um arquivo de idioma (base ou destino) for alterado fora da ferramenta depois que o projeto tirou seu snapshot (git pull, outro editor, restauração de backup), como a ferramenta detecta e o que faz?

- Detecção: hash/mtime ao abrir o projeto, antes de enviar para produção, em tempo real (file watcher)?
- Granularidade: por arquivo ou por chave (merge de 3 vias snapshot × produção × edição local)?
- UI de resolução: aceitar a versão externa, manter a minha, comparar lado a lado; bloqueia o envio até resolver?
- Mudança na **base** (texto em inglês alterado): marca as traduções daquela chave como desatualizadas?

## Resolução

- **Detecção por hash SHA-256 do conteúdo dos arquivos** (com `mtime` apenas como atalho opcional quando inalterado):
  - Executada ao **abrir o `.i18nproj`**, **imediatamente antes de Enviar para Produção** (bloqueando se houver divergência até sincronizar/resolver) e por **monitoramento passivo em tempo real** (`QFileSystemWatcher` + checagem ao focar a janela), exibindo faixa não-intrusiva com botão *"Sincronizar agora"*.
  - Se um arquivo de origem/destino estiver ausente ou com JSON inválido no disco, a sincronização/envio é bloqueada com alerta explícito (não trata como arquivo vazio).
- **Merge em 3 vias por chave para arquivos de DESTINO (`snapshot × disco × rascunho_local`):**
  - Chave sem edição local (`dirty = False`): absorve o novo valor do disco e atualiza o snapshot; se o valor mudou e estava `reviewed`, rebaixa `review_status` para `unreviewed`.
  - Chave editada localmente para o mesmo texto do disco (`rascunho_local == disco`): atualiza o snapshot e limpa `dirty` (sem conflito).
  - Chave onde **ambos** mudaram de forma divergente (incluindo remoção no disco enquanto há `dirty = True`): marca **conflito real**.
- **UI de resolução de conflito:**
  - Diálogo listando as chaves em conflito com comparação **Snapshot anterior × Disco atual × Minha edição**, permitindo resolver por chave (*Manter minha edição*, *Aceitar do disco* ou *Editar manualmente*) ou em lote (*Manter todas minhas* / *Aceitar todas do disco*).
  - **Enviar para Produção** permanece bloqueado para arquivos com conflitos pendentes até a resolução.
- **Mudança externa no arquivo BASE (ex.: `en.json`):**
  - Atualiza o snapshot da base; para cada destino onde a chave estava `reviewed`, altera `review_status` para `stale` e grava `previous_base` no `.i18nproj` para exibir *"Base anterior × Base atual"* ao revisor (limpo ao aprovar ou reeditar e reaprovar).
  - Destinos ainda `unreviewed` apenas atualizam a coluna de referência sem virar `stale`.


