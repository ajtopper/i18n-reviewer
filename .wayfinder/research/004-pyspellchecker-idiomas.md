# Achados — pyspellchecker para pt-BR, es, fr, de

Ticket: [pyspellchecker para pt-BR, es, fr, de](../tickets/004-pyspellchecker-idiomas.md)
Data: 2026-11-11 · Pesquisa: research-agent

> **Resposta curta:** **não, em nenhum dos 4 idiomas.** O dicionário `pt` do `pyspellchecker` é uma lista **pt-PT**
> (Acordo de 1990) — rejeita `ônibus`, `econômico`, `contato`, `registro`, `bônus`, `fenômeno`. O `es` é praticamente
> só lemas: falta `puede`, `horas`, `minutos`, `hay`, `está` — **45% das palavras únicas da tradução real `es.json` do
> Hearthbound são marcadas**. Em `fr` toda elisão (`l'arme`) é marcada; em `de` compostos comuns (`Rettungswurf`)
> também. Hunspell (dicionários LibreOffice) acerta esses casos (1,2% pt-BR / 1,9% es marcados nos arquivos reais,
> quase tudo nome próprio/inglês). Recomendação: **`pyenchant` (Hunspell nativo) + dicionários LibreOffice
> empacotados**, atrás de uma interface própria de corretor.

## Fontes e método

- **Código-fonte do `pyspellchecker` 0.9.1** (versão atual no PyPI, publicada em 2026-10-10 — https://pypi.org/pypi/pyspellchecker/json),
  lido a partir do wheel instalado: `spellchecker/spellchecker.py`, `spellchecker/utils.py`, README (METADATA).
- **Script de build dos dicionários**: https://github.com/barrust/pyspellchecker/blob/master/scripts/build_dictionary.py
  e a lista-base `scripts/data/levidromelist-dicts/portuguese.txt` do mesmo repositório.
- **Dicionários Hunspell LibreOffice**: https://github.com/LibreOffice/dictionaries (`pt_BR/`, `es/es_ES`,
  `fr_FR/dictionaries/fr`, `de/de_DE_frami`).
- **PyPI JSON API** para `spylls`, `cyhunspell`, `pyenchant`, `symspellpy`.
- **Hook PyInstaller**: https://github.com/pyinstaller/pyinstaller-hooks-contrib (`stdhooks/hook-enchant.py`).
- **Experimentos** num venv descartável (Python 3.14.7, Windows) fora do repo:
  `…\brain\7362d1f6-…\scratch\spell_exp.py`, `spylls_exp.py`, `enchant_exp.py`.
- ⚠️ O Context7 não estava acessível neste subagente (ferramenta MCP não exposta); todas as afirmações vêm do código-fonte,
  repositórios e PyPI acima, ou de execução direta.

## 1. Dicionários embutidos do pyspellchecker

| Fato | Fonte |
|---|---|
| Idiomas: `en, es, fr, it, pt, de, ru, ar, lv, eu, nl, fa`. Só existe **`pt`**, sem variante. | `SpellChecker.languages()` em `spellchecker.py`; README |
| Cada dicionário é um JSON gzip `resources/<lang>.json.gz` lido via `pkgutil.get_data("spellchecker", …)`. | `spellchecker.py` (`__init__`) |
| Tamanhos (gz): pt 1,26 MB, de 1,08 MB, fr 0,50 MB, es 0,35 MB. Palavras únicas: pt 416 782, de 339 101, fr 139 905, es 86 158. | listagem do pacote + experimento |
| Origem: frequências de palavras do **OpenSubtitles 2018**, limpas por regras por idioma, corte `MINIMUM_FREQUENCY = 50`, depois **filtradas por uma lista de palavras** (`levidromelist-dicts/<idioma>.txt`) e completadas com ela (freq. 50). | `build_dictionary.py` linhas 7–18, 36, `clean_portuguese` (592–661) |
| Em `pt` o alfabeto aceito é `abcdefghijklmnopqrstuvwxyzáâãàçéêíóôõú` (sem `ü`); em `fr` inclui `œæ` mas **não o apóstrofo**; em `de` `äöüß`. | `build_dictionary.py` linhas 600, 528, 456 |
| `pt_include.txt` está vazio — nenhuma correção manual para pt. | `scripts/data/pt_include.txt` (experimento: 0 entradas) |

### O `pt` é pt-PT, não uma mistura

A lista-base `portuguese.txt` tem exatamente **416 782** entradas — o mesmo número de palavras únicas do `pt.json.gz`,
ou seja, o dicionário final é essa lista. Verificação direta nela:

| Palavra | Na lista | Palavra | Na lista |
|---|---|---|---|
| ônibus | ❌ | autocarro | ✅ |
| econômico | ❌ | económico | ✅ |
| contato | ❌ | contacto | ✅ |
| registro | ❌ | registo | ✅ |
| fenômeno | ❌ | fenómeno | ✅ |
| bônus | ❌ | ação / ideia | ✅ (pós-Acordo) |
| fato | ✅ | acção / idéia | ❌ |

