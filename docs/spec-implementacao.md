---
title: "Especificação de Implementação — i18n Reviewer"
labels: [ready-for-agent, spec]
status: open
source_map: "../.wayfinder/map.md"
---

# Especificação de Implementação: i18n Reviewer

> Sintetizada a partir do [mapa Wayfinder](../.wayfinder/map.md) e dos 22 tickets de decisão e pesquisa concluídos em `.wayfinder/tickets/`. Prevalece sobre a [Especificação Técnica Inicial](spec-inicial.md).

---

## Problem Statement

Desenvolvedores e tradutores de módulos e sistemas do Foundry VTT precisam revisar, editar e manter múltiplos arquivos de localização (`lang/*.json`) sincronizados com um idioma de referência (geralmente `en.json`). Editar esses JSONs manualmente em editores de texto traz problemas recorrentes:

1. **Risco de corrupção estrutural e diffs sujos no Git:** reformatar o arquivo inteiro altera indentação, quebras de linha (`CRLF`/`LF`), linhas em branco, objetos inline ou ordem de chaves, gerando diffs gigantescos; erros como chaves duplicadas ou uma chave folha seguida de ramo com o mesmo prefixo (`"A.B": "x"` antes de `"A.B.C": "y"`) fazem o Foundry VTT descartar silenciosamente chaves ou o arquivo inteiro.
2. **Quebra de sintaxes embutidas:** placeholders (`{name}`, `{count}`), expressões `{{handlebars}}`, tags HTML/XML e enrichers do Foundry/sistemas (`@UUID[...]{label}`, `[[/r ...]]`, `&Reference[...]`, `@Check[...]`, `@Damage[...]`) traduzidos ou apagados por engano exibem `"undefined"` ou quebram links e rolagens dentro do jogo.
3. **Inconsistência terminológica e erros ortográficos:** termos recorrentes de RPG ("Spell Slot" → "Espaço de Magia") são traduzidos de formas divergentes ao longo de milhares de chaves, e corretores genéricos baseados em listas simples (como `pyspellchecker`) rejeitam grafias brasileiras, elisões francesas, compostos alemães e flexões verbais em espanhol, além de marcarem tokens técnicos como erros.
4. **Falta de fluxo de revisão incremental e segurança de publicação:** não há separação nativa entre rascunho em revisão e arquivo de produção do módulo, nem detecção de alterações externas (ex.: `git pull` atualizando o inglês base e deixando traduções antigas desatualizadas) ou rollback rápido com escrita atômica.

---

## Solution

O **i18n Reviewer** é uma aplicação desktop Windows em **Python 3.14 (64-bit) + PySide6** que carrega pacotes do Foundry VTT a partir do seu manifest (`module.json` / `system.json`), apresenta todos os idiomas lado a lado numa tabela multilíngue orientada a revisão por teclado, protege tokens técnicos e sintaxes do Foundry, aplica linting de glossário em dois níveis (global e por projeto) e verificação ortográfica real via **Hunspell (`pyenchant` + dicionários LibreOffice)**, isola todo o trabalho em andamento num arquivo `.i18nproj` sem tocar nos JSONs do módulo, e publica em produção com **preservação cirúrgica de estilo (por spans)**, backups agrupados fora do repositório Git e escrita atômica resiliente a locks do Windows/OneDrive.

---

## User Stories

