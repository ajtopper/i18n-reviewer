---
id: 8
title: Ciclo de vida do status por chave
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: []
parent: map
---

## Question

Qual é a máquina de estados do status de cada célula (chave × idioma de destino)?

- Estados além de `original`, `edited`, `reviewed`? (ex.: `missing`, `sent`/em produção, `stale` quando o texto da base muda depois da revisão).
- Transições: quem/como marca `reviewed` (ação explícita, atalho, revisar sem editar?), editar uma célula revisada volta para `edited`?
- O que acontece com os status após **Enviar para Produção** — reset, persistem, histórico?
- Definição precisa dos filtros *Apenas Pendentes* e *Apenas Editadas* em termos desses estados.
- O status vive só no `.i18nproj` ou também precisa sobreviver a um projeto novo sobre os mesmos arquivos?

## Resolução

- **Modelo em 2 eixos por célula `(chave, idioma_destino)`:**
  - **Estado de revisão (`review_status`):** `unreviewed` | `reviewed` | `stale` (mais existência derivada `missing` quando ausente no destino e sem rascunho local).
  - **Pendência de envio (`dirty`):** booleano **derivado** (`valor_local != snapshot_producao`). Se o usuário editar de volta ao texto idêntico ao de produção (ou acionar "Reverter célula"), `dirty` volta a `False` automaticamente.
- **Transições:**
  - Editar uma célula que diverge da produção torna `dirty = True` e rebaixa `review_status` para `unreviewed` (exigindo nova aprovação).
  - Marcar como revisado é uma **ação explícita** (botão/atalho, ex. `Ctrl+Enter`, a refinar no protótipo [014](014-prototipo-tabela.md)); permite aprovar textos já existentes sem editá-los (não aplicável a `missing`).
- **Enviar para Produção:**
  - Envia todas as células `dirty = True` do escopo; se alguma ainda estiver `unreviewed` ou `stale`, exibe aviso e pede confirmação antes de gravar.
  - Após a escrita bem-sucedida, o snapshot de produção é atualizado (`dirty` vira `False`), mas **`review_status` é preservado** no `.i18nproj` (`reviewed` continua `reviewed`; o que foi enviado sem revisão continua `unreviewed`).
- **Filtros da barra superior:**
  - *Apenas Pendentes*: linhas com ao menos um destino em `missing`, `stale` ou `unreviewed`.
  - *Apenas Editadas*: linhas com ao menos um destino com `dirty = True` (edições locais não enviadas para produção).
- **Persistência:** exclusiva no arquivo `.i18nproj`; nenhum metadado é gravado nos `lang/*.json` do módulo/sistema.