Frequências no `pt.json.gz` reforçam: `facto` 52 682 vs `fato` 24 464; `equipa` 87 499 vs `equipe` 5 229.

**Experimento (pt-BR válidas, 46 palavras, vocabulário de RPG):** 12 rejeitadas —
`bônus, contato, econômico, elfo, fenômeno, goblin, grimório, infravisão, patrulheiro, registro, rolagem, ônibus`.
**pt-PT que deveriam ser alertadas em pt-BR:** só 7/14 foram; `facto, contacto, autocarro, registo, equipa, fenómeno, económico` passaram.
Grafias pré-Acordo (`idéia, vôo, freqüência, lingüiça`) são marcadas — correto para pt-BR atual.

## 2. Dicionário customizado/pessoal

- `SpellChecker(local_dictionary=path)` carrega um JSON (opcionalmente `.gz`) de `{palavra: frequência}`; é **exclusivo com `language`** (ValueError se ambos). — `spellchecker.py` `__init__`.
- `language` aceita lista: vários dicionários somados. — idem.
- Runtime: `word_frequency.load_words([...])`, `add(word, val)`, `load_text(...)`, `load_text_file(...)`, `remove(...)`, `remove_by_threshold(n)`. — `WordFrequency`.
- Persistência: só `export(path, gzipped=True)` do **dicionário inteiro** (centenas de milhares de entradas); não há conceito de "lista pessoal" separada — o app teria que manter o próprio arquivo e reaplicar `load_words` a cada carga. — `SpellChecker.export`.
- Dicionários de idioma são **forçadamente case-insensitive** (`case_sensitive=True` só sem `language`). — `__init__`.
- Experimento: `load_words(["Hearthbound"])` → `known` ok; `remove` → some. Funciona, mas tudo vira minúsculas.

## 3. Tokenização

- Tokenizer padrão: `re.findall(r"(\w[\w']*\w|\w)", text)` — mantém apóstrofo ASCII interno, quebra em hífen e em tudo
  que não é `\w`. Pode-se passar `tokenizer=` próprio. — `utils._parse_into_words`; `SpellChecker.__init__`.
- Experimento `split_words("L'arme d'attaque, peut-être aujourd'hui {name} @UUID[Item.x] <b>Dano</b> 2d6+3 Rüstungsklasse")`
  → `["L'arme","d'attaque","peut","être","aujourd'hui","name","UUID","Item","x","b","Dano","b","2d6","3","Rüstungsklasse"]`.
  - Placeholders `{name}`, links `@UUID[...]` e tags HTML **viram palavras** → o app precisa mascarar antes de tokenizar.
  - **fr:** o tokenizer mantém `l'arme`, mas o dicionário fr não tem apóstrofo (alfabeto acima) → **toda elisão é falso positivo**
    (`l'arme, d'attaque, l'initiative, qu'il` rejeitadas; `aujourd'hui` passa por estar na lista). O apóstrofo tipográfico `’` nem é `\w`.
  - **fr:** `cœur`, `œuvre` rejeitadas; `coeur` (grafia errada) aceita.
  - Números puros são ignorados (`_check_if_should_check`), mas `2d6` vira token a checar.
- **de:** 12/31 compostos usuais rejeitados (`Rettungswurf, Trefferpunkte, Rüstungsklasse, Angriffswurf, Nahkampfwaffe, Zauberspruch, Charakterbogen, …`).
  Não há decomposição de compostos — é uma lista plana de formas.
- **es:** a lista de teste curta (vocabulário de RPG no singular) parecia boa — 1/23 falso positivo (`envenenado`) — mas o
  teste com dados reais (seção 4b) mostra que o dicionário **não tem plurais nem conjugações comuns**. Causa: a lista-base
  `levidromelist-dicts/spanish.txt` (86 016 entradas) contém `hora, minuto, prueba` mas não `horas, minutos, pruebas, puede, hay, está`,
  e o build remove do corpus tudo que não está nela (`clean_spanish`, mesmo padrão de `clean_portuguese`). Não é regressão:
  o `es.json.gz` da 0.8.4 tem as mesmas 86 158 entradas e as mesmas lacunas.

## 4. Desempenho e empacotamento

| Medida (pyspellchecker 0.9.1, Py 3.14) | Resultado |
|---|---|
| Carga pt / de / fr / es | 0,34 s / 0,24 s / 0,09 s / 0,05 s |
| `unknown()` em 3 200 palavras | 0,005 s |
| `correction()` distância 2 (pt), 10 palavras | 1,66 s (~166 ms/palavra); `candidates("conjuracao")` 0,47 s |
| `correction()` distância 1 | ~1 ms/palavra, mas perde `conjuracao→conjuração` (2 edições: ç e ã) |

