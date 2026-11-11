# Formato real dos arquivos de idioma e do manifest no Foundry

> Achados do ticket [Formato real dos arquivos de idioma e do manifest no Foundry](../tickets/001-formato-lang-files-foundry.md).
> Pesquisa feita em 2026-11-11.

## Fontes e método

| Rótulo | Fonte | Observação |
|---|---|---|
| **[DOC]** | [Languages and Localization](https://foundryvtt.com/article/localization/) — artigo oficial | Documentação de usuário/desenvolvedor. |
| **[API11] [API12] [API13]** | API docs oficiais: [v11](https://foundryvtt.com/api/v11/classes/client.Localization.html), [v12](https://foundryvtt.com/api/v12/classes/client.Localization.html), [v13](https://foundryvtt.com/api/v13/classes/foundry.helpers.Localization.html) | Assinaturas e lista de métodos da classe `Localization`. |
| **[CORE-L]** | `resources/app/client/helpers/localization.mjs` da instalação local do Foundry **v14 Stable build 370** (`C:\Program Files\Foundry Virtual Tabletop`) | Código-fonte real do core (lido em modo somente leitura). |
| **[CORE-H]** | `resources/app/common/utils/helpers.mjs` (mesma instalação) | `expandObject`, `setProperty`, `getProperty`, `mergeObject`. |
| **[CORE-P]** | `resources/app/common/packages/base-package.mjs` e `_types.mjs` | Esquema do array `languages` no manifest. |
| **[CORE-S]** | `resources/app/dist/packages/package.mjs` e `dist/files/files.mjs` (minificados) | Resolução e validação do `path` no servidor. |
| **[EXP]** | Scripts de experimento em `brain/.../scratch/` (`merge-test.mjs`, `survey.mjs`, `dups.py`, `canon.py`) | `merge-test.mjs` importa **o próprio `helpers.mjs` do core** e roda casos de borda. |
| **[LOCAL]** | `foundry-vtt-dev/Data/systems/*` e `Data/modules/*` (instalação local, somente leitura) | dnd5e 6.0.6, pf2e 8.7.0, sf2e 1.7.0, crucible 0.11.3, daggerheart 2.12.7, tormenta20 1.6.7, 3ds-atlas 1.5.5, hearthbound 0.9.1, vision-t20 1.0.3. |
| **[GH]** / **[GL]** | Arquivos brutos em GitHub/GitLab | [foundryvtt/dnd5e `lang/en.json`](https://raw.githubusercontent.com/foundryvtt/dnd5e/master/lang/en.json), [foundryvtt/pf2e `static/lang/en.json`](https://raw.githubusercontent.com/foundryvtt/pf2e/master/static/lang/en.json), [mclemente/fvtt-ptbr-dnd5e-translation `lang/pt-BR.json`](https://raw.githubusercontent.com/mclemente/fvtt-ptbr-dnd5e-translation/main/lang/pt-BR.json), grupo [fvtt-brasil](https://gitlab.com/fvtt-brasil): [core](https://gitlab.com/fvtt-brasil/core/-/raw/master/module.json), [dnd5e](https://gitlab.com/fvtt-brasil/dnd5e/-/raw/master/dnd5e_pt-BR/module.json), [pf2e](https://gitlab.com/fvtt-brasil/pf2e/-/raw/master/pf2e_pt-BR/module.json). |
| **[PY]** | [Documentação do módulo `json` do Python](https://docs.python.org/3/library/json.html) | Seções "Character Encodings" e "Repeated Names Within an Object". |

> [!NOTE]
> **Versões.** O código lido é do **v14 build 370** (a versão instalada). Para v11–v13 só tive acesso às API docs, que listam a mesma
> estrutura (`translations`, `_fallback`, `setLanguage`, `has`, `localize`, e — em v11 — os métodos então "privados por convenção"
> `_discoverSupportedLanguages`, `_getTranslations`, `_filterLanguagePaths`, `_loadTranslationFile`) [API11][API13]. O código v14
> ainda reporta erros com o rótulo `"Localization#_loadTranslationFile"` [CORE-L L359, L370], o que sugere continuidade do
> algoritmo. Afirmações sobre comportamento interno exato valem com certeza para v14; para v11–v13 são **inferência de alta confiança**.

---

## 1. A entrada `languages` no manifest

### 1.1 Campos

Esquema real (v14) [CORE-P `base-package.mjs` L367–L376]:

| Campo | Tipo/regra | Notas |
|---|---|---|
| `lang` | string, obrigatório, não vazio, validado por `Intl.getCanonicalLocales` | Só **valida**; não normaliza o valor salvo. |
| `name` | string, opcional | Se ausente, migração preenche `name = lang` [CORE-P L561–L562]. |
| `path` | string, obrigatório, não vazio | Relativo à raiz do pacote (ver 1.2). |
| `system` | id de pacote, opcional | Só carrega se `game.system.id === system` [CORE-L L334]. |
| `module` | id de pacote, opcional | Só carrega se `game.modules.get(module)?.active` [CORE-L L335]. |
| `flags` | objeto livre | Não é lido pelo carregamento [CORE-L L331–L339]. dnd5e/pf2e/sf2e declaram `"flags": {}` [LOCAL]. |

O typedef oficial documenta `system` como "Only apply this set of translations when a specific system is being used" e `module` como
"Only apply this set of translations when a specific module is active" [CORE-P `_types.mjs` L78–L84]. O artigo oficial documenta apenas
`lang`, `name`, `path`, e diz que `lang` é um código em minúsculas (link para ISO 639-2) [DOC] — **o artigo está desatualizado**
em relação ao esquema: códigos com região como `pt-BR` são aceitos e usados (3ds-atlas, hearthbound, vision-t20, tormenta20 [LOCAL];
fvtt-brasil [GL]).

Manifests de **System, Module e World** podem declarar `languages` [DOC]; o core carrega também os do world [CORE-L L307–L312].
Módulos com `"coreTranslation": true` traduzem a interface do core (ex.: `pt-BR` do fvtt-brasil [GL core]) [CORE-P `base-module.mjs` L20].

### 1.2 Resolução do `path`

- No servidor, `languages[].path` é um `PackageAssetField` com `mustExist: true`, `allowHTTP: true`, `relativeToPackage: true`
  [CORE-S `package.mjs`, classe `PackageAssetField` e `ServerPackageMixin.defineSchema`].
- O caminho é juntado a `Data/<systems|modules|worlds>/<id>/`; se escapar dessa pasta (`..`) é rejeitado (`isPathContained`), e se o
  arquivo não existir o servidor **lança erro** `The file "<path>" included by <type> <id> does not exist` [CORE-S `PackageAssetField.initialize`,
  `Files.resolveClientPaths`, `Files.isPathContained`].
- O caminho é normalizado com `path.normalize` e convertido para `/` (`Files.standardizePath`) [CORE-S `files.mjs`].
- **URLs HTTP são aceitas** como `path` (`allowHTTP`) e passadas adiante sem resolução local [CORE-S].
- O cliente faz `fetch(path)` do caminho já resolvido [CORE-L L352].

### 1.3 Vários arquivos para o mesmo `lang`

São suportados e comuns: `#filterLanguagePaths` devolve **todos** os `path` cujo `lang` bate [CORE-L L331–L339]. Exemplos:
pf2e declara 4 arquivos `en` (`en.json`, `action-en.json`, `re-en.json`, `kingmaker-en.json`) e sf2e 5 [LOCAL]; o módulo pt-BR do
fvtt-brasil para pf2e declara 3 arquivos `pt-BR` [GL pf2e]. Cada entrada repete `lang` e `name` (pf2e usa `name` diferente por
arquivo: "Main (English)", "Actions (English)"…) [LOCAL].

### 1.4 Idiomas fornecidos por um pacote **para outro**

- Mecanismo nativo: campos `system` / `module` da entrada (1.1) — o arquivo pertence ao pacote que o declara, mas só carrega se o
  sistema/módulo-alvo estiver em uso [CORE-L L334–L336].
- Na prática, os módulos de tradução pt-BR inspecionados **não usam** `system`/`module` na entrada: declaram o vínculo em
  `relationships.systems` (e, no pf2e, também no legado `systems: ["pf2e"]`) e confiam em só serem ativados no mundo certo [GL dnd5e, GL pf2e].
- Como as chaves vivem num dicionário global único (seção 2), um módulo de tradução simplesmente redefine as chaves do sistema
  (ex.: `"ACTOR.TypeCharacter"`, `"DND5E.…"`) no seu próprio arquivo [GL dnd5e `lang/pt-BR/system.json`].
- Pastas `lang/` desses módulos também contêm arquivos que **não são** de localização do core — p.ex. `lang/pt-BR/compendium/dnd5e.*.json`
  e `lang/en/*.json`, consumidos pelo módulo Babele (tradução de compêndios) e **não declarados** em `languages` [GL dnd5e, GL pf2e árvore do repo].

### 1.5 Código de idioma: comparação exata

A filtragem é `l.lang !== lang` (igualdade de string) [CORE-L L333], e `CONFIG.supportedLanguages` é indexado pelo `lang` literal
[CORE-L L259]. Como o esquema só valida (não canoniza) [CORE-P L368], **`pt-BR` e `pt-br` seriam idiomas distintos** (inferência
direta do código; não testei em runtime). O core só embarca `en` (`CORE_SUPPORTED_LANGUAGES = ["en"]`) [CORE `constants.mjs` L275].

---

## 2. Como o core monta o dicionário

### 2.1 Ordem de carga e precedência

`#getTranslations(lang)` [CORE-L L283–L321]:

1. core (`lang/<lang>.json`, só se `lang` ∈ `CORE_SUPPORTED_LANGUAGES`, i.e. `en`);
2. sistema ativo — entradas na ordem do manifest;
3. módulos ativos (mais o `defaultModule` de tradução do core, mesmo se inativo) — iterando `game.modules`;
4. world.

Todos são buscados em paralelo, mas **mesclados na ordem acima** com `mergeObject(translations, json, {inplace: true})`
(sobrescreve = o último vence) [CORE-L L315–L319]. O artigo oficial confirma core → sistema → módulos e que "modules may override
the translation strings assigned by the core software or by the game system" [DOC].

### 2.2 Planas × aninhadas × mistas

Cada arquivo é parseado com `resp.json()` e **expandido** com `foundry.utils.expandObject` antes da mescla [CORE-L L366–L368].
`expandObject` percorre as entradas **na ordem do arquivo** e aplica `setProperty(expanded, k, valor)`, que divide `k` em `.`
e cria objetos intermediários [CORE-H L545–L558, L852–L874]. Consequências (verificadas com o próprio `helpers.mjs` [EXP `merge-test.mjs`]):

| Entrada (um arquivo) | Resultado |
|---|---|
| `{"A.B.C":"x","A.B.D":"y"}` | `{A:{B:{C:"x",D:"y"}}}` — planas e aninhadas são **equivalentes**. |
| `{"A":{"B":"x"},"A.C":"y"}` | `{A:{B:"x",C:"y"}}` — mistura funciona se o objeto vem antes. |
| `{"A":{"B.C":"x"}}` | `{A:{B:{C:"x"}}}` — chaves pontuadas **dentro** de objetos também são expandidas (recursivo). |
| `{"A.C":"y","A":{"B":"x"}}` | `{A:{B:"x"}}` — **`A.C` some**: a chave posterior `A` substitui o objeto inteiro. |
| `{"A.B":"x","A":"str"}` | `{A:"str"}` — folha posterior apaga o ramo. |
| `{"A":"str","A.B":"x"}` | **Erro** `Cannot use 'in' operator to search for 'B' in str` → o arquivo **inteiro** vira `{}` (o `catch` registra "Unable to parse localization file" e retorna objeto vazio) [CORE-L L369–L376]. |
| `{"A.B":"first","A.B":"second"}` | `{A:{B:"second"}}` — duplicata textual: vence a última (`JSON.parse`). |
| `{"__proto__.x":"bad","A.B":"ok"}` | `__proto__`, `constructor`, `prototype` são ignorados [CORE-H L842, L859, L866]. |

Entre arquivos, `mergeObject` é recursivo: objeto × objeto mescla; tipos diferentes → o posterior **substitui** [CORE-H L1199–L1230]:

- sistema `{A:{B:"sys",C:"sys"}}` + módulo `{"A.B":"mod"}` → `{A:{B:"mod",C:"sys"}}` (override pontual) [EXP];
- sistema `{A:{B:"sys"}}` + módulo `{A:"modstring"}` → `{A:"modstring"}` (ramo inteiro perdido) [EXP];
- sistema `{A:"sysstring"}` + módulo `{A:{B:"mod"}}` → `A` vira objeto e `localize("A")` deixa de achar string [EXP].

Outros detalhes:

- `mergeObject` interpreta chaves que começam com `-=` ou `==` como operadores de deleção/substituição (deprecados desde v14)
  [CORE-H `isDeletionKey` L1662–L1665, L1164–L1168]. Uma chave de tradução assim seria tratada como operador (borda teórica; não vista nos arquivos).
- `localize`/`has` só aceitam valores `typeof === "string"`; números, `null`, objetos → tratados como ausentes [CORE-L L390–L396, L436–L443].
- Placeholders são `{nome}`, substituídos por `/{[^}]+}/g` em `format`/`localize(key, data)` [CORE-L L400, L444].
- Quando `CONFIG.debug.i18n` está ligado, chaves inexistentes que parecem IDs (`/^[\x21-\x2D\x2F-\x7E]+(?:\.[\x21-\x2D\x2F-\x7E]+)+$/`)
  geram `console.error` [CORE-L L47, L438–L440].

### 2.3 Fallback

- Para idioma ≠ `en`, o core carrega **também o dicionário `en` completo** (todas as fontes, mesma ordem) em `_fallback` [CORE-L L234–L237].
- `localize(key)`: tenta `translations`; se não for string, tenta `_fallback`; se ainda não, **devolve a própria chave** [CORE-L L435–L445].
  O v11 já documentava "If a translation is not available, the original string is returned" [API11].
- O fallback é **sempre `en`**, não o "idioma base" do pacote. Se um pacote declara `en` apontando para um arquivo em outro idioma — como
  o tormenta20, cujo `en` aponta para `lang/pt-BR.json` [LOCAL] — o "fallback inglês" daquele pacote será português.
- Também há fallback para `label`/`hint` de DataModels via `<prefix>.FIELDS` (desde v12) [CORE-L L169–L180; API13 `localizeDataModel`].
- Se `setLanguage` recebe um idioma fora de `CONFIG.supportedLanguages`, cai para `en` [CORE-L L227–L230].

---

## 3. Padrões observados nos arquivos reais

### 3.1 Estilo de chave e estrutura

| Arquivo | Estilo | Folhas | Prof. máx. | Fonte |
|---|---|---:|---:|---|
| core `public/lang/en.json` (v14) | aninhado no topo + muitas planas `"SCENE.X"` | — | — | [LOCAL] |
| dnd5e `en.json` | **misto**: 957 chaves planas no topo + 123 objetos; 1090 chaves pontuadas | 4059 | 8 | [LOCAL]=[GH] (bytes idênticos) |
| pf2e `en.json` (+3 arquivos) | **totalmente aninhado**, 0 chaves pontuadas, topo ordenado | 5830 | 7 | [LOCAL], [GH] |
| crucible `en.json` | aninhado com chaves pontuadas internas (38) | 2130 | 8 | [LOCAL] |
| daggerheart `en.json` | aninhado, 0 pontuadas | 2321 | 10 | [LOCAL] |
| tormenta20 `pt-BR.json` | aninhado + 28 pontuadas; **1 chave duplicada** (`T20.Immunity`) | 1756 | 9 | [LOCAL] [EXP `dups.py`] |
| 3ds-atlas (9 idiomas) | **totalmente plano** (12 370 chaves em `en`, 3444 em `pt-BR`) | — | 1 | [LOCAL] |
| hearthbound (4 idiomas) | aninhado sob um único objeto raiz, ordenado | 1314 | 7 | [LOCAL] |
| vision-t20 | **`en` plano, `pt-BR` aninhado** (estilos diferentes entre base e alvo) | 23 / 11 | 1 / 4 | [LOCAL] |
| mclemente pt-BR dnd5e | misto (espelha o `en` do dnd5e) | 3065 | 8 | [GH] |
| fvtt-brasil core `pt-BR/foundry.json` | plano | 2276 | 1 | [GL] |
| fvtt-brasil dnd5e `pt-BR/system.json` | plano | 1211 | 1 | [GL] |
| fvtt-brasil pf2e `pt-BR/system.json` | aninhado | — | — | [GL] |

Nenhum arquivo inspecionado tinha valores não-string [EXP `survey.mjs`]. HTML embutido é comum (pf2e `action-en.json`: 908 tags;
dnd5e: 81) e placeholders `{x}` aparecem às centenas (dnd5e 640, pf2e 752) [EXP `survey.mjs`].

### 3.2 Formatação byte a byte — "canônico para `json.dumps`?"

"Canônico" = o corpo é **idêntico** a `json.dumps(json.loads(txt), indent=N, ensure_ascii=False)` após normalizar CRLF→LF e o newline
final [EXP `canon.py`]. Nenhum arquivo usa BOM, `\uXXXX`, `\/`, tabs, ou formato compacto.

| Arquivo | Indent | EOL | `\n` final | Canônico? | Desvios |
|---|---|---|---|---|---|
| core `en.json` (v14, instalação Windows) | **0 no topo**, 2 dentro | CRLF | sim | **não** | 125 linhas em branco separando grupos; 15 `"k" : "v"` (espaço antes de `:`); 3 `"k":"v"` |
| dnd5e `en.json` | **0 no topo**, 2 dentro | LF | sim | **não** | 159 linhas em branco; 83 objetos inline `{ "label": "…" }` |
| pf2e `en.json`, `action-en.json` | 4 | LF | sim | sim | — |
| crucible `en.json` | 2 | LF | sim | **não** | 1 `"k":"v"` sem espaço |
| crucible `de.json` | 2 | LF | sim | sim | — |
| daggerheart `en.json` | 4 | LF | **não** | **não** | 10 objetos inline; 6 linhas com espaço no fim |
| tormenta20 `pt-BR.json` | 2 | LF | **não** | **não** | chave duplicada (some no round-trip) |
| 3ds-atlas `en`/`pt-BR` | 2 | **CRLF** | sim | sim | — |
| hearthbound `en`/`pt-BR` | 2 | **CRLF** | sim | sim | — |
| vision-t20 `en`/`pt-BR` | 4 | LF | sim | sim | — |
| dnd5e `en.json` (GitHub) | 0/2 | LF | sim | **não** | idem local |
| pf2e `en.json` (GitHub) | 4 | LF | sim | sim | — |
| mclemente pt-BR dnd5e | 2 | LF | sim | sim | (não replica a formatação 0/2 do `en`) |
| fvtt-brasil core pt-BR | 2 | LF | sim | sim | — |
| fvtt-brasil dnd5e pt-BR | 4 | LF | sim | sim | — |
| fvtt-brasil pf2e pt-BR | 4 | LF | **não** | sim | — |

> [!WARNING]
> CRLF nos arquivos locais pode ser artefato de `git core.autocrlf` no Windows (o dnd5e local é LF e byte-idêntico ao GitHub, mas não
> verifiquei a origem de 3ds-atlas/hearthbound). De qualquer forma, é o que o app vai encontrar em disco no Windows.

### 3.3 Ordenação

Topo ordenado alfabeticamente: pf2e, sf2e, hearthbound, vision-t20 `pt-BR`. Não ordenados: dnd5e, core, crucible, daggerheart,
tormenta20, 3ds-atlas, fvtt-brasil core/dnd5e [EXP `survey.mjs`, `remote.mjs`]. A ordem **importa semanticamente** em casos mistos
(tabela 2.2), não só esteticamente.

### 3.4 BOM e codificação

- Nenhum arquivo inspecionado tem BOM [EXP].
- `JSON.parse` puro rejeita BOM [EXP `merge-test.mjs`], mas o core usa `Response.json()` [CORE-L L366], cujo algoritmo decodifica com
  "UTF-8 decode", que remove BOM ([Fetch — consume body / parse JSON from bytes](https://fetch.spec.whatwg.org/#ref-for-parse-json-from-bytes);
  [Encoding — UTF-8 decode](https://encoding.spec.whatwg.org/#utf-8-decode)). Ou seja, **o Foundry tolera BOM**.
- O Python `json.loads(str)` **rejeita** BOM ("Unexpected UTF-8 BOM (decode using utf-8-sig)") [EXP]; a doc diz que o desserializador
  "raises a ValueError when an initial BOM is present" e que o serializador não escreve BOM [PY "Character Encodings"].
- Duplicatas: Python por padrão "ignores all but the last name-value pair" [PY "Repeated Names Within an Object"] — mesmo resultado do
  `JSON.parse`, mas **o round-trip perde a duplicata** silenciosamente.

---

## Caso de referência: hearthbound

Módulo de referência do projeto (`Data/modules/hearthbound`, v0.9.1, `compatibility.minimum: "14"`, `verified: "14.370"`) [LOCAL]:

- `languages`: 4 entradas simples `lang`/`name`/`path` — `en`, `pt-BR`, `es`, `eo` → `lang/<lang>.json`; sem `system`/`module`/`flags` [LOCAL `module.json` L29+].
- Estrutura: **100% aninhado** sob uma única raiz `HEARTHBOUND`, 0 chaves pontuadas, profundidade máx. 7, **1314 folhas em cada arquivo**,
  com a **mesma sequência de caminhos nos 4 arquivos** (alvos espelham a ordem do `en`) [EXP `survey.mjs` + verificação Python].
- Ordem: o topo tem uma chave só; os níveis internos **não** são estritamente ordenados por code point — ou seja, a ordem é a do autor, não
  um sort automático [EXP].
- Bytes: indent 2, **CRLF**, newline final, sem BOM, sem `\uXXXX`/`\/`, sem espaços no fim; **canônico** para
  `json.dumps(indent=2, ensure_ascii=False)` + CRLF + `\n` final nos 4 arquivos [EXP `canon.py`].
- Conteúdo: 186 placeholders `{x}` por arquivo, 0 tags HTML [EXP `survey.mjs`].
- Leitura: é o **caso fácil** — qualquer abordagem de escrita (re-serialização ou spans) preserva os bytes; ele **não** exercita os casos
  difíceis (misto plano/aninhado, formatação não canônica, duplicatas, vários arquivos por `lang`). Os testes de round-trip precisam de
  fixtures adicionais (dnd5e `en.json`, core `en.json`, tormenta20 `pt-BR.json`, daggerheart `en.json`, pf2e multi-arquivo).

> [!NOTE]
> **Versão-alvo: v14.** Onde houver divergência entre versões, valem as afirmações sobre o código v14 build 370 lido neste documento.

---

## Implicações para o i18n Reviewer

1. **Descoberta via manifest é viável e precisa tratar:** vários arquivos por `lang` (concatenar logicamente, na ordem do manifest, último
   vence); `system`/`module` condicionais; `path` que pode ser URL HTTP (não editável — sinalizar); `lang` comparado por string exata
   (não normalizar `pt-br`→`pt-BR` silenciosamente); `name` opcional; arquivos em `lang/` **não declarados** (Babele) devem ser ignorados
   ou explicitamente fora de escopo.
2. **Modelo de chave = caminho expandido.** A identidade de uma string é o caminho pontuado após `expandObject`; plano, aninhado e misto são
   equivalentes para o Foundry. O app deve comparar base × alvo nesse espaço normalizado, porque base e alvo **podem ter estilos diferentes**
   (vision-t20; mclemente vs dnd5e na formatação).
3. **Validação pré-produção deve replicar a semântica do core**, incluindo os casos que quebram: folha seguida de ramo com o mesmo prefixo
   (o Foundry descarta o **arquivo inteiro**), ramo apagado por folha/objeto posterior, chaves duplicadas (existem no mundo real — tormenta20),
   valores não-string, chaves `-=`/`==`/`__proto__`. Esses são bons candidatos a "chaves corrompidas" que bloqueiam o envio.
4. **A stdlib (`json.dumps`) não basta para preservar estilo.** Vários arquivos populares não são canônicos (core e dnd5e: topo sem indentação,
   linhas em branco, objetos inline; crucible/daggerheart: espaçamento irregular, espaços no fim; sem newline final em alguns). Para a premissa
   "preserva exatamente estilo e ordem", **edição por spans (substituir só o literal do valor) é obrigatória** ao menos para arquivos não canônicos;
   detectar e preservar EOL (LF/CRLF), newline final, BOM (se houver) e indentação por arquivo. Escrever strings com `ensure_ascii=False`-equivalente
   (todos os arquivos usam UTF-8 literal, zero `\uXXXX`).
5. **Fallback de referência:** o Foundry cai para `en`, não para o idioma de origem do pacote, e alguns pacotes declaram `en` apontando para
   outro idioma (tormenta20). O app não deve assumir que "base = en" sem checar.
6. **Escala:** arquivos de 5–12 mil folhas e até ~950 KB por arquivo (3ds-atlas `en`), com HTML e placeholders `{x}` abundantes — confirmar que
   filtro/validação em tempo real aguentam isso.
