# 05: Proteção de placeholders, enrichers e HTML (destaque, validação em cascata e exceções)

**What to build:** Durante a revisão e edição, a ferramenta extrai em cascata placeholders (`{nome}`), `{{handlebars}}`, enrichers do Foundry e de sistemas (`@UUID`, `@Embed`, inline rolls `[[...]]`, `&Reference`, `@Check`, `@Damage`, `@Template`, `@Localize`, `[[/act]]`, regras customizadas do projeto e heurística genérica), URLs e tags HTML/XML. O editor destaca visualmente os tokens protegidos, o painel Inspector e o menu de contexto permitem reinserir tokens faltantes com um clique, a tabela sinaliza erros críticos (faixa vermelha, bloqueando **Enviar para Produção** para o arquivo) vs. avisos (faixa âmbar, pedindo confirmação no envio) e o revisor pode registrar exceções (*"Ignorar este alerta"*) no `.i18nproj`.

**Blocked by:** 02: Edição inline/expandida, ciclo de status, filtros, busca e Undo/Redo

**Status:** ready-for-agent

- [ ] O extrator processa na ordem fixa: `{{handlebars}}` → enrichers conhecidos (core v14 + `dnd5e` + `pf2e`) + `custom_enrichers` do projeto + heurística genérica (`@Nome[...]`, `&Nome[...]`, `[[/nome ...]]`) → URLs → tags/entidades HTML/XML (incluindo tags do `pf2e` como `<actor>`, `<dc>`) → placeholders `{nome}` restantes, evitando que o `{rótulo}` de um enricher seja confundido com um placeholder `{nome}`.
- [ ] Separa em cada enricher a parte técnica (tipo, alvo/UUID, `#hash`, comando, fórmula, parâmetros técnicos — que devem ficar idênticos à base) das partes traduzíveis (`{rótulo}`, `#flavor` em rolagens, `name:` em `@Check` do `pf2e` e `caption="..."` em `@Embed`).
- [ ] Classifica como **Erro Crítico** (faixa lateral esquerda vermelha de 4 px na célula e bloqueio de publicação do arquivo no pré-envio, salvo exceção): conjunto de nomes únicos de placeholders `{nome}` divergente da base (ordem livre), `{{handlebars}}` alterado/ausente ou parte técnica de enricher alterada/ausente.
- [ ] Classifica como **Aviso** (faixa lateral esquerda âmbar de 4 px e confirmação no pré-envio): contagem diferente de repetições do mesmo `{nome}` quando os nomes únicos batem, tags ou atributos técnicos HTML/XML divergentes/desbalanceados, ou URL omitida/alterada.
- [ ] Detecta defeitos na própria string base (ex.: colisão entre `{rótulo}` de enricher e `{placeholder}` na mesma string) como aviso informativo na base/Inspector, sem nunca bloquear o envio.
- [ ] Os editores (inline e expandido) destacam por cor os tokens protegidos (`QSyntaxHighlighter`), e tanto o Inspector quanto a 2ª seção do menu de contexto oferecem clique/ação rápida para inserir tokens faltantes na posição do cursor (integrado ao `QUndoStack`).
- [ ] Permite marcar/desmarcar *"Ignorar este alerta"* por `(key_path, lang, rule_id)` com justificativa opcional (persistido em `ignored_warnings` com `value_hash`, reativando automaticamente o alerta se o texto mudar) e permite configurar `custom_enrichers` por projeto.
- [ ] Validação inicial do projeto roda em `QThreadPool` priorizando linhas visíveis e reavalia síncronamente a célula editada em tempo real; filtro *Todos os Alertas* na toolbar exibe todas as linhas com erro crítico ou aviso ativo.
- [ ] Testes `pytest` + `pytest-qt` cobrindo toda a cascata de extração (core, `dnd5e`, `pf2e`, genéricos, HTML, colisões na base), severidades, bloqueio no pré-envio e invalidação automática de `ignored_warnings` quando o valor muda.