- Verificação é barata; **sugestões com distância 2 são lentas** e o README recomenda distância 1 para palavras longas. Sugestões
  são ordenadas só por frequência (com preferência por diferença só de acentos): `salvaguardaa→salvaguardar`, `patrulhero→patrulhar`.
- **PyInstaller:** não existe `hook-spellchecker.py` no pyinstaller-hooks-contrib (404 em `stdhooks/`); como os dados são lidos com
  `pkgutil.get_data`, é preciso `collect_data_files('spellchecker')` num hook/spec próprio (não testado em build congelado).

## 4b. Medida com traduções reais (módulo Hearthbound)

Arquivos: `foundry-vtt-dev/Data/modules/hearthbound/lang/pt-BR.json` e `es.json` (1 314 strings cada; `module.json` declara
`en, pt-BR, es, eo`). Placeholders `{x}`/`{{x}}`, `@X[...]`, tags HTML e entidades mascarados; tokens = sequências de letras com
hífen/apóstrofo internos; pyspellchecker checa as partes de palavras hifenizadas. Script: `scratch/real_data_exp.py`.

| Arquivo | Tokens / únicos | pyspellchecker marcados (únicos · ocorrências) | Hunspell via pyenchant (únicos · ocorrências) |
|---|---|---|---|
| pt-BR.json | 11 897 / 2 642 | **121 (4,6%) · 528 (4,4%)** | **32 (1,2%) · 80 (0,7%)** |
| es.json | 12 305 / 2 677 | **1 209 (45,2%) · 3 009 (24,5%)** | **50 (1,9%) · 263 (2,1%)** |
| eo.json | 10 340 / 3 135 | — (sem dicionário `eo`) | 115 (3,7%) · 5,0% |

- **Falsos positivos só do pyspellchecker, pt-BR** (amostra): `Percepção, percepção, bônus, Furtividade, Rolagem, rolagens, Planejamento,
  detectar, detecta, umidade, úmidas, incômodo, gerencia, Gerenciar, crônica, Registro, registros, Fenômeno, magias, facção, facções,
  pedágio, quilômetros, inanição, desobstrui, surrupiar, lacrimejantes, forrageamento`. Quase todos são grafias pt-BR (`percepção` vs pt-PT
  `perceção`, `detectar` vs `detetar`, `facção` vs `fação`, `registro`, `quilômetros`, `bônus`).
- **Falsos positivos só do pyspellchecker, es** (amostra): `puede, hay, está, horas, minutos, días, puntos, todas, pruebas, tiradas, criaturas,
  personajes, raciones, provisiones, encuentros, pierde, sufre, otorga, permite, requiere, reduce`.
- **O que o Hunspell marca** é quase só o que deveria ir para glossário/dicionário pessoal ou ser ignorado: nomes (`Hearthbound, Calendaria,
  Foundry`), inglês deixado no texto (`RollTable, Journey, Travel, Off-Guard, Death, Saves`), siglas (`PV, VTT, NPCs, DJ`), abreviações de
  unidade (`h, m, ft, po`) e termos de jogo (`Arcanismo, goblins, bonificador, penalizador, Rolaje`). Únicas marcações "só Hunspell":
  `www`, `com` (URL). Nenhum falso positivo de grafia pt-BR/es comum.
- **Esperanto:** `"eo" in SpellChecker.languages()` → `False` (confirmado). O LibreOffice tem `eo/eo.aff|.dic`; funcionou no pyenchant
  (3,7% únicos marcados, também majoritariamente nomes/inglês/siglas: `Hearthbound, Off-Guard, Insight, Fatigued, KD, VP`). Licença do
  `eo`: **GPLv3** (`eo/license-en.txt`).

## 5. Alternativas (Hunspell + dicionários LibreOffice)

Mesmos testes com os dicionários LibreOffice: `pt_BR` (VERO, LGPLv3/MPL — `pt_BR/README_pt_BR.txt`), `es_ES`, `fr` (Grammalecte 7.7, MPL 2.0 —
`fr_FR/dictionaries/README_dict_fr.txt`), `de_DE_frami`.

