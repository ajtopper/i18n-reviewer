# Achados — Empacotamento de dicionários Hunspell

Ticket: [Empacotamento de dicionários Hunspell](../tickets/017-empacotamento-dicionarios-hunspell.md)
Data: 2026-11-11 · Pesquisa: research-agent · Anterior: [pyspellchecker para pt-BR, es, fr, de](004-pyspellchecker-idiomas.md)

> **Resposta curta:** **sim, dá para distribuir**, com três ressalvas. (1) O build congelado PyInstaller 6.22.3
> `--onedir --windowed` + pyenchant 3.3.0 + `hook-enchant` oficial **funciona em Python 3.14 no Windows** sem hook
> próprio; os dicionários extras entram por `--add-data` e um dicionário colocado pelo usuário em
> `ENCHANT_CONFIG_DIR\hunspell` foi detectado. (2) **Bug bloqueante de caminho:** o provider hunspell do wheel
> (build MinGW) **não abre `.aff/.dic` em caminhos com caracteres não-ASCII** (`C:\Users\João\…`, `pasta ção`):
> o dicionário "carrega" vazio, sem exceção, e **rejeita todas as palavras**. Contorno testado: caminho curto 8.3.
> (3) **Licenças:** `de_DE_frami` e `eo` são **só GPL** (para o nosso caso); `es` e `pt_BR` aceitam LGPLv3/MPL;
> `fr` é MPL 2.0; e o wheel do pyenchant arrasta ~48 DLLs MSYS2 que o app não usa, algumas **GPLv3** (readline,
> gettext-tools) — dá para removê-las. Tamanho: **120 MB** (onedir cru) → **38,8 MB / 14,8 MB zip** enxuto.

## Fontes e método

- **Repositório LibreOffice/dictionaries** (branch `master`, lido via `raw.githubusercontent.com` e API do GitHub em
  2026-11-11): `pt_BR/README_en.txt`, `pt_BR/README_pt_BR.txt`, `pt_BR/description.xml`; `es/LICENSE.md`,
  `es/README_hunspell_es.txt`; `fr_FR/dictionaries/README_dict_fr.txt`, `fr_FR/description.xml`;
  `de/README_de_DE_frami.txt`, `de/README_extension_owner.txt`, `de/COPYING_OASIS.txt`; `eo/license-en.txt`,
  `eo/description.xml`. Os tamanhos dos `.aff/.dic` usados no experimento batem byte a byte com os do `master`
  (ex.: `pt_BR.dic` 4 477 695, `de_DE_frami.dic` 4 356 903, `eo.dic` 377 989).
- **pyenchant 3.3.0** — código do wheel `win_amd64` instalado (`enchant/_enchant.py`, `METADATA`,
  `licenses/LICENSE.txt`) e licença do repositório (API GitHub `pyenchant/pyenchant` → `LGPL-2.1`).