1. Como tradutor/revisor, quero abrir um módulo ou sistema do Foundry apontando para o seu `module.json` ou `system.json`, para que a ferramenta descubra automaticamente todos os arquivos declarados em `languages[]`.
2. Como tradutor, quero que o idioma `en` seja pré-selecionado como base quando existir (ou o 1º idioma do manifest), mas podendo trocar o idioma base ou apontar um arquivo `en.json` externo, para revisar também módulos que só declaram a própria tradução (ex.: pacotes `fvtt-brasil`) ou pacotes cujo `en` aponta para outro idioma.
3. Como revisor de um sistema grande (ex.: `pf2e` com múltiplos arquivos por idioma), quero ver todas as chaves de um idioma unificadas numa única coluna, vendo no painel Inspector de qual arquivo cada chave veio e podendo filtrar por arquivo quando necessário.
4. Como revisor, quero ser avisado discretamente quando o manifest tiver entradas com `path` HTTP remoto (listadas como não-editáveis), entradas condicionais (`system`/`module`) ou códigos de idioma fora do padrão BCP-47 (`pt-br` vs `pt-BR`), sem que a ferramenta altere o manifest sozinha.
5. Como revisor, quero visualizar na tabela a coluna `KEY_PATH` (monoespaçada, somente leitura), a coluna do idioma base (somente leitura) e N colunas de idiomas de destino editáveis, podendo ocultar/exibir colunas de idiomas com checkboxes na barra superior para focar apenas nos idiomas que estou revisando.
6. Como revisor, quero que cada célula de destino tenha dois eixos independentes de estado — **estado de revisão** (`unreviewed`, `reviewed`, `stale`, além de `missing` derivado) e **pendência de envio** (`dirty`, derivado da comparação `valor_local != snapshot_producao`) — para distinguir claramente o que já foi aprovado do que ainda não foi gravado nos arquivos do módulo.
7. Como revisor, quero aprovar uma célula que já estava boa em produção sem precisar editá-la (via `Ctrl+Enter` ou botão), marcando-a como `reviewed` e pulando automaticamente para a próxima célula pendente.
8. Como revisor, quero que qualquer edição cujo texto divirja do snapshot de produção marque a célula como `dirty = True` e rebaixe `review_status` para `unreviewed`, e que voltar o texto exatamente ao valor de produção (ou acionar *"Reverter para produção"*) limpe `dirty` automaticamente.
9. Como revisor, quero distinguir visualmente na célula — sem sobrepor o texto — os badges `OK` (verde suave: `reviewed` e limpo), `EDITADO` (amarelo suave: `dirty` e `unreviewed`), `EDITADO · OK` (amarelo suave: `dirty` e `reviewed`), `STALE` (lilás: texto base mudou depois da revisão) e `MISSING` (cinza itálico: ausente no destino), além de uma faixa lateral esquerda de 4 px vermelha (erro crítico) ou âmbar (aviso).
10. Como revisor, quero filtrar a tabela por *Todas*, *Apenas Pendentes* (`missing`, `stale` ou `unreviewed`), *Apenas Editadas* (`dirty = True`), *Inconsistências de Glossário* ou *Todos os Alertas*, e buscar por chave ou texto (`Ctrl+F`) com resposta fluida mesmo em pacotes de 10 000+ chaves.
11. Como revisor, quero ver chaves que existem na base e faltam no destino (`missing`), chaves com string vazia `""` (marcadas com alerta `[vazia]` em Pendentes, pois impedem o fallback do Foundry) e chaves com texto idêntico à base (marcadas com `= base` enquanto `unreviewed`, saindo de Pendentes ao aprovar).
12. Como revisor, quero que categorias plurais exigidas pelo idioma de destino (conforme CLDR / `Intl.PluralRules`, ex.: `.many` em `pt-BR`, `es`, `fr` sob prefixos `.one`/`.other` da base) não sejam tratadas como órfãs e sejam sugeridas como `missing` quando faltarem no destino.
13. Como revisor, quero ver chaves que existem apenas no destino e não na base com badge `ÓRFÃ`, sabendo que a ferramenta nunca as apagará sozinha e que posso marcá-las para remoção com confirmação explícita.
14. Como revisor, quero que textos curtos/médios sejam editados inline (`F2` / duplo clique) e textos longos ou com muito HTML contem com um **Editor Expandido** (`Shift+F2` ou botão no Inspector) lado a lado (Base × Tradução), mantendo as linhas da tabela limitadas a ~5 linhas (~110 px) para não degradar a rolagem.
15. Como revisor, quero usar `Ctrl+Z` e `Ctrl+Y` (`QUndoStack`) na sessão para desfazer/refazer edições de texto, aplicação de sugestões de glossário/ortografia, marcação de `reviewed`, reversão de célula e marcação de remoção de órfãs.
16. Como revisor, quero que placeholders (`{nome}`), `{{handlebars}}`, URLs, tags HTML/XML (`<strong>`, `<actor>`) e partes técnicas de enrichers (`@UUID[alvo]{rótulo}`, `[[/r fórmula # flavor]]{rótulo}`, `&Reference[...]`, `@Check[...]`, `@Damage[...]`, `@Template[...]`, `@Localize[...]`, `[[/act ...]]`) sejam destacados por cor no editor e validados em tempo real, permitindo traduzir apenas os rótulos/flavors.
17. Como revisor, quero reinserir rapidamente um token protegido faltante clicando nele no painel Inspector ou pelo menu de contexto da célula.
18. Como revisor, quero poder marcar *"Ignorar este alerta"* por `(chave, idioma, regra)` com justificativa opcional quando uma divergência de placeholder, HTML ou glossário for intencional, sabendo que o alerta voltará automaticamente se o texto mudar depois.
19. Como revisor, quero manter um glossário em dois níveis — **Global** do usuário e **Por Projeto** (onde o projeto sobrescreve termos iguais do global) — com suporte a variantes/flexões aceitas por idioma, flag *"Não traduzir"* (`do_not_translate`), flag `case_sensitive` e importação/exportação em `glossary.json` e `CSV`.
20. Como revisor, quero pressionar `Ctrl+Space` durante a edição para abrir um popup com os termos do glossário detectados na string base e inserir a tradução preferida no cursor (ou adicionar rapidamente um termo selecionado ao glossário via menu de contexto).
21. Como revisor, quero verificação ortográfica precisa em `pt-BR`, `es`, `fr` e `de` desde o primeiro dia (e suporte a qualquer dicionário Hunspell `.aff/.dic` que eu colocar na pasta do usuário, como `eo`), ignorando automaticamente spans técnicos, termos do glossário, siglas em MAIÚSCULAS, números/dados (`1d20`), tokens de ≤ 2 letras (`h`, `m`, `ft`) e palavras idênticas à base.
22. Como revisor, quero clicar com o botão direito numa célula para ver um menu de contexto organizado em 4 seções fixas (Revisão/Célula → Placeholders faltantes → Glossário → Sugestões de ortografia e *"Adicionar ao dicionário"* pessoal global).
23. Como revisor, quero salvar meu trabalho num arquivo `.i18nproj` portável (`Ctrl+S`), podendo fechar e reabrir o aplicativo sem tocar nos arquivos JSON do módulo e contando com recuperação automática caso o aplicativo feche inesperadamente.
24. Como revisor, quero que a ferramenta detecte por hash SHA-256 (ao abrir o projeto, ao focar a janela/watcher e antes de publicar) se algum arquivo do módulo foi alterado por fora (ex.: `git pull`), fazendo merge automático de 3 vias por chave para o que não colide, abrindo um diálogo lado a lado (*Snapshot × Disco × Minha edição*) apenas para chaves em conflito real e marcando como `stale` (com comparativo *Base anterior × Base atual*) as chaves já revisadas cujo texto base mudou.
25. Como desenvolvedor de módulo, quero que a ferramenta diagnostique arquivos malformados — bloqueando o envio em caso de JSON inválido ou folha-antes-de-ramo (que faz o Foundry descartar o arquivo todo), apontando linhas de chaves duplicadas (editando a última ocorrência, que é a efetiva no Foundry) e exibindo folhas não-string como somente-leitura `[não-string]` — sem nunca reestruturar meu arquivo às escondidas.
26. Como desenvolvedor de módulo, quero clicar em **Enviar para Produção**, escolher por checkbox quais idiomas modificados publicar, revisar um resumo único de avisos e ter certeza de que apenas os valores editados (e chaves criadas/removidas) mudarão no diff do Git, preservando byte a byte a formatação, indentação, linhas em branco, objetos inline e quebras de linha originais.
27. Como desenvolvedor de módulo, quero que cada envio para produção crie antes um lote de backup agrupado em `%APPDATA%\i18n-reviewer\backups\<project_id>\` (sem sujar o `git status` do módulo) e grave cada arquivo via `.tmp` + `os.replace` com retries para locks do OneDrive, permitindo restaurar o lote inteiro ou um idioma individual com um clique (criando um backup `pre-restore` antes de reverter).

---

## Implementation Decisions

### 1. Stack, Runtime e Arquitetura de Módulos

- **Runtime alvo:** CPython 3.14.x 64-bit no Windows.
- **Dependências de runtime:** `PySide6-Essentials==6.12.0`, `shiboken6==6.12.0`, `pyenchant==3.3.0`.
- **Dependências de build:** `pyinstaller==6.22.3`, `pyinstaller-hooks-contrib==2026.10`.
- **Divisão arquitetural:**
  - `json_handler`: scanner JSON estrito em Python puro com mapeamento de spans, expansão lógica compatível com `expandObject` do Foundry, diagnóstico estrutural e writer cirúrgico por spans.
  - `project_manager`: descoberta de pacotes via manifest (`module.json` / `system.json`), serialização/migração do `.i18nproj`, crash recovery, detecção de alterações externas por SHA-256, merge de 3 vias por chave e máquina de estados de revisão.
  - `validation_service` (ou integrado ao domínio): extração em cascata de placeholders, `{{handlebars}}`, enrichers, URLs e HTML/XML, cálculo de severidade e verificação de exceções ignoradas.
  - `glossary_service`: gerenciamento do glossário em 2 níveis (Global + Projeto), importação/exportação JSON/CSV e linter com mascaramento de spans técnicos.
  - `spell_service`: adaptador sobre `pyenchant` (provider Hunspell), resolução de caminhos não-ASCII no Windows, verificação por palavra-sentinela, PWL global por idioma e tokenização com filtro de ruído.
  - `backup_manager`: lotes de backup agrupados (`publish` e `pre-restore`) em `%APPDATA%`, rotação automática, restauração seletiva/completa e escrita atômica com retries.
  - `ui`: janela principal, `QAbstractTableModel` + `QSortFilterProxyModel`, delegate de status/alertas, painel lateral Inspector, Editor Expandido (`Shift+F2`), diálogos de conflito, pré-publicação, glossário e backups, `QUndoStack` e workers em `QThreadPool`.

### 2. Descoberta de Pacotes, Idioma Base e Multi-Arquivo

- **Leitura do manifest:** lê `languages[]` de `module.json` ou `system.json` (`lang`, `name`, `path`, `system`, `module`). Caminhos são resolvidos relativos à raiz do pacote (rejeitando `..` fora do pacote).
- **Entradas especiais:**
  - `path` HTTP/HTTPS: listadas como não-editáveis com aviso na criação do projeto.
  - Condicionais (`system` / `module`): carregadas por padrão (com opção de desmarcar na criação do projeto), exibindo a condição no Inspector/cabeçalho.
  - Capitalização de `lang`: nunca modifica o manifest, mas emite aviso discreto se o código não seguir BCP-47 (ex.: `pt-br`) ou se houver dois códigos que diferem apenas por caixa.
- **Escolha da base:** pré-seleciona `en` quando presente (senão o 1º idioma), permitindo trocar o idioma base na criação do projeto ou apontar um arquivo `base_external_path` fora do manifest.
- **Múltiplos arquivos por idioma:** unificados numa única coluna por `lang`, mesclados na ordem do manifest (último vence em colisões, sinalizando a colisão no diagnóstico). Cada chave mantém referência ao seu arquivo de origem (visível no Inspector e filtrável na toolbar). Chaves novas (`missing` traduzidas) vão para o arquivo-espelho correspondente ao da base (mapeado no projeto) ou para o arquivo principal definido pelo usuário.

### 3. Leitura de JSON, Diagnóstico de Malformados e Writer por Spans

- **Princípio de não-interferência:** a ferramenta nunca reestrutura nem apaga chaves automaticamente fora das edições do usuário; arquivos sem edições nunca são reescritos.
- **Scanner JSON próprio estrito (Python puro):**
  - Lê os bytes brutos (detectando presença de BOM UTF-8, `CRLF` vs. `LF`, newline final, indentação predominante e se 100% dos caracteres não-ASCII estão escapados com `\uXXXX`).
  - Mapeia cada par `chave: valor` e objetos pai com seus spans exatos `(start_byte, end_byte)` e linha/coluna.
  - Constrói o caminho lógico expandido dividindo em `.` (espelhando `foundry.utils.expandObject`).
- **Política para arquivos malformados:**
  - **Erro de sintaxe JSON** ou **folha seguida de ramo com o mesmo prefixo** (`"A": "str"` antes de `"A.B": "x"`, que faz o Foundry descartar o arquivo inteiro): abre o arquivo em modo diagnóstico/somente-leitura apontando linha e erro, e **bloqueia Enviar para Produção** para aquele arquivo sem travar os demais.
  - **Sobrescrita silenciosa no `expandObject`** (`"A.C": "y"` seguido de `"A": {"B": "x"}` ou ramo seguido de folha): abre apontando as chaves/linhas perdidas com alerta antes de publicar.
  - **Chaves duplicadas no mesmo arquivo:** abre normalmente apontando as linhas duplicadas, exibe e edita o span da **última ocorrência** (a que vence no `JSON.parse`/Foundry) e pede confirmação no envio sem remover a ocorrência antiga sozinho.
  - **Folhas não-string (`null`, número, booleano, array):** exibidas na tabela como somente-leitura com badge `[não-string]` (e alerta se a base tiver string).
- **Edição, inserção e remoção cirúrgica por spans:**
  - **Alteração de valor:** substitui apenas o span do literal do valor editado. Grafia de caracteres não-ASCII no novo literal usa `ensure_ascii=True` somente se o arquivo de destino inteiro escapar todos os não-ASCII; caso contrário (UTF-8 literal ou misto), usa `ensure_ascii=False` sem tocar nos valores vizinhos.
  - **Inserção de chave nova (`missing` traduzida):** inserida na **posição relativa da base** (logo após o vizinho/ancestral anterior da base presente no destino, ou no topo do bloco / fim do arquivo se não houver anterior), seguindo o **estilo do próprio arquivo de destino** (plano no plano, aninhado no aninhado criando os objetos intermediários necessários; em arquivo misto, dentro do objeto pai se existir ou seguindo o estilo do bloco/vizinho), com a indentação e EOL do destino (herdando da base apenas se o destino for novo/vazio).
  - **Remoção de chave órfã:** só ocorre quando marcada explicitamente pelo usuário com confirmação; remove o par e a vírgula adjacente preservando o entorno e poda objetos pai que ficarem vazios após a remoção.

### 4. Modelo de Célula, Ciclo de Status, Chaves Faltantes/Órfãs e Plurais

```python
# Modelo conceitual validado no protótipo (Ticket 014) e decisões (Tickets 006, 008, 009)
@dataclass
class CellState:
    prod_value: str | None          # None = ausente no arquivo de produção
    local_value: str | None         # None = sem tradução local (missing); se != prod_value => dirty=True
    marked_for_deletion: bool = False  # Para chaves órfãs marcadas para remoção
    review_status: Literal["unreviewed", "reviewed", "stale"] = "unreviewed"
    previous_base: str | None = None   # Preenchido quando review_status == "stale"
