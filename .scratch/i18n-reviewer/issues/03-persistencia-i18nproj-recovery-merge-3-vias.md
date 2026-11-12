# 03: Persistência .i18nproj, recuperação de crash e sincronização externa (merge 3-vias)

**What to build:** O usuário salva e reabre seu projeto num arquivo `.i18nproj` portável (`Ctrl+S`), mantendo todo o trabalho em andamento (`drafts`, `review_state`, snapshots SHA-256 e configurações do pacote) sem tocar nos arquivos JSON do módulo. Se o aplicativo fechar inesperadamente, um rascunho de recuperação em `%APPDATA%` oferece restaurar a sessão ao reabrir. Quando arquivos de idioma (base ou destino) mudam no disco fora da ferramenta (ex.: `git pull`), o aplicativo detecta por SHA-256 (ao abrir, via watcher/foco da janela), realiza merge automático de 3 vias por chave para mudanças sem conflito, marca traduções `reviewed` como `stale` (guardando o texto base anterior para exibir *Antes × Agora*) quando a base muda e abre um diálogo lado a lado para resolver conflitos reais.

**Blocked by:** 02: Edição inline/expandida, ciclo de status, filtros, busca e Undo/Redo

**Status:** done

- [x] Salva e carrega `.i18nproj` (`schema_version: 1`, `indent=2, ensure_ascii=False`) usando escrita atômica (`.tmp` + `os.replace`), sugerindo por padrão pasta fora do repositório Git do módulo, com indicador `*` de alterações não salvas na janela e confirmação ao fechar.
- [x] Armazena `package_root_rel` (relativo ao `.i18nproj` quando no mesmo drive) + `package_root_abs` como fallback e caminhos dos arquivos de idioma relativos ao pacote; ao abrir, tenta relativo primeiro, depois absoluto, e exibe diálogo *"Relocalizar pasta do pacote"* se nenhum existir.
- [x] Migra automaticamente versões anteriores de `schema_version` criando backup prévio do `.i18nproj`, e recusa abrir arquivos com `schema_version` superior à suportada pelo app com mensagem clara.
- [x] Grava rascunho automático de crash recovery em `%APPDATA%\i18n-reviewer\recovery\<project_id>.json` durante a sessão e remove-o ao salvar ou fechar normalmente; ao abrir com recovery pendente, oferece restaurar o trabalho não salvo.
- [x] Verifica o hash SHA-256 de todos os arquivos do projeto ao abrir o `.i18nproj` e passivamente com o app aberto (`QFileSystemWatcher` + evento de foco da janela), exibindo faixa não-intrusiva com botão *"Sincronizar agora"*; arquivos ausentes ou com JSON inválido no disco bloqueiam a sincronização com alerta explícito.
- [x] No merge de 3 vias por chave nos arquivos de destino (`snapshot × disco × rascunho_local`): chaves com `is_dirty = False` absorvem o valor do disco (rebaixando `reviewed` para `unreviewed` se o texto mudou); chaves onde `rascunho_local == disco` atualizam o snapshot e limpam `is_dirty`; chaves onde disco e rascunho mudaram de forma divergente (incluindo remoção no disco enquanto `is_dirty = True`) entram em estado de conflito real.
- [x] Diálogo de resolução de conflitos exibe *Snapshot anterior × Disco atual × Minha edição* lado a lado, permitindo resolver por chave (*Manter minha edição*, *Aceitar do disco*, *Editar manualmente*) ou em lote (*Manter todas minhas* / *Aceitar todas do disco*).
- [x] Quando o texto base de uma chave muda externamente, atualiza o snapshot da base e altera destinos que estavam `reviewed` para `stale`, gravando `previous_base` no `.i18nproj` e exibindo *Base anterior × Base atual* no Inspector (limpando `previous_base` quando a célula volta a ser aprovada).
- [x] Testes `pytest` + `pytest-qt` cobrindo serialização/portabilidade do `.i18nproj`, relocalização de pacote, crash recovery, merge 3-vias (absorção silenciosa, convergência e conflito real) e transição `reviewed → stale`.

