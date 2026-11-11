---
id: 13
title: Política de backups e restauração
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [8]
parent: map
---

## Question

Como os backups funcionam num projeto com vários arquivos de destino?

- Localização: `.i18n_backups/` dentro da pasta `lang/` do módulo (polui o repositório git do módulo → `.gitignore`?) vs. pasta do app (`%APPDATA%`) vs. ao lado do `.i18nproj`.
- Um envio para produção com N idiomas gera N `.bak` independentes ou um snapshot agrupado (restaurar "o envio de 16:45" de uma vez)?
- Nomenclatura (`pt-BR_2026-11-11_164500.bak`) e colisão no mesmo segundo.
- Retenção: manter tudo, últimos N, por idade; limpeza manual.
- Restaurar: o que acontece com o projeto aberto e os status (interage com a detecção de alteração externa); a restauração em si gera backup do estado atual antes?

## Resolução

- **Localização (substitui `.i18n_backups/` dentro de `lang/` da spec inicial):** armazenados fora do pacote do Foundry, em `%APPDATA%\i18n-reviewer\backups\<project_id>\` (usando um ID estável guardado no `.i18nproj`), mantendo o repositório git do módulo/sistema 100% limpo.
- **Snapshot agrupado por envio:** cada **Enviar para Produção** cria um lote com timestamp + sufixo sequencial/ms para evitar colisão (`YYYY-MM-DD_HHMMSS_NNN/`), contendo um `manifest.json` (data/hora, tipo `publish` ou `pre-restore`, caminhos e hashes SHA-256) e uma cópia `.bak` byte a byte **apenas** dos arquivos modificados naquele envio. O diálogo permite restaurar o **lote inteiro** ou **um arquivo individual**.
- **Retenção:** mantém por padrão os **últimos 30 lotes** por projeto (configurável), com rotação automática dos mais antigos ao criar novo backup, além de exclusão manual pelo diálogo de backup.
- **Segurança na restauração:**
  - Antes de reverter, cria automaticamente um snapshot `pre-restore` com o estado atual em produção dos arquivos envolvidos.
  - Valida o `.bak` antes de aplicar e grava no destino via arquivo temporário no mesmo diretório + substituição atômica (`os.replace`).
- **Efeito no projeto aberto:** ao restaurar, o usuário escolhe entre **(A)** apenas reverter produção e sincronizar via merge 3-vias do [ticket 009](009-alteracao-externa-conflito.md) (preservando/resolvendo rascunhos locais `dirty`) ou **(B)** descartar também os rascunhos locais dos arquivos restaurados. Células `reviewed` cujo valor em produção mudou voltam para `unreviewed`.