- **Enchant** (https://github.com/rrthomas/enchant): `lib/enchant.5.in.in` (man page enchant(5)), `lib/provider.vala`,
  `lib/dict.vala`, `providers/enchant_hunspell.cpp`; licença via API (`LGPL-2.1`).
- **Hunspell** (https://github.com/hunspell/hunspell, tag `v1.7.2`): `src/hunspell/csutil.cxx` (`myopen`),
  `src/hunspell/filemgr.cxx`, cabeçalho de licença `MPL 1.1/GPL 2.0/LGPL 2.1`. **Nuspell**: API GitHub → `LGPL-3.0`.
- **MSYS2** (https://packages.msys2.org/package/mingw-w64-x86_64-<pkg>): campo *License(s)* das DLLs embutidas no wheel.
- **PyInstaller**: `pyinstaller-hooks-contrib` `stdhooks/hook-enchant.py`; `COPYING.txt` (Bootloader Exception);
  `doc/hooks.rst` (`module_collection_mode`).
- **GNU**: texto da LGPL-2.1 (https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt), GPL FAQ `#MereAggregation`
  (https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation). MPL 2.0: https://www.mozilla.org/MPL/2.0/.
- **Experimento** (venv descartável `…\brain\7362d1f6-…\scratch\venv-enchant`, CPython **3.14.4** de `C:\Python314`,
  pyenchant 3.3.0 com libenchant **2.3.4**, PyInstaller 6.22.3, pyinstaller-hooks-contrib 2026.10). Script e saídas em
  `…\scratch\enchant-freeze\` (`hello_enchant.py`, `nuspell_test.py`, `dist\`, `slim\`, `build.log`).
- ⚠️ O Context7 aparece configurado, mas este subagente não tem a ferramenta para chamá-lo; tudo acima vem de
  repositórios, páginas oficiais ou execução direta.

## 1. Licenças e obrigações de redistribuição

> [!NOTE]
> Levantamento de restrições, não parecer jurídico nem decisão de licença do app.

### 1a. Dicionários (`.aff/.dic`)

| Dicionário | Licença declarada | O que exige ao redistribuir num binário | Restrição sobre a licença do app | Fonte |
|---|---|---|---|---|
| **pt_BR** (VERO 3.3.0, Raimundo Moura) | "LGPLv3 **and** Mozilla Public License" — versão da MPL **não especificada**; texto ambíguo entre "e"/"ou" | Incluir aviso de copyright/licença; disponibilizar a forma-fonte (os próprios `.aff/.dic` ou link) e informar como obtê-la (LGPLv3 §4 / MPL) | Nenhuma forte se tratado como LGPLv3 (arquivo de dados separado, substituível) | `pt_BR/README_en.txt`, `README_pt_BR.txt` |
| **es_ES** (RLA-ES 2.9, Santiago Bosio) | Tripla **disjunta, à escolha**: GPL-3.0+ **ou** LGPL-3.0+ **ou** MPL-1.1+ | Escolher uma; com LGPLv3 ou MPL: aviso + texto da licença + acesso à forma-fonte | Nenhuma forte (escolher LGPL/MPL) | `es/LICENSE.md`, `es/README_hunspell_es.txt` |
| **fr_FR** (Grammalecte/Dicollecte 7.7) | **MPL 2.0** | MPL 2.0 §3.2: distribuição executável deve tornar a forma-fonte disponível e informar o destinatário; manter avisos; copyleft só por arquivo | Nenhuma (MPL é por arquivo) | `fr_FR/dictionaries/README_dict_fr.txt` |
| **de_DE_frami** (igerman98 + Baumann, 2017-01-09) | **GPL v2 ou v3** (sem "or later"); alternativa **OASIS 0.1** | OASIS 0.1 só vale para programas "whose PRIMARY format for saving documents is the Open Document Format" — **não é o nosso caso** (salvamos JSON). Logo: GPL — incluir licença, oferecer fonte correspondente | **Ponto crítico:** se a distribuição conjunta for "programa combinado" e não "agregado", a GPL alcança o app. Arquivo de dados lido em runtime, separado e substituível, tende a "agregado" pelo critério da FSF — mas a FSF diz que a linha "is a legal question" | `de/README_de_DE_frami.txt`, `de/README_extension_owner.txt`, `de/COPYING_OASIS.txt`, GPL FAQ |
| **eo** (versão 2018.01.21) | **GPLv3** (único texto de licença do pacote) | Idem GPL: licença + fonte correspondente | Idem `de_DE_frami` | `eo/license-en.txt`, `eo/description.xml` |
| en_* (já dentro do wheel pyenchant, pacote MSYS2 `hunspell-en`) | "LGPL OR custom:scowl" | Aviso/licença SCOWL | Nenhuma forte | packages.msys2.org `hunspell-en` |

### 1b. Motor e bibliotecas

| Componente | Licença | Obrigações relevantes no onedir | Fonte |
|---|---|---|---|
| pyenchant 3.3.0 (código Python) | LGPL-2.1 | LGPL-2.1 §6: aviso proeminente + cópia da licença + permitir que o usuário use versão modificada. ⚠️ Por padrão o PyInstaller **compila o pacote para dentro do PYZ** (não substituível); `module_collection_mode = 'py'`/`'pyc'` deixa os módulos como arquivos externos | `METADATA`, `licenses/LICENSE.txt`; `hooks.rst` |
| libenchant-2 2.3.4 | LGPL-2.1 | §6(b) "suitable shared library mechanism" — DLL separada no onedir atende; aviso + licença; fonte (ou oferta §6c) | API GitHub rrthomas/enchant; texto LGPL-2.1 |
| libhunspell-1.7 | Tri: MPL-1.1 / GPL-2.0+ / LGPL-2.1+ (escolher LGPL ou MPL) | Aviso + licença + fonte | `hunspell.cxx` cabeçalho; MSYS2 `hunspell` |
| libnuspell + ICU 72 | LGPL-3.0+ / licença ICU | Só necessários se o provider nuspell for mantido (ver §3) | API GitHub nuspell; MSYS2 `icu` |
| GLib 2, libintl, libiconv | LGPL-2.1+ | Aviso + licença + fonte | MSYS2 `glib2`, `gettext-runtime`, `libiconv` |
| libstdc++, libgcc_s | GPL-3.0+ **WITH GCC Runtime Library Exception 3.1** | A exceção permite distribuir em qualquer licença | MSYS2 `gcc-libs` |
| libwinpthread, pcre2 | MIT/BSD-3 | Aviso | MSYS2 |
| **DLLs extras no wheel, não carregadas** (48: `libreadline8`, `libhistory8`, `libgettextlib/src`, `libgmp`, `libmpfr`, `libpython3.10`, `tcl86`, `tk86`, `libcrypto/ssl-3`, `libsqlite3`, ICU extras…) | Mistas; **`readline` e `gettext-tools` = GPL-3.0+** | O `hook-enchant` (`collect_dynamic_libs('enchant')`) copia **todas** → redistribuiríamos GPLv3 sem usar. Removê-las elimina a obrigação e ~29 MB | MSYS2 `readline`, `gettext-tools`; `hook-enchant.py` |
| PyInstaller bootloader | GPL-2.0+ com **Bootloader Exception** | Permite distribuir o executável sob qualquer licença | `COPYING.txt` |

## 2. Build congelado (experimento)

`hello_enchant.py` define `ENCHANT_CONFIG_DIR` (antes do `import enchant`), lista providers/idiomas, verifica
palavras boas/ruins e sugestões em pt_BR, es_ES, fr_FR, de_DE e eo, grava uma PWL e enumera as DLLs carregadas;
escreve tudo em `result.json` (app `--windowed`, sem console).

```text
pyinstaller --onedir --windowed --name hello_enchant \
  --add-data "bundle\hunspell;enchant/data/mingw64/share/enchant/hunspell" hello_enchant.py
```

| Item | Resultado |
|---|---|
| Build | OK em 12 s; `hook-enchant.py` aplicado automaticamente; nenhum hook próprio |
| Execução (`exit 0`) | libenchant carregada de `_internal\enchant\data\mingw64\bin`; providers `hunspell` e `nuspell` |
| Dicionários empacotados (pt_BR, es_ES, fr_FR, de_DE) em `…\share\enchant\hunspell` | Descobertos e funcionais: 0 palavras boas rejeitadas, 0 ruins aceitas; sugestões `feitico→feitiço`, `dano→daño`, `coeur→cœur`, `Angrifswurf→Angriffswurf` |
| Dicionário "do usuário" (`eo`) em `ENCHANT_CONFIG_DIR\hunspell` | Descoberto e funcional (`chevalo→ĉevalo`) |
| PWL `DictWithPWL("pt_BR", <userdir>\pessoal-pt_BR.txt)` | `add("Hearthbound")` persistiu no arquivo |
| Carga por idioma / import | 0,05–0,22 s / 0,34 s; processo completo 1,2 s |
| Efeito colateral | Cada `Dict(lang)` **cria `<lang>.dic` e `<lang>.exc` vazios** (PWL implícita) na raiz de `ENCHANT_CONFIG_DIR` → o diretório precisa ser gravável (confirmado em `lib/dict.vala`, `with_implicit_pwl`) |

### Tamanho

| Variante | Tamanho | Arquivos | `.zip` |
|---|---|---|---|
| onedir cru (hook oficial) | **120,4 MB** | 149 | 46,8 MB |
| – dos quais `_internal\enchant` | 102,3 MB (bin 67,6 · dicionários 31,8, sendo en_* 20,2 e os 4 extras 11,6) | 129 | |
| **enxuto** (só as 10 DLLs que o hunspell carrega, sem provider nuspell/ICU, só `en_US`) | **38,8 MB** | 50 | **14,8 MB** |

A variante enxuta foi obtida apagando arquivos do onedir pronto e **rodou com resultado idêntico** (5 idiomas OK,
provider único `hunspell`). Em produção isso seria filtragem de `a.binaries`/`a.datas` no `.spec` — não testado.
Base Python/PyInstaller sem enchant ≈ 18 MB; o motor enxuto + 4 dicionários acrescenta ≈ 21 MB.

### Bug: caminho com caracteres não-ASCII

| Cenário | Dicionários do pacote | Dicionário do usuário |
|---|---|---|
| Instalação e userdir ASCII (com ou sem espaços) | ✅ | ✅ |
| Instalação em `pasta ção çé\`, userdir ASCII | ❌ todas as palavras rejeitadas, sem sugestões, "carga" 2 ms | ✅ |
| Instalação ASCII, userdir `usuário ção\` | ✅ | ❌ idem |
| userdir não-ASCII passado como **caminho curto 8.3** (`GetShortPathNameW` → `CFG_AO~1`) | — | ✅ |

- **Causa (código-fonte):** `myopen()` em `hunspell/csutil.cxx` só converte o caminho UTF-8 para wide quando
  compilado com `_MSC_VER` **e** o caminho começa com `\\?\`; senão faz `stream.open(path)` com os bytes UTF-8
  interpretados na página ANSI. O wheel é build MinGW (`data\mingw64`), e o Enchant passa caminhos UTF-8
  (`Filename.to_utf8` em `provider.vala`). Mesmo com ANSI = Windows-1252 (onde `ç` existe), falha.
- **Silencioso:** o hunspell só imprime `error: …pt_BR.aff: cannot open` no stderr C (invisível num app `--windowed`);
  `enchant.Dict()` não levanta exceção. O app teria que detectar (ex.: checar uma palavra-sentinela conhecida).
- O provider `nuspell` não serviu de alternativa: `Broker.set_ordering("pt_BR", "nuspell")` continuou devolvendo
  `hunspell` (mesmo com `nuspell\pt_BR.*` presente) — não investigado a fundo.
- O caminho curto depende de nomes 8.3 estarem habilitados no volume (não verificável sem admin aqui; neste C: estão).

## 3. Dicionários adicionados pelo usuário

- Enchant procura arquivos do usuário em `ENCHANT_CONFIG_DIR` (se definido) e, sem ele, em
  `CSIDL_LOCAL_APPDATA\enchant` (= `%LOCALAPPDATA%\enchant`) no Windows; dicionários hunspell ficam no subdiretório
  `hunspell\` — enchant(5), "FILES AND DIRECTORIES"; `enchant_get_user_config_dir()` em `provider.vala`.
- O provider hunspell busca **apenas** em `<user_config_dir>\hunspell` e nos `g_get_system_data_dirs()` (relativos às
  DLLs empacotadas) — `s_buildDictionaryDirs` em `enchant_hunspell.cpp`. Não há lista de pastas configurável.
- Sem definir `ENCHANT_CONFIG_DIR`, o app compartilharia `%LOCALAPPDATA%\enchant` com qualquer outro programa Enchant
  (PWLs `<lang>.dic/.exc` inclusive). Definindo, por ex., `%APPDATA%\i18n-reviewer\enchant`, basta o usuário soltar
  `xx_YY.aff` + `xx_YY.dic` em `…\enchant\hunspell\` — validado no experimento com `eo`.
- Convenção de nomes: a tag do Enchant é o nome do arquivo (`fr.aff` do LibreOffice precisa virar `fr_FR.aff` para
  responder a `fr_FR`; `de_DE_frami` → `de_DE`).
- Atenção à confusão de nomes: `<cfg>\pt_BR.dic` (PWL implícita, texto, uma palavra por linha) ≠
  `<cfg>\hunspell\pt_BR.dic` (dicionário Hunspell).

## Implicações para o i18n Reviewer

1. **Viável empacotar pyenchant + Hunspell no onedir** com o `hook-enchant` oficial; dicionários extras via
   `--add-data` para `enchant/data/mingw64/share/enchant/hunspell` (ou para o diretório do usuário).
2. **Enxugar no `.spec` é quase obrigatório:** manter só `libenchant-2`, `enchant_hunspell` e suas 8 dependências e
   `en_US` (se o inglês-fonte for checado): 120 → 39 MB e **remove DLLs GPLv3 não usadas** (readline, gettext-tools).
   Decidir se o provider nuspell (+ ICU, 35 MB, LGPL-3.0) fica de fora.
3. **Caminhos não-ASCII quebram silenciosamente o corretor.** Usuários brasileiros com acento no nome de usuário
   (`%APPDATA%`) ou pasta de instalação acentuada são realistas. A arquitetura precisa de uma estratégia (caminho
   curto 8.3 + fallback, instalação forçada em caminho ASCII, ou copiar dicionários para um diretório ASCII
   controlado) **e** de uma autoverificação com palavra-sentinela que avise o usuário em vez de marcar tudo errado.
4. **`ENCHANT_CONFIG_DIR` deve apontar para um diretório gravável e exclusivo do app** (Enchant cria PWLs implícitas
   lá a cada idioma aberto); é também a pasta natural para dicionários adicionados pelo usuário (`…\hunspell\`).
5. **Restrições de licença a levar para a decisão de licença/distribuição:** `de_DE_frami` e `eo` só via GPL
   (OASIS não se aplica); pt_BR/es podem ser LGPLv3/MPL, fr MPL 2.0; LGPL do pyenchant sugere coletar o pacote com
   `module_collection_mode='py'` e manter DLLs separadas; todas exigem pasta de avisos/licenças + acesso à fonte.
6. Wheel traz libenchant **2.3.4** (2022) enquanto o upstream está em v2.8.x — correções de caminho no Windows, se
   existirem upstream, não chegam sem rebuild próprio.