| Motor | Situação no PyPI | Resultado nos testes |
|---|---|---|
| **pyenchant 3.3.0** | 2025-09; wheel `win_amd64` com libenchant + providers **hunspell e nuspell** embutidos; LGPL; só dicionários `en_*` incluídos | pt_BR: aceita `ônibus, econômico, contato, registro, bônus, grimório, patrulheiro, rolagem, guarda-costas`; rejeita `acção, idéia, vôo, lingüiça, económico`. fr: aceita `l'arme`, `l’arme`, `qu'il`, `cœur`; rejeita `coeur`. de: aceita todos os compostos testados. es: 0 falsos positivos. Carga 0,05–0,23 s; 3 sugestões em 0,01–0,17 s, de boa qualidade (`Angrifswurf→Angriffswurf`, `coeur→cœur`, `dano→daño`). |
| **spylls 0.1.7** | 2022-01, "Beta", Hunspell em Python puro, MIT | Mesma qualidade de aceitação (é Hunspell), mas carga 0,5–2,3 s e **sugestões inviáveis**: 3 palavras em 45 s (pt_BR) e 107 s (fr). |
| **cyhunspell 2.0.2** | 2021-02; wheels Windows só até **cp39** | Sem wheel para o Python atual — descartado. |
| hunspell 0.5.5 / phunspell 0.1.6 | 2018 / 2021, só sdist | Exigem compilação — descartados. |
| symspellpy 6.10.2 | 2026-11, MIT | Mesmo modelo de frequência; não traz dicionários pt-BR/fr/de — trocaria o problema de lugar. Não testado. |

Detalhes do pyenchant verificados no experimento:
- Dicionários extras: pastas `<ENCHANT_CONFIG_DIR>/hunspell/<lang>.aff|.dic` são descobertas (`list_languages()` passou a listar `pt_BR, es_ES, fr_FR, de_DE`).
  Alternativa: copiar para `enchant/data/mingw64/share/enchant/hunspell`.
- Dicionário pessoal: `enchant.DictWithPWL("pt_BR", "pessoal.txt")` + `add("Hearthbound")` grava a palavra no arquivo texto (uma por linha) — persistência pronta e case-preserving.
- `enchant.checker.SpellChecker` tem tokenizer próprio, mas também marca `name` e `UUID` de placeholders → o mascaramento é responsabilidade do app em qualquer motor.
- Falsos negativos pt_BR: o VERO aceita `facto, contacto, autocarro, registo` (variantes pt-PT legítimas no dicionário). Aceitável: falso negativo é muito menos custoso que falso positivo para revisor.
- **PyInstaller:** existe `hook-enchant.py` oficial (`collect_dynamic_libs('enchant')` + `collect_data_files('enchant')`); não testado em build congelado. Os `.aff/.dic` do LibreOffice (~10 MB para os 4 idiomas, sem compressão) iriam como `datas` próprios, com `ENCHANT_CONFIG_DIR` apontando para eles antes do `import enchant`.

## Implicações para o i18n Reviewer

1. **Descartar `pyspellchecker` como motor.** pt-BR: dicionário é pt-PT (4,4% das ocorrências reais marcadas, quase tudo grafia BR correta). es: dicionário sem flexões (24,5% das ocorrências reais marcadas). fr: elisões sempre marcadas. de: compostos marcados. eo: inexistente.
2. **Motor recomendado: `pyenchant` (provider hunspell) + dicionários LibreOffice** (`pt_BR` VERO, `es_ES`, `fr_FR` Grammalecte, `de_DE_frami`, e `eo` se o Esperanto entrar) empacotados com o app. Qualidade alta (0,7–2,1% de ocorrências marcadas nos arquivos reais, quase tudo nome/inglês/sigla), carga < 0,25 s, sugestões em ~50 ms, dicionário pessoal com persistência nativa (PWL). Como é Hunspell genérico, **qualquer idioma com `.aff/.dic`** passa a ser suportado sem código novo.
3. **Isolar o motor atrás de uma interface própria** (`check(token)`, `suggest(token)`, `add_personal(word)`); trocar de motor no futuro custa só o adaptador. `spylls` serve de fallback puro-Python só para verificação (não para sugestões).
4. **Tokenização é do app, não do motor:** mascarar placeholders (`{x}`, `{{x}}`, `%s`), `@UUID[...]`/`@Compendium[...]`, tags HTML e termos do glossário antes de checar; tratar `’` e `'` em francês; não quebrar palavras com hífen antes de consultar o Hunspell (ele aceita `guarda-costas`, `peut-être`).
5. **Sugestões sob demanda** (menu de contexto/`Ctrl+Space`), verificação em tempo real só com `check()`; nada de calcular sugestões para todo o texto.
6. **Licenças a registrar na distribuição:** pyenchant/libenchant LGPL (linkagem dinâmica via DLL ok), VERO LGPLv3/MPL, Grammalecte MPL 2.0, `eo` **GPLv3**; `es_ES` e `de_DE_frami` precisam ter a licença conferida no README de cada pasta antes de empacotar.
7. **Ruído residual previsível:** siglas (`PV`, `DC`), unidades (`h`, `m`, `ft`) e inglês deixado de propósito (`RollTable`, `Off-Guard`) — a política de ignorar tokens (tudo maiúsculo, ≤ 2 letras, termos do glossário/fonte `en`) decide se o corretor fica útil ou chato.