```

- **Regras de transição:**
  - `dirty` é sempre derivado: `(local_value != prod_value) or marked_for_deletion`. Se o usuário editar de volta ao valor idêntico ao de produção (ou acionar *"Reverter para produção"*), `dirty` volta a `False` automaticamente.
  - Editar uma célula que diverge da produção torna `dirty = True` e define `review_status = "unreviewed"`.
  - Marcar como `reviewed` é uma ação explícita (`Ctrl+Enter`, menu ou botão); permite aprovar textos já existentes sem editá-los (não aplicável a `missing`).
  - Após **Enviar para Produção** com sucesso: `prod_value` passa a ser `local_value` (`dirty` vira `False`), mas `review_status` é **preservado** no `.i18nproj`.
- **Diferenciação `missing` × `""` × `= base`:**
  - `missing` (`local_value is None`): não existe no destino; só é criada no arquivo de produção se receber tradução.
  - String vazia `""`: existe no destino; exibe alerta `[vazia]` e entra em *Apenas Pendentes* (no Foundry, `""` impede o fallback para o inglês).
  - Igual à base (`local_value == base_text`): entra em *Apenas Pendentes* com marcador discreto `= base` enquanto `unreviewed`; sai de Pendentes quando marcada como `reviewed`.
- **Categorias plurais CLDR:** sob prefixos plurais da base (`.zero`, `.one`, `.two`, `.few`, `.many`, `.other`), sufixos exigidos pelas regras de plural do idioma de destino (ex.: `.many` em `pt-BR`, `es`, `fr`) não são marcados como órfãos, e categorias exigidas que faltarem no destino aparecem como `missing` sugeridas (usando `.other` da base como referência).
- **Conflito estrutural base × destino (folha vs. objeto no mesmo caminho):** exibido como somente-leitura na célula afetada com alerta de **Conflito estrutural**, bloqueando escrita automática que causaria colisão no arquivo de destino.

### 5. Persistência (`.i18nproj`), Alteração Externa e Merge de 3 Vias

- **Esquema `.i18nproj` (`schema_version: 1`, gravado com `indent=2, ensure_ascii=False` + `os.replace`):**
  ```json
  {
    "schema_version": 1,
    "project_id": "uuid-v4",
    "package": {
      "manifest_type": "module | system",
      "package_id": "hearthbound",
      "package_root_rel": "../foundry-vtt-dev/Data/modules/hearthbound",
      "package_root_abs": "C:/Users/.../hearthbound",
      "base_lang": "en",
      "base_external_path": null,
      "target_langs": ["pt-BR", "es", "eo"],
      "files": [{"lang": "pt-BR", "path": "lang/pt-BR.json", "conditional": null, "enabled": true}],
      "missing_target_mapping": {"pt-BR": "lang/pt-BR.json"}
    },
    "snapshots": {
      "files": {
        "lang/en.json": {"sha256": "...", "entries": {"KEY": "val"}},
        "lang/pt-BR.json": {"sha256": "...", "entries": {"KEY": "val"}}
      }
    },
    "drafts": {
      "edits": {"pt-BR": {"KEY": "novo valor"}},
      "deletions": {"pt-BR": ["ORPHAN.Key"]}
    },
    "review_state": {
      "pt-BR": {"KEY": {"status": "reviewed", "previous_base": null}}
    },
    "ignored_warnings": [
      {"key_path": "KEY", "lang": "pt-BR", "rule_id": "placeholder_count", "reason": "", "value_hash": "..."}
    ],
    "custom_enrichers": [],
    "project_glossary": []
  }
  ```
- **Portabilidade e salvamento:** tenta resolver `package_root_rel` primeiro e `package_root_abs` como fallback; se ambos falharem, abre diálogo *"Relocalizar pasta do pacote"*. Salvamento é manual (`Ctrl+S` + confirmação ao fechar se houver mudanças), acompanhado de rascunho automático de crash recovery em `%APPDATA%\i18n-reviewer\recovery\<project_id>.json` (removido ao salvar ou fechar normalmente). Versões antigas do esquema migram com backup prévio; versões futuras recusam abrir pedindo atualização do app.
- **Detecção de alteração externa e Merge 3-vias:**
  - Verifica SHA-256 dos arquivos ao abrir o `.i18nproj`, imediatamente antes de **Enviar para Produção**, e passivamente via `QFileSystemWatcher` / foco da janela (exibindo faixa com botão *"Sincronizar agora"*). Arquivos ausentes ou com JSON inválido no disco bloqueiam a sincronização/envio com erro explícito.
  - **Destinos (`snapshot × disco × rascunho_local`):**
    - Sem edição local (`dirty = False`): absorve o novo valor do disco; se o texto mudou e estava `reviewed`, volta para `unreviewed`.
    - Com edição local convergente (`rascunho_local == disco`): atualiza snapshot e limpa `dirty` sem conflito.
    - Com mudança divergente no disco e no rascunho local (incluindo chave removida no disco enquanto `dirty = True`): marca **conflito real** e abre diálogo comparando *Snapshot anterior × Disco atual × Minha edição* (resolução por chave ou em lote), bloqueando **Enviar para Produção** até resolver.
  - **Base (`en.json`):** quando o texto base de uma chave muda no disco, atualiza o snapshot da base; células de destino que estavam `reviewed` passam para `stale` e guardam o texto antigo em `previous_base` (exibindo *Antes × Agora* no Inspector até nova aprovação).

### 6. Extração e Validação de Placeholders, Enrichers e HTML

- **Ordem fixa de extração em cascata (para evitar colisão entre `{rótulo}` de enricher e `{placeholder}`):**
  1. `{{handlebars}}` (`\{\{\{?[^{}]*\}?\}\}`)
  2. Enrichers conhecidos (lista embutida de core v14: `@UUID` e links de documento, `@Embed`, inline rolls `[[...]]`; `dnd5e`: `[[/check|save|attack|damage|heal|item|award|...]]`, `[[lookup|language ...]]`, `&Reference[...]`; `pf2e`: `@Check`, `@Damage`, `@Template`, `@Localize`, `[[/act ...]]`) + regras extras configuradas em `custom_enrichers` no `.i18nproj` + heurística genérica (`@Nome[...](?:\{[^}]+\})?`, `&Nome[...](?:\{[^}]+\})?`, `\[\[/[a-zA-Z]+[^\]]*\]\](?:\{[^}]+\})?`)
  3. URLs (`https?://[^\s<]+`)
  4. Tags HTML/XML (incluindo tags semânticas do `pf2e` como `<actor>`, `<dc>`) e entidades HTML
  5. Placeholders simples `{nome}` (`\{([^{}]+)\}`) no texto restante e dentro dos segmentos traduzíveis.
