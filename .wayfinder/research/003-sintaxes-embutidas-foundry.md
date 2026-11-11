# Achados: sintaxes embutidas em strings de localização do Foundry

> Ticket: [Sintaxes embutidas em strings de localização do Foundry](../tickets/003-sintaxes-embutidas-foundry.md)
> Data: 2026-11-11 · Autor: research-agent

## Fontes e versões

A pesquisa usou **código-fonte primário instalado localmente** (somente leitura), fixado em versão, mais documentação oficial publicada:

| Fonte | Versão | Onde |
|---|---|---|
| Foundry VTT core (cliente) | **v14 Stable, build 370** (`resources/app/package.json` → `release.generation: 14, build: 370`) | `C:\Program Files\Foundry Virtual Tabletop\resources\app\` |
| Sistema dnd5e | 6.0.6 (verified 14) | `foundry-vtt-dev\Data\systems\dnd5e\dnd5e.mjs` |
| Sistema pf2e | 8.7.0 (verified 14.370) | `foundry-vtt-dev\Data\systems\pf2e\pf2e.mjs` |
| Outros sistemas p/ amostragem | daggerheart 2.12.7, crucible 0.11.3, tormenta20 1.6.7, sf2e 1.7.0 | `foundry-vtt-dev\Data\systems\*` |
| Docs da API (online) | página atual de `foundry.helpers.Localization` | https://foundryvtt.com/api/classes/foundry.helpers.Localization.html |
| Wiki do dnd5e (online) | página "Enrichers" | https://github.com/foundryvtt/dnd5e/wiki/Enrichers |

Abreviações de citação usadas abaixo:
- **[L]** = [localization.mjs](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/client/helpers/localization.mjs)
- **[TE]** = [text-editor.mjs](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/client/applications/ux/text-editor.mjs)
- **[HB]** = [handlebars.mjs](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/client/applications/handlebars.mjs)
- **[CHAT]** = [chat.mjs](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/client/applications/sidebar/tabs/chat.mjs)
- **[CFG]** = [config.mjs](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/client/config.mjs)
- **[CONST]** = [constants.mjs](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/common/constants.mjs)
- **[5E]** = [dnd5e.mjs](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/systems/dnd5e/dnd5e.mjs)
- **[PF2]** = [pf2e.mjs](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/systems/pf2e/pf2e.mjs)

Contagens de ocorrência vêm de varredura dos `lang/*.json` instalados (scripts em `brain/.../scratch/scan.py`, `scan2.py`, `hearth.py`; os números de pf2e/sf2e são duplicados porque o sf2e reaproveita os arquivos do pf2e).

> [!NOTE]
> A regra do usuário pede Context7 para docs de bibliotecas; o servidor MCP `context7` não expõe ferramentas nesta sessão. Usei o código-fonte instalado (mais primário que a doc) e as páginas oficiais acima.

---

## 1. Como um valor de localização é processado (pipeline)

1. **Carregamento.** Cada arquivo `lang` passa por `foundry.utils.expandObject` (chaves com ponto e objetos aninhados são equivalentes) e é mesclado em ordem core → sistema → módulos → mundo com `mergeObject` [L:314-319, 363-368]. Se o idioma não é `en`, o inglês é carregado como `_fallback` [L:236].
2. **`localize(stringId, data)`**: busca a chave; se não for string, tenta o `_fallback` (inglês); se também falhar, **retorna o próprio stringId** [L:435-443]. Se `data` for passado, aplica `translation.replace(/{[^}]+}/g, k => data[k.slice(1, -1)])` [L:400, 444].
3. **v14: `format` é um alias de `localize`.** `Object.defineProperties(Localization.prototype, {format: {value: Localization.prototype.localize}})` [L:481]. A doc online atual descreve só `localize(stringId, data?)` com interpolação ("Variables can be included in the template enclosed in curly braces") — https://foundryvtt.com/api/classes/foundry.helpers.Localization.html. Também existe o global `_loc(...)` usado pelo próprio core (ex.: [TE:510, 556]).
4. **Handlebars `{{localize "KEY" a=1}}`** chama `_loc(value, hash)` e devolve string comum [HB:265-269] → com `{{ }}` o Handlebars **escapa** HTML (`&`→`&amp;` etc., [handlebars.js:388-397](file:///C:/Program%20Files/Foundry%20Virtual%20Tabletop/resources/app/node_modules/handlebars/dist/handlebars.js#L388-L397)); só com `{{{ }}}`/`innerHTML` o HTML do valor é renderizado.
5. **Enriquecimento (opcional, decidido pelo código chamador).** `TextEditor.enrichHTML(content)` faz `innerHTML` do texto, remove `section.secret` não revelados e aplica, nesta ordem: content links → hyperlinks → inline rolls → embeds → enrichers customizados de `CONFIG.TextEditor.enrichers` [TE:123-163]. **As regex rodam somente sobre nós de texto** (TreeWalker `SHOW_TEXT`) [TE:390-395, 408-426]; atributos HTML não são enriquecidos, e um enricher partido por uma tag não casa.

> [!IMPORTANT]
> A ordem é **formatar primeiro, enriquecer depois**: o código típico é `enrichHTML(_loc("KEY", {data}))` (ex.: crucible, [crucible-compiled.mjs:8297](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/systems/crucible/crucible-compiled.mjs#L8297)). Logo, a regex de placeholder `{[^}]+}` **também atinge o `{label}` dos enrichers** quando há `data` (ver §2.1, "colisão").

Se um valor é ou não enriquecido/renderizado como HTML **não é visível no arquivo de idioma** — depende de cada chamada no código do pacote.

---

## 2. Sintaxes do core

### 2.1 Placeholders de formatação `{nome}`

- **Exemplo:** `"DND5E.ADVANCEMENT.AbilityScoreImprovement.PointsRemaining.one": "{points} Point Remaining"` (dnd5e en.json).
- **Gramática exata do core:** `/{[^}]+}/g`; o nome é tudo entre as chaves (`k.slice(1,-1)`) [L:400, 444]. Qualquer caractere exceto `}` é aceito — ex. real com hífen: `"PF2E.EffectPanel.AppliedBy": "Applied by: {condition-list}"`.
- **Regex proposto (Python):** `\{([^{}]+)\}` aplicado **depois** de remover os spans de enrichers (§2.3–2.6, §3); manter também a variante exata do core `\{[^}]+\}` para simular o comportamento real.
- **Deve ficar idêntico:** o nome dentro das chaves. Nome traduzido/alterado → `data[k]` é `undefined` e o JS insere o texto literal **`"undefined"`** (comportamento de `String.prototype.replace` com callback que retorna `undefined`; reproduzido com Node 24 sobre a mesma expressão de [L:444]).
- **Traduzível:** todo o texto ao redor; a **ordem** dos placeholders pode mudar (substituição é por nome).
- **Armadilhas verificadas:**
  - **Sem `data`, nada é substituído** [L:444] — o mesmo valor pode ser usado com e sem formatação; o arquivo não diz qual.
  - **Chaves literais em prosa viram placeholder** se houver `data`: ex. real `"Erhält { weather, previousWeather, zoneId } als Kontext"` (chave `CALENDARIA.Weather.Picker.FxMacroHint` em um lang do módulo 3ds-atlas) seria trocado por `undefined` se formatado.
  - **Colisão com rótulos de enrichers:** em `crucible` `ACTION.DelayHint` = `"... 1 and {maximum} ... See @UUID[Compendium...]{Initiative and Turn Order} ..."` é chamado como `enrichHTML(_loc("ACTION.DelayHint", {maximum}))` [crucible-compiled.mjs:8297]. Simulando [L:444]: `{Initiative and Turn Order}` → `undefined`, e o link sai sem o rótulo seguido do texto "undefined". O inverso é usado de propósito pelo pf2e: `@Check[perception|dc:{societyDC}|showDC:gm]` (en.json, `PF2E.Actions.CreateForgery.ForgedDocument.SuccessGmNote`) — o placeholder é preenchido antes do enricher.
  - **`{{x}}` não é sintaxe do Localization**, mas a regex do core casa `{{x}` dentro de `{{x}}` (ver §2.8).
  - **`{}` vazio** não casa (`[^}]+` exige ≥1 caractere).
- **Frequência local:** ~10 mil ocorrências; todas as amostras de core/dnd5e/pf2e/hearthbound são identificadores JS simples (`[A-Za-z_$][\w$]*`), com raras exceções (`{condition-list}`).

### 2.2 Pluralização (não é sintaxe dentro do valor)

- O core não tem sintaxe ICU/plural no valor; oferece `game.i18n.pluralRules` = `new Intl.PluralRules(this.lang)` [L:59-70]. Os sistemas montam **a chave** com o sufixo da categoria: `` `DND5E.ADVANCEMENT.AbilityScoreImprovement.PointsRemaining.${pluralRules.select(n)}` `` [5E:46555]; dnd5e en.json tem 168 chaves terminadas em `.one/.other/...`.
- **Fato relevante p/ tradução:** as categorias variam por idioma (Node 24 / ICU 78.3): `en` e `de` = `one, other`; `pt-BR`, `es`, `fr` = `one, many, other`. Em `pt-BR`/`fr`, `select(0)` = `one`; `select(1000000)` = `many` em pt-BR/es/fr. Se o tradutor não criar `.many`, `localize` cai no `_fallback` inglês, que também não tem `.many` → **retorna a própria chave** [L:436-443].

### 2.3 Content links `@UUID[...]{rótulo}` e formas legadas

- **Exemplo:** `@UUID[Compendium.pf2e.equipment-srd.Item.s1vB3HdXjMigYAnY]{Healer's Toolkit}` (pf2e en.json).
- **Regex do core:** `` new RegExp(`@(${documentTypes.join("|")})\\[([^#\\]]+)(?:#([^\\]]+))?](?:{([^}]+)})?`, "g") `` com `documentTypes = DOCUMENT_LINK_TYPES + ["Compendium", "UUID"]` [TE:202-205]; `DOCUMENT_LINK_TYPES = ["Actor","Cards","Item","Scene","JournalEntry","Macro","RollTable","PlaylistSound"]` [CONST:515-516].
- **Regex proposto (Python):** `@(UUID|Compendium|Actor|Cards|Item|Scene|JournalEntry|Macro|RollTable|PlaylistSound)\[([^#\]]+)(?:#([^\]]+))?\](?:\{([^}]+)\})?`
- **Idêntico:** o tipo (`UUID` etc.), o alvo (UUID/id/nome) e o `#hash` — o alvo vai para `fromUuid`/`collection.get|getName` [TE:474-478, 628-686]; alterado → link "broken".
- **Traduzível:** o `{rótulo}` (vira `name` do anchor [TE:462-470, 481]). Ele é **opcional**: sem rótulo usa-se o nome do documento (geralmente no idioma original do compêndio) [TE:482, 641, 673]. O rótulo **não pode conter `}`** (termina o grupo) e não pode conter tags HTML (partiria o nó de texto, §1.5).
- **Evidência de tradução real:** crucible `pl.json` mantém o UUID e traduz o rótulo (`{Inicjatywa i kolejność tur}`); `de.json` simplesmente **omite a frase com o link** — enricher ausente na tradução é um caso real.
- **Frequência local:** `@UUID` 964 (pf2e), 2 (crucible); `@Compendium`/legados: 0.

### 2.4 Embeds `@Embed[config]{rótulo}`

- **Regex do core:** `/@Embed\[(?<config>[^\]]+)](?:{(?<label>[^}]+)})?/gi` [TE:217-221].
- **Gramática do `config`:** tokens `(?:[^\s"]+|"[^"]*")+`, cada um `chave=valor` ou valor solto; o primeiro valor que parece UUID vira `uuid`; flags `inline`, `cite`, `caption`, `captionPosition`, `classes` [TE:563-616, 42-56].
- **Regex proposto:** `@Embed\[([^\]]+)\](?:\{([^}]+)\})?` (case-insensitive).
- **Idêntico:** UUID, nomes de chaves e valores booleanos/numéricos/flags.
- **Traduzível:** o `{rótulo}` (usado como legenda) e, por inferência do parser, o **valor textual entre aspas** de `caption="..."` (exemplo da própria doc: `caption="Example Caption"` [TE:574-578]). Profundidade máx. de embed = 5 [CONST:2004].
- **Frequência local:** 0 ocorrências em lang files.

### 2.5 Inline rolls `[[...]]`

- **Regex do core:** `/\[\[(\/[a-zA-Z]+\s)?(.*?)(]{2,3})(?:{([^}]+)})?/gi` [TE:247-251]. `]]]` significa fórmula terminando em `]` [TE:723].
- **Formas:**
  - Sem comando (`[[1d20+5]]`) → avaliado na hora; `{rótulo}` opcional [TE:726-733].
  - Com comando de rolagem: `/r` `/roll`, `/gmr` `/gmroll`, `/br` `/blindroll`, `/sr` `/selfroll`, `/pr` `/publicroll` [CHAT:95-99]; gramática do resto: `([^#]+)(?:#(.*))?` = **fórmula `#` flavor** [CHAT:78]. Comandos não-rolagem retornam `null` (não enriquecem) [TE:744-746].
- **Exemplos reais (pf2e en.json):** `[[/r @abilities.str.mod # Damage: Arcane Slam]]{Strength modifier}`; `[[/r (@actor.level)[fire] #Tamper Backfire]]{fire damage equal to your level}`.
- **Regex proposto:** `\[\[(/[a-zA-Z]+\s)?(.*?)(\]{2,3})(?:\{([^}]+)\})?` e, para comandos de rolagem, subdividir o miolo em `^([^#]+)(?:#(.*))?$`.
- **Idêntico:** comando, fórmula (dados, `@caminhos.de.dados`, `[tipo]` de dano).
- **Traduzível:** o `{rótulo}` (texto do anchor/flavor [TE:757, 763]) e o **flavor após `#`** (vai para `dataset.flavor` [TE:751-757]).
- **Atenção:** sistemas registram **seus próprios** `[[/comando ...]]` (dnd5e, pf2e `/act`, daggerheart `/dr` `/fr`, crucible `/award` etc. — §3). A regex do core também casa esses textos; o core retorna `null` para eles e o enricher do sistema assume.

### 2.6 Hyperlinks

- **Regex do core:** `/(https?:\/\/)(www\.)?([^\s<]+)/gi` [TE:232-235]. **Idêntico:** a URL inteira (vira `href` e texto) [TE:697-705].

### 2.7 Enrichers customizados (mecanismo)

- `CONFIG.TextEditor.enrichers: TextEditorEnricherConfig[]` (padrão `[]`); cada item tem `pattern` (**RegExp global**), `enricher`, `id?`, `replaceParent?`, `onRender?` [CFG:2808-2853]. Aplicados em ordem de registro após os do core [TE:144-148, 264-280].
- **Consequência:** o conjunto de sintaxes **depende do sistema/módulos ativos** e pode ser substituído (o tormenta20 faz `CONFIG.TextEditor.enrichers = [applyEffect]`, [tormenta20.mjs:21722](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/systems/tormenta20/tormenta20.mjs#L21722)). Não há lista fechada; só dá para cobrir os sistemas conhecidos + uma heurística genérica (`@Palavra[...]`, `&Palavra[...]`, `[[/palavra ...]]`).

### 2.8 `{{handlebars}}` dentro de valores

- O `Localization` **não** processa `{{...}}` [L:400-444]. Templates `.hbs` ficam em arquivos próprios; em lang files só aparecem quando um módulo faz a própria interpolação. Ex. real: `"Supports {{path}} placeholders, e.g. {{token.name}}."` (3ds-atlas en.json, 34 ocorrências).
- **Idêntico:** o conteúdo inteiro `{{...}}`. Se esse valor for formatado com `data`, a regex do core casa `{{path}` e insere `undefined` (simulação de [L:444]).
- **Regex proposto:** `\{\{\{?[^{}]*\}?\}\}` (extrair **antes** dos placeholders simples).

### 2.9 HTML embutido e entidades

- **Exemplos reais:** `"<actor>{actor}</actor> takes {hpDamage} damage."` (pf2e); `"Use the <i class=\"fa-solid fa-plus\"></i> button above..."` (dnd5e); `<a data-action="openQueue" class="hm-welcome-link">Pending Approvals Queue</a>` (3ds-atlas); `<span class="reference">Click + Drag</span>` (core en.json).
- **Tags mais comuns** nos lang locais: `strong` 1738, `p` 1307, `hr` 113, `a` 107, `em`, `li`, `span`, `br`, `i`, `code`… e **tags não-HTML do pf2e**: `actor`, `dc`, `opposer`, `rarity`, `value`, `adjusted`… O pf2e converte nós XML específicos (`querySelector(t)`) em `<span>` [PF2:18768-18774] — o nome da tag é sintaxe.
- **Regex proposto (tags):** `</?([A-Za-z][\w-]*)(\s[^<>]*)?/?>`; **entidades:** `&(?:[A-Za-z][A-Za-z0-9]*|#\d+|#x[0-9A-Fa-f]+);`.
- **Idêntico:** nomes de tags, estrutura (abre/fecha), atributos técnicos (`class`, `data-*`, `href`, ícones `fa-*`).
- **Traduzível:** o texto entre as tags; por inferência, atributos de texto visível (`title`, `aria-label`, `data-tooltip`) — não houve exemplo no corpus local.
- **Renderização depende do uso:** com `{{localize}}` o HTML é escapado e aparece literalmente [HB:265-269; handlebars.js:388-397]; só vira HTML via `{{{ }}}`, `innerHTML` ou `enrichHTML` (que faz `innerHTML` [TE:129-130]). O mesmo vale para entidades (`&times;` crucible, `&sol;` dnd5e): em contexto HTML equivalem ao caractere Unicode; em contexto escapado aparecem como texto `&times;`.
- **Enrichers × tags:** como a regex roda por nó de texto [TE:390-426], inserir tag dentro de um enricher (ex. `{<em>rótulo</em>}`) quebra o casamento.

### 2.10 `%s`, `\n` e referências a outras chaves

- **`%s`/printf:** não existe no core (só `{nome}` [L:444]); 0 ocorrências nos lang locais. Seria texto literal.
- **`\n`:** é só um caractere do valor; o core não o trata. 631 ocorrências (pf2e as usa entre tags HTML, irrelevantes no render HTML). Em contexto não-HTML a exibição depende do CSS do chamador. Não quebra nada sozinho.
- **Chave dentro de valor:** `localize` não é recursivo [L:435-445]. Exceção de sistema: pf2e `@Localize[KEY]` (§3.2).
- **Formato de chave válido (para debug):** `/^[\x21-\x2D\x2F-\x7E]+(?:\.[\x21-\x2D\x2F-\x7E]+)+$/` [L:47].

---

## 3. Enrichers de sistemas

### 3.1 dnd5e 6.0.6 [5E:31943-31971]

Registrados em `CONFIG.TextEditor.enrichers` (regex literais do código):

| id | pattern |
|---|---|
| `dnd5e-enricher` | `` \[\[/(?<type>attack\|award\|check\|concentration\|damage\|heal\|healing\|save\|skill\|tool\|item)(?<config> .*?)?]](?!])(?:{(?<label>[^}]+)})? `` (gi) |
| `dnd5e-lookup` | `\[\[(?<type>language\|lookup) (?<config>[^\]]+)]](?:{(?<label>[^}]+)})?` (gi) |
| `dnd5e-reference` | `&(?<type>Reference)\[(?<config>[^\]]+)](?:{(?<label>[^}]+)})?` (gi) |

- **Gramática do `config`:** tokens separados por espaço, `chave=valor` ou valor solto, aspas permitidas; `damage/heal` aceitam várias configs separadas por `&` [5E:32044-32057].
- **Exemplos (doc do código e wiki):** `[[/check ability=str skill=dec/per dc=15]]`, `[[/check strength deception persuasion 15]]` [5E:32401-32403]; `[[/check dex format=long]]` (https://github.com/foundryvtt/dnd5e/wiki/Enrichers); `[[lookup @name]]` [5E:33170-33171]; `&Reference[condition=unconscious]{Label}` [5E:33234-33235]; `&Reference[rule="Difficult Terrain"]` (wiki).
- **Idêntico:** tipo, todas as chaves e valores do config. Abilities/skills/tools são **chaves de `CONFIG.DND5E`** (`CONFIG.DND5E.skills[skill]`, `enrichmentLookup.abilities[...]`) [5E:32452-32468]; o `&Reference` faz `slugify` do valor e procura em `CONFIG.DND5E.ruleTypes` [5E:33251-33272]. Traduzir `&Reference[Perception]` → `&Reference[Percepção]` = regra não encontrada → enricher retorna `null` e o texto cru fica visível [5E:33269-33271].
  - Ex. real em módulo: `"Fast pace imposes disadvantage on &Reference[Perception] or &Reference[Survival] checks"` (3ds-atlas en.json) — aqui o valor é nome em inglês e **precisa ficar em inglês**.
  - Ressalva (inferência): `rule="Difficult Terrain"` é texto entre aspas, mas é chave de busca → idêntico.
- **Traduzível:** `{label}` (substitui o texto padrão [5E:33278]); no `lookup`, o `{...}` é **fallback** exibido quando o caminho não existe [5E:33184, 33207].

### 3.2 pf2e 8.7.0 [PF2:119288-119296, 18747-18767]

| pattern | Grupos |
|---|---|
| `/@(Check\|Localize\|Template)\[([^\]]+)\](?:{([^}]+)})?/g` | tipo, params, rótulo |
| `/@(Damage)\[((?:[^[\]]\|\[[^[\]]*\])*)\](?:{([^}]+)})?/g` | permite **um nível** de `[...]` aninhado na fórmula |
| `/\[\[\/(act)\s+(?<slug>[-a-z]+)(?:\s+(?<options>[^\]]+))?\]\](?:\{(?<label>[^}]+)\})?/g` | slug, opções, rótulo |

- **Params de `@Check`/`@Template`:** separados por `|`; cada um `chave:valor`; o primeiro sem `:` é `type` [PF2:18826-18832, 18891].
- **Exemplos reais (pf2e en.json/re-en.json):** `@Check[reflex|dc:30|basic|name:Explosive Ammunition|options:area-effect]`, `@Damage[10[bludgeoning]|options:fall-damage]`, `@Template[type:emanation|distance:10]`, `[[/act administer-first-aid variant=stabilize]]{Medicine}`, `@Localize[PF2E.PersistentDamage.Bleed1d4.success]`.
- **Idêntico:** tipos/slugs (`fortitude`, `reflex`, `perception`, skills, `emanation`, `burst`…), `dc`, fórmulas, tipos de dano, `options`, `traits`, `showDC`, slug de `/act` e suas opções; **a chave dentro de `@Localize[...]`** (é passada a `_loc`; se não resolver, erro "Failed to localize" e `null` [PF2:18775-18780]). O valor de `@Localize` é **enriquecido recursivamente** [PF2:18779].
- **Traduzível:** `{rótulo}` de `@Check` (passa por `_loc` [PF2:18945]), `@Damage`, `@Template` (substitui o rótulo gerado [PF2:18792-18796]) e `[[/act]]` [PF2:18865]; o param **`name:`** de `@Check` (texto exibido como flavor do repost; passa por `_loc` [PF2:18944, 18960]).
- **Tags XML do pf2e** (`<actor>`, `<dc>`…) — idênticas (§2.9).
- **Pré-processamento:** um valor que é só `<p>@Localize[KEY]</p>` é desembrulhado antes do enrich [PF2:18679].
- **Frequência local:** `@UUID` 964, `@Damage` 527, `@Check` 232, `@Template` 72, `@Localize` 1; `[[/act]]` 79, `[[/r]]` 41, `[[/gmr]]` 4.

### 3.3 Outros sistemas instalados (amostra, só patterns)

- **daggerheart 2.12.7:** `@Damage[...]{}`, `[[/dr ...]]{}`, `[[/fr ...]]{}`, `@Effect`, `@Template`, `@Lookup`, `@Resolve[...]{}`, `@EmbedTable[...]` ([daggerheart.js:45923-45951](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/systems/daggerheart/build/daggerheart.js#L45923-L45951)). Ex. real: `@Resolve[@item.tier + 1|sign]{Gain Weapon Tier + 1}`.
- **crucible 0.11.3:** `[[/award ...]]`, `[[/counterspell ...]]`, `[[/knowledge x]]`, `[[/language x]]`, `[[/skill ...]]`, `[[/talent x]]`, `@Condition[x]`, `@Action[...]`, `@Spell[...]` — **sem `{rótulo}`** nesses patterns ([crucible-compiled.mjs:17368-17431](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/systems/crucible/crucible-compiled.mjs#L17368-L17431)); também `@Rule[movement.freeMovement]` aparece no en.json.
- **tormenta20 1.6.7:** substitui a lista inteira de enrichers [tormenta20.mjs:21722].

---

## 4. Caso de referência: hearthbound (v14, somente leitura)

`module.json`: versão 0.9.1, `compatibility {minimum: 14, verified: 14.370}`, idiomas `en`, `pt-BR`, `es`, `eo` em `lang/*.json`.

- **Sintaxes presentes:** **apenas placeholders `{identificador}`**. Cada arquivo: 1314 chaves, 186 placeholders, 51 nomes distintos; **0** HTML, entidades, enrichers (`@X[`, `[[`, `&Reference`), `{{...}}`, `%s` ou `\n`; nenhum placeholder com nome não-identificador (varredura `hearth.py`).
- **Nomes mais usados:** `{count}` 32, `{dc}` 21, `{actor}` 17, `{day}` 12, `{name}` 8, `{total}` 8, `{days}` 6, `{unit}` 6, `{destination}` 5, `{phase}` 5… Ex.: `"RollBadge": "{total} vs DC {dc}"`, `"Option": "{name} — {perDay} {unit}/day ({perHour} {unit}/h)"` (placeholder repetido).
- **Consistência atual:** pt-BR, es e eo têm **o mesmo multiconjunto de placeholders que o en em todas as chaves**, e nenhuma chave faltando/sobrando.
- **Uso no código:** o módulo usa um wrapper próprio, [localization.mjs](file:///C:/Users/ajtop/OneDrive/Documents/foundry-vtt-dev/Data/modules/hearthbound/scripts/localization.mjs): `format(key, data)` → `game.i18n.format(key, data)` (alias de `localize` na v14 [L:481]); `localize(key, data)` só formata se `data` for objeto; registra helpers Handlebars `hbFormat`/`format`. Contagem: **151** chamadas `format("HEARTHBOUND...", {...})` em `scripts/`, 6 usos de helper com hash nos `.hbs`, 172 `{{localize ...}}`, **61 chaves dinâmicas** montadas com template literal (ex. `` `HEARTHBOUND.Journey.CampConsequences.Consequences.${def.key}.Title` ``). Exemplos: `format("HEARTHBOUND.Journey.Log.RollBadge", { total, dc }, ...)`, `format("HEARTHBOUND.Conditions.Exhaustion", { level })`.
- Logo, para o hearthbound, o risco real é **placeholder renomeado/removido/adicionado** → `"undefined"` ou dado ausente na UI.

---

## 5. Tabela-resumo

| Sintaxe | Regex de extração (proposta) | Idêntico à base | Traduzível |
|---|---|---|---|
| Placeholder | `\{([^{}]+)\}` (após remover enrichers/`{{}}`) | nome | texto ao redor; ordem |
| `{{hbs}}` | `\{\{\{?[^{}]*\}?\}\}` | tudo | — |
| `@UUID`/legados | §2.3 | tipo, alvo, `#hash` | `{rótulo}` |
| `@Embed` | `@Embed\[([^\]]+)\](?:\{([^}]+)\})?` | uuid, chaves, flags | `{rótulo}`, `caption="..."` |
| Inline roll | `\[\[(/[a-zA-Z]+\s)?(.*?)(\]{2,3})(?:\{([^}]+)\})?` | comando, fórmula | `#flavor`, `{rótulo}` |
| URL | `(https?://)(www\.)?([^\s<]+)` | tudo | — |
| dnd5e `[[/cmd]]`, `[[lookup]]`, `&Reference` | §3.1 | tipo, config inteiro | `{rótulo}`/fallback |
| pf2e `@Check/@Damage/@Template/@Localize`, `[[/act]]` | §3.2 | tipo, params, chave do `@Localize` | `{rótulo}`, `name:` do `@Check` |
| HTML | `</?([A-Za-z][\w-]*)(\s[^<>]*)?/?>` | tags, estrutura, atributos técnicos | texto entre tags; `title`/`aria-label` (inferência) |
| Entidade | `&(?:[A-Za-z][A-Za-z0-9]*\|#\d+\|#x[0-9A-Fa-f]+);` | depende do contexto | — |
| `\n` | literal | — (contagem informativa) | — |

---

## Implicações para o i18n Reviewer

*(Fatos e consequências técnicas; a severidade fica para o ticket de política.)*

1. **Ordem de extração importa.** Para evitar falsos positivos: `{{...}}` → enrichers (que têm `{rótulo}`) → URLs → tags/entidades → placeholders simples no que sobrar. A regex crua do core (`{[^}]+}`) contaria o `{rótulo}` de `@UUID` como placeholder.
2. **O núcleo checável com segurança é "token idêntico, texto livre":** multiconjunto de placeholders, a "parte técnica" de cada enricher (tipo + alvo/config/params) e o multiconjunto de tags HTML devem bater com a base; rótulos `{...}` de enrichers, `#flavor` de rolagens, `name:` do pf2e e texto entre tags são traduzíveis.
3. **Não dá para saber pelo arquivo** se um valor é formatado, enriquecido ou renderizado como HTML — depende do código do pacote. Comparar com a base é o proxy viável: se a base tem a sintaxe, a tradução deve ter a mesma parte técnica.
4. **O conjunto de enrichers depende do sistema** (`CONFIG.TextEditor.enrichers` é aberto e pode ser substituído). O app precisa de uma lista conhecida (core + dnd5e + pf2e, talvez outros) e de uma heurística genérica para `@Nome[...]`, `&Nome[...]` e `[[/nome ...]]`.
5. **Colisões reais a sinalizar mesmo na base:** chaves literais em prosa e `{rótulo}` de enricher em valores também formatados com `data` viram `"undefined"` (caso crucible `ACTION.DelayHint`). Não é erro do tradutor, mas o revisor pode encontrar isso.
6. **Valores de config "parecidos com texto" não são traduzíveis** (`&Reference[Perception]`, `rule="Difficult Terrain"`, slugs `/act`, tipos do `@Check`). Um corretor ortográfico/glossário deve **ignorar** os spans técnicos e checar só os rótulos.
7. **Pluralização é por chave, não por sintaxe:** pt-BR/es/fr têm a categoria `many` (e pt-BR/fr tratam 0 como `one`), que não existe em en. Uma checagem de "chaves extras em relação à base" pode marcar `.many` legítimas, e a falta de `.many` faz a UI mostrar a chave crua.
8. **Escrita segura:** o loader faz `expandObject` e mesclagem [L:314-319, 363-368], então chaves com ponto e aninhadas são equivalentes para o Foundry — isso importa para o writer que preserva estilo/ordem.
9. **Caso hearthbound:** só placeholders simples, hoje 100% consistentes nas 4 línguas; 61 chaves dinâmicas no código, o que limita qualquer análise de "chave não usada" por busca estática.