- **Partes técnicas vs. traduzíveis:** tipo, alvo/UUID, `#hash`, comandos, fórmulas e parâmetros técnicos de enrichers devem permanecer idênticos à base; `{rótulo}`, `#flavor` em rolagens, `name:` em `@Check` do `pf2e` e `caption="..."` em `@Embed` são traduzíveis.
- **Severidades:**
  - **Erro crítico** *(bloqueia Enviar para Produção para o arquivo, salvo exceção explícita em `ignored_warnings`)*: conjunto de nomes únicos de placeholders `{nome}` divergente da base (ordem é livre), `{{handlebars}}` alterado/ausente, ou parte técnica de enricher alterada/ausente.
  - **Aviso** *(alerta visual + confirmação ao Enviar para Produção)*: quantidade diferente de repetições do mesmo `{nome}` quando os nomes únicos batem, tags/atributos técnicos HTML/XML divergentes ou desbalanceados, ou URL omitida/alterada.
  - **Aviso informativo na base** *(nunca bloqueia)*: defeito detectado na própria string de referência (ex.: colisão `{rótulo}` de enricher na mesma string que `{placeholder}`).

### 7. Glossário e Memória de Tradução

- **Dois níveis com precedência:** glossário **Global** (`%APPDATA%\i18n-reviewer\glossary.json`) + glossário **Por Projeto** (`project_glossary` no `.i18nproj`), onde termos do projeto sobrescrevem termos iguais do global.
- **Estrutura da entrada:** `term`, `source_variants` (opcional, para plurais na fonte), `case_sensitive` (padrão `false`), `do_not_translate` (padrão `false`, exige manter o termo original idêntico), `notes` (opcional) e `translations: {lang: [preferida, ...variantes_aceitas]}` (a 1ª é a preferida para inserção; todas as variantes/flexões listadas satisfazem o linter).
- **Linter e interações:** mascara antes todos os spans técnicos do extrator (item 6); casa termos na base por limite de palavra (`\b`) onde o termo mais longo vence sobreposições; não alerta em células `missing`/vazias; emite sempre **aviso** não-bloqueante (ignorável via `ignored_warnings`). `Ctrl+Space` no editor abre popup com os termos da linha e insere a tradução no cursor. Suporta importação/exportação em `glossary.json` e `CSV`.

### 8. Verificação Ortográfica (`SpellService`)

- **Motor:** `pyenchant` (provider `hunspell`) atrás de uma interface própria (`check(lang, word)`, `suggest(lang, word)`, `add_personal(lang, word)`).
- **Dicionários:** empacota `pt_BR` (VERO), `es_ES`, `fr_FR` (Grammalecte) e `de_DE` (`de_DE_frami`) como arquivos `.aff/.dic` separados (junto de `en_US`) e descobre automaticamente qualquer `.aff/.dic` colocado pelo usuário em `%APPDATA%\i18n-reviewer\enchant\hunspell\`.
- **Mapeamento e fallback:** mapeia tags do Foundry para códigos do Enchant (`pt-BR` → `pt_BR`, `es` → `es_ES`, `fr` → `fr_FR`, `de` → `de_DE`, com fallback por prefixo). Idiomas sem dicionário instalado (ex.: `eo`) ficam com o corretor desligado na coluna e aviso discreto apontando para a pasta `hunspell\` do usuário.
- **Dicionário pessoal e mascaramento:** PWL global por idioma em `ENCHANT_CONFIG_DIR`. Ignora automaticamente spans técnicos (item 6), termos do glossário ativo (originais e traduções), palavras em MAIÚSCULAS, números/dados (`1d20`), tokens com ≤ 2 letras (`h`, `m`, `ft`) e palavras idênticas à string base; preserva hífens e apóstrofos ao consultar o Hunspell.
- **Desempenho e contorno Windows não-ASCII:** roda `check()` em tempo real ao editar e em lote assíncrono (`QThreadPool`) para o projeto, calculando `suggest()` **somente sob demanda** no menu de contexto. Se o caminho dos dicionários ou `ENCHANT_CONFIG_DIR` contiver caracteres não-ASCII, converte via `GetShortPathNameW` (caminho curto 8.3) ou usa pasta ASCII configurada em `settings.json`, validando sempre a abertura do dicionário com uma **palavra-sentinela** para nunca falhar silenciosamente.

### 9. Pipeline Pré-Produção, Backups e Escrita Atômica

- **Localização e retenção de backups:** armazenados em `%APPDATA%\i18n-reviewer\backups\<project_id>\` (fora da pasta do módulo). Cada envio ou pré-restauração gera um lote `YYYY-MM-DD_HHMMSS_NNN/` com `manifest.json` (data/hora, tipo `publish` | `pre-restore`, caminhos e hashes SHA-256) e cópia `.bak` apenas dos arquivos modificados naquele lote. Mantém por padrão os últimos **30 lotes** por projeto (configurável em `settings.json`) + exclusão manual.
- **Sequência exata de Enviar para Produção:**
  1. Diálogo pré-envio com checkboxes por arquivo modificado (permite publicar apenas os idiomas escolhidos).
  2. Verificação SHA-256 no disco dos arquivos marcados e da base (se mudou → aborta e abre merge 3-vias).
  3. Verificação de bloqueios estruturais/críticos nos arquivos marcados (JSON inválido, folha-antes-de-ramo, conflito estrutural, erro crítico de placeholder/`{{hbs}}`/enricher não ignorado).
  4. Confirmação única agrupando todos os avisos não-bloqueantes dos arquivos marcados (HTML/URL, glossário, duplicadas, células `dirty` ainda `unreviewed`/`stale` e órfãs a remover).
  5. Geração do payload em memória por spans + validação estrita `json.loads` + simulação do `expandObject` do Foundry + conferência exata do diff planejado.
  6. Criação do lote de backup `publish` em `%APPDATA%`.
  7. Gravação de `<arquivo>.tmp` no mesmo diretório do destino seguida de `os.replace` com até **5 tentativas** em backoff curto (`100–500 ms`) para contornar locks transitórios do OneDrive/antivírus.
- **Falha parcial e Restauração:** se algum arquivo falhar após os retries, interrompe os restantes e oferece reverter imediatamente os arquivos já gravados usando o lote de backup recém-criado ou mantê-los. Na ação **Restaurar Backup** (por lote inteiro ou arquivo individual), valida o `.bak`, cria antes um lote automático `pre-restore` do estado atual em produção, aplica via `.tmp` + `os.replace` e pergunta se o usuário deseja sincronizar mantendo rascunhos locais (merge 3-vias) ou descartar também os rascunhos locais dos arquivos restaurados.

### 10. UI/UX, Escala e Build/Distribuição Windows

- **Tabela e Inspector:** linhas limitadas a ~5 linhas (~110 px) na tabela com margem superior reservada (~18 px) para o badge não cobrir o texto; edição inline (`F2`) via `QPlainTextEdit` + Editor Expandido (`Shift+F2`) lado a lado; menu de contexto em 4 seções fixas (Revisão/Célula → Placeholders → Glossário → Ortografia); `QUndoStack` (`Ctrl+Z`/`Ctrl+Y`); atalhos `Ctrl+Enter`, `Ctrl+Down`, `Ctrl+Space`, `Ctrl+F` (busca com debounce de 150 ms) e cache de altura de linha por largura de coluna.
- **Build `spec/build.spec` (`--onedir --windowed`):**
  - Exclui módulos Qt não usados (`QtWebEngine*`, `QtQml`, `QtQuick`, `Qt3D*`, `QtMultimedia*`, `QtPdf*`).
  - Enxuga `enchant`: mantém apenas `libenchant-2`, `enchant_hunspell` e suas 8 DLLs dependentes (removendo `nuspell`/ICU e as ~38 DLLs MSYS2/GPLv3 não usadas, reduzindo a parcela do enchant de ~120 MB para ~39 MB) e empacota os dicionários `en_US`, `pt_BR`, `es_ES`, `fr_FR` e `de_DE`.
  - Define `module_collection_mode={'enchant': 'py'}` e inclui a pasta `licenses/` com todos os avisos e links para as fontes dos dicionários e bibliotecas.
  - Entrega em `.zip` portátil da pasta `dist/i18n-reviewer/` (com script Inno Setup opcional no repositório).

---

## Testing Decisions

- **Princípio de teste:** testar o comportamento externo e os contratos observáveis nas fronteiras dos serviços e da UI (bytes gravados no disco, estados resultantes, alertas emitidos e interações de usuário), nunca detalhes internos privados.
- **Ferramental:** `pytest` + `pytest-qt` com fixtures autocontidas em `tests/fixtures/` dentro do repositório (para rodar em qualquer máquina/CI sem depender de caminhos externos) + suíte de integração opcional sobre uma **cópia temporária** do módulo de referência `hearthbound` (pulada automaticamente via `skipif` quando o caminho local não existir; nunca toca no diretório original do `hearthbound`).
- **Fronteiras (seams) testadas:**
  1. **`json_handler` (Leitura, Diagnóstico e Writer por Spans):**
     - Round-trip byte a byte sem edições em todos os estilos (canônico, não-canônico com linhas em branco/objetos inline/`"k" : "v"`, misto plano+aninhado, `\uXXXX`, BOM, `CRLF`/`LF`, sem newline final).
     - Edições pontuais alterando exclusivamente as linhas tocadas no diff.
     - Inserção de chaves novas na posição relativa da base seguindo o estilo do destino (plano, aninhado, misto) e remoção de órfãs podando objetos pai vazios.
     - Detecção de chaves duplicadas (edição na última ocorrência), folhas não-string e bloqueio em folha-antes-de-ramo / JSON inválido.
  2. **`project_manager` + `backup_manager` (Ciclo de Projeto, Merge 3-Vias e Pipeline de Produção):**
     - Descoberta por `module.json`/`system.json`, múltiplos arquivos por `lang`, portabilidade de caminhos e crash recovery.
     - Transições de `review_status` (`unreviewed`, `reviewed`, `stale` com `previous_base`) e `dirty` derivado; categorias plurais CLDR (`.many`) e conflitos estruturais.
     - Merge de 3 vias por chave (`snapshot × disco × rascunho`) sem conflito e com conflito real.
     - Pipeline pré-produção completo: seleção parcial de idiomas, bloqueios críticos, simulação `expandObject`, criação de lote `.bak`, escrita atômica com simulação de `PermissionError` (retries + falha parcial + rollback) e restauração com geração automática de `pre-restore`.
  3. **`validation_service`, `glossary_service` e `spell_service`:**
     - Extração em cascata (core + `dnd5e` + `pf2e` + genéricos + regras customizadas) sem colisão entre `{rótulo}` de enricher e `{placeholder}`; exceções em `ignored_warnings` invalidando ao mudar o texto.
     - Precedência Projeto > Global no glossário, import/export CSV, termo mais longo vencendo sobreposição e mascaramento de spans técnicos.
     - `SpellService` com `pt_BR`, `es_ES`, `fr_FR`, `de_DE`, PWL global, filtro de tokens ignorados, contorno de caminho com caracteres não-ASCII (8.3 / fallback ASCII) e falha controlada se a palavra-sentinela falhar.
  4. **UI (`pytest-qt`) e Escala:**
     - Filtros da toolbar, busca com debounce, `QUndoStack` (`Ctrl+Z`/`Ctrl+Y`), fluxo `Ctrl+Enter` (revisar + próxima pendente), diálogo de resolução de conflito e teste de escala/responsividade com fixture sintética de **10 000 chaves**.
  5. **Smoke test do executável congelado (`--self-test`):**
     - Modo `--self-test` no `app/main.py` executado após `pyinstaller spec/build.spec`, verificando que o `.exe` congelado inicializa o Qt em modo offscreen e carrega os 4 dicionários Hunspell passando na palavra-sentinela (`exit 0`).

---

## Out of Scope

- **Traduções de compêndio do Babele (`lang/*/compendium/*.json`):** arquivos JSON que não são declarados no array `languages[]` do manifest seguem estrutura própria do Babele e não fazem parte deste projeto.
- **Edição de arquivos de idioma remotos (`path` HTTP/HTTPS em `languages[]`):** são apenas identificados e listados como não-editáveis na abertura do pacote.
- **Formatos não-JSON (`.po`, `.yaml`, `.ts`) e tradução automática via API/LLM:** o foco exclusivo é revisão humana e escrita segura para arquivos JSON de localização do ecossistema Foundry VTT.
- **Reestruturação/formatação automática de JSONs malformados:** a ferramenta diagnostica erros e bloqueia publicações perigosas, mas nunca reescreve a estrutura do arquivo inteiro por conta própria.

---

## Further Notes

- **Referência completa de pesquisa e decisões:**
  - Mapa Wayfinder: [`.wayfinder/map.md`](../.wayfinder/map.md)
  - Pesquisas de base: [001 — Formato Foundry](../.wayfinder/research/001-formato-lang-files-foundry.md), [002 — Round-trip JSON](../.wayfinder/research/002-round-trip-json-python.md), [003 — Sintaxes Embutidas](../.wayfinder/research/003-sintaxes-embutidas-foundry.md), [004 — Corretor Ortográfico](../.wayfinder/research/004-pyspellchecker-idiomas.md), [005 — Stack Python 3.14](../.wayfinder/research/005-compatibilidade-stack-python.md), [017 — Empacotamento Hunspell](../.wayfinder/research/017-empacotamento-dicionarios-hunspell.md).
  - Protótipo descartável da UI (Ticket 014): validado em PySide6 (`proto_014.py` / `proto_014_preview.png`).
- **Módulo de referência local (somente leitura):** `C:\Users\ajtop\OneDrive\Documents\foundry-vtt-dev\Data\modules\hearthbound` (Foundry v14, `en`, `pt-BR`, `es`, `eo`, 1314 chaves por arquivo, 186 placeholders).

