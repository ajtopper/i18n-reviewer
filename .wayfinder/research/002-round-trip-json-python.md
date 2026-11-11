# Achados — Round-trip fiel de JSON em Python

> Ticket: [Round-trip fiel de JSON em Python](../tickets/002-round-trip-json-python.md) · Data: 2026-11-11
> Escopo: levantar fatos e opções. **A escolha da estratégia é do ticket [Estratégia do writer com preservação de estilo](../tickets/007-writer-preservacao-estilo.md).**

## Fontes e método

- **Fontes primárias:** documentação oficial do módulo `json` ([docs.python.org/3/library/json.html](https://docs.python.org/3/library/json.html)), código-fonte do CPython 3.14.7 instalado (`C:\Python314\Lib\json\*.py`), RFC 8259 ([rfc-editor.org/rfc/rfc8259](https://www.rfc-editor.org/rfc/rfc8259)), repositórios e metadados de pacote das bibliotecas candidatas.
- **Experimentos descartáveis** (fora do repo) em `C:\Users\ajtop\.gemini\antigravity\brain\7362d1f6-13de-43a8-a414-89bc2c833cc8\scratch\rt002\` — `exp_stdlib.py`, `exp_libs.py`, `exp_edit.py`, `exp_edit2.py`, `exp_meta.py`. Python 3.14.7 (Windows, AMD64), json-five 1.1.2, tree-sitter 0.26.1, tree-sitter-json 0.24.8. Referenciados abaixo como **[E: arquivo]**.
- O MCP Context7 não estava invocável nesta sessão (nenhuma ferramenta de chamada MCP disponível); a documentação foi lida direto da fonte oficial e do código-fonte.

## 1. O que a especificação JSON permite (e portanto o que pode variar entre arquivos)

| Aspecto | O que o RFC 8259 diz | Fonte |
|---|---|---|
| Espaço em branco | Permitido antes/depois de qualquer token estrutural (`{ } [ ] : ,`): espaço, tab, LF, CR. | [RFC 8259 §2](https://www.rfc-editor.org/rfc/rfc8259#section-2) |
| Chaves duplicadas | Nomes "SHOULD be unique"; com duplicatas o comportamento é imprevisível entre implementações. | [RFC 8259 §4](https://www.rfc-editor.org/rfc/rfc8259#section-4) |
| Escapes | Qualquer caractere pode ser escapado como `\uXXXX`; hex aceita maiúsculas **ou** minúsculas; `\/` é escape válido. Logo `é`, `\u00e9` e `\u00E9` são o mesmo dado. | [RFC 8259 §7](https://www.rfc-editor.org/rfc/rfc8259#section-7) |
| Números | Sintaxe livre (`1e5`, `1.50`, `1.0`); a precisão é questão da implementação. | [RFC 8259 §6](https://www.rfc-editor.org/rfc/rfc8259#section-6) |
| BOM | Implementações MUST NOT adicionar BOM; parsers MAY ignorá-lo. | [RFC 8259 §8.1](https://www.rfc-editor.org/rfc/rfc8259#section-8.1) |
| Ordem de membros | Objetos são "unordered"; a ordem não é parte do dado. | [RFC 8259 §1](https://www.rfc-editor.org/rfc/rfc8259#section-1) |

Consequência: **várias grafias textuais mapeiam para o mesmo valor**, e qualquer abordagem "parse → objeto Python → serializar" perde a grafia original de tudo que não for reconstruível a partir de parâmetros globais.

## 2. `json` da stdlib

### 2.1 Leitura

- **Ordem de chaves:** `json.loads` monta `dict`; desde Python 3.7 a ordem de inserção do `dict` é garantida ([stdtypes — dict](https://docs.python.org/3/library/stdtypes.html#dict), "Changed in version 3.7"). `object_pairs_hook` recebe a lista ordenada de pares e seu retorno substitui o `dict` ([json.load](https://docs.python.org/3/library/json.html#json.load)).
- **Chaves duplicadas:** por padrão são aceitas e **vence a última** ([json — Repeated Names Within an Object](https://docs.python.org/3/library/json.html#repeated-names-within-an-object)); a mesma seção indica `object_pairs_hook` para detectá-las. Verificado: `{"A":"1","A":"2"}` → `{'A': '2'}`; um hook que levanta erro ao ver chave repetida detecta o caso **[E: exp_stdlib.py]**.
- **BOM:** a doc afirma que o desserializador levanta `ValueError` com BOM inicial ([json — Character Encodings](https://docs.python.org/3/library/json.html#character-encodings)). Na prática isso vale para **`str`**: `loads` checa `s.startswith('\ufeff')` e levanta `JSONDecodeError("Unexpected UTF-8 BOM (decode using utf-8-sig)")` (`Lib/json/__init__.py`, linha ~341). Para **`bytes`**, `detect_encoding` devolve `'utf-8-sig'` quando vê `codecs.BOM_UTF8` (`Lib/json/__init__.py`, linhas 248–255), então o BOM é aceito silenciosamente. Ambos verificados **[E: exp_stdlib.py]**.
- **Não-padrão aceito por padrão:** `NaN`, `Infinity`, `-Infinity` são aceitos na leitura ([json — Infinite and NaN Number Values](https://docs.python.org/3/library/json.html#infinite-and-nan-number-values)); verificado `{"a": NaN}` → `nan` **[E: exp_stdlib.py]**. Vírgula final é rejeitada ("Illegal trailing comma") **[E: exp_meta.py]**.
- **Offsets:** `JSONDecoder.raw_decode(s, idx)` retorna `(obj, índice_fim)` ([json.JSONDecoder.raw_decode](https://docs.python.org/3/library/json.html#json.JSONDecoder.raw_decode)). `json.decoder.scanstring(s, end)` devolve `(valor, índice_fim)` de uma string JSON (`Lib/json/decoder.py`, `py_scanstring` linha 70) — **não está na documentação pública**, é API interna.

### 2.2 Escrita

- `indent` aceita inteiro **ou string** (ex.: `"\t"`) ([json.dump](https://docs.python.org/3/library/json.html#json.dump)).
- `separators` padrão é `(', ', ': ')` sem indent e `(',', ': ')` com indent ([json.dump](https://docs.python.org/3/library/json.html#json.dump); `Lib/json/encoder.py` linhas 103 e 159). Logo `{"A":"x"}` compacto vira `{"A": "x"}` e `"A" : "x"` vira `"A": "x"` **[E: exp_stdlib.py]**.
- `ensure_ascii=True` (padrão) escapa todo não-ASCII como `\uXXXX` **minúsculo** (`'\\u{0:04x}'`, `Lib/json/encoder.py` linhas 31, 60, 67). É **global**: não há como reproduzir um arquivo que mistura `é` literal e `\u00e9`.
- Mesmo com `ensure_ascii=False`, caracteres de controle são escapados (`\u0007`), mas U+2028 sai literal (`ESCAPE`, `Lib/json/encoder.py` linha 18) **[E: exp_stdlib.py]**.
- `dumps` **nunca** emite `\/`, nunca emite BOM, nunca emite newline final, e só gera `\n` (sem CRLF) — tudo isso tem de ser reaplicado por fora **[E: exp_stdlib.py]**.
- Floats são reescritos via `float.__repr__` (`Lib/json/encoder.py` linha 227): `1e5` → `100000.0`, `1.50` → `1.5` **[E: exp_stdlib.py]**.

### 2.3 Round-trip "reserializar com estilo detectado" — resultado medido

Script: detectar BOM, CRLF/LF, newline final, string de indentação (primeiro recuo) e presença de `\uXXXX`; `loads` → `dumps(indent=…, ensure_ascii=…)` → reaplicar CRLF, newline final e BOM **[E: exp_stdlib.py]**.

| Caso | Bytes idênticos? | Diferença |
|---|---|---|
| Tabs + LF + aninhado | ✅ | — |
| 2 espaços + CRLF, plano com `.` nas chaves, sem newline final | ✅ | — |
| 4 espaços + BOM UTF-8 | ✅ | — |
| Misto plano/aninhado (`"A.B"` e `"A": {…}`) | ✅ | — |
| Objeto vazio `{}` indentado | ✅ | — |
| `\u00e9`, `\u00E9`, `\/` | ❌ | `\/` → `/`; `\u00E9` → `\u00e9` |
| Compacto `{"A":"x"}` | ❌ | separadores ganham espaço |
| `"A" : "x"` (espaço antes de `:`) | ❌ | espaço removido |
| Números `1e5`, `1.50` | ❌ | `100000.0`, `1.5` |

Conclusão factual: a stdlib dá round-trip byte a byte **apenas para arquivos "canônicos"** (formatação idêntica à que `json.dumps` produziria com algum `indent`). Qualquer desvio é normalizado no arquivo inteiro na primeira gravação.

## 3. Bibliotecas e técnicas de edição preservando formato

### 3.1 `json5` (dpranke/pyjson5)
- API espelha a stdlib (`loads` → objetos Python, `dumps` a partir deles) ([github.com/dpranke/pyjson5](https://github.com/dpranke/pyjson5)); portanto herda as mesmas perdas de formato da seção 2. Não é candidata para preservação.
- **Conflito:** instala o módulo `json5`, o mesmo nome de import de `json-five`; instalar os dois no mesmo ambiente sobrescreve um com o outro (verificado no venv de teste) **[E: exp_libs.py]**.

### 3.2 `json-five` (spyoungtech/json-five) — modelo com espaços preservados
- Projeto declara suporte a round-trip preservando comentários e espaço via modelo (`ModelLoader` / `ModelDumper`) ([github.com/spyoungtech/json-five](https://github.com/spyoungtech/json-five); [json-five.readthedocs.io](https://json-five.readthedocs.io/)). Licença Apache, Python ≥ 3.8, depende de `sly` (MIT) e `regex` (Apache-2.0 AND CNRI-Python) (metadados do pacote 1.1.2) **[E: exp_meta.py]**.
- **Medido:** round-trip idêntico em **todos** os casos, inclusive os que a stdlib falha (`\u00E9`, `\/`, compacto, `"A" : `, `1e5`, `1.50`, CRLF, tabs, BOM como `\ufeff` na `str`) **[E: exp_libs.py, exp_edit.py]**.
- **Edição:** `JSONObject.key_value_pairs` é uma *property* que recria a lista a partir de `keys`/`values` (código-fonte `json5/model.py`), então atribuir nela não tem efeito; editar exige substituir `obj.values[i]` por um novo nó `DoubleQuotedString(characters, raw_value)` copiando `wsc_before`/`wsc_after`. Funcionou e alterou só o valor **[E: exp_edit.py, exp_edit2.py]**. O `raw_value` (grafia do literal) é responsabilidade de quem edita.
- **Leniente:** aceita JSON5 (vírgula final, comentários, chaves sem aspas) — um arquivo inválido como JSON estrito seria aceito sem aviso **[E: exp_meta.py]**.
- **Duplicadas:** o loader padrão também faz "última vence" (`{"A":1,"A":2}` → `{'A': 2}`) **[E: exp_libs.py]**; no modelo, `keys` é uma lista, logo duplicatas ficam visíveis.
- **Desempenho:** arquivo sintético de 395 KB / 10 000 folhas: stdlib `loads` 0,002 s; json-five `ModelLoader` **1,34 s**, `ModelDumper` 0,05 s, round-trip idêntico **[E: exp_edit.py]**.
- Inserção de chave nova: não há API de alto nível; seria montar `KeyValuePair` + nós de espaço à mão (inferido da estrutura do modelo; não testado).

### 3.3 `tree-sitter` + `tree-sitter-json` — CST com spans em bytes
- `py-tree-sitter` expõe nós com `start_byte`/`end_byte` e `child_by_field_name` ([tree-sitter.github.io/py-tree-sitter](https://tree-sitter.github.io/py-tree-sitter/)); a gramática JSON é [tree-sitter/tree-sitter-json](https://github.com/tree-sitter/tree-sitter-json) (MIT, metadados 0.24.8) **[E: exp_meta.py]**.
- **Medido:** cada `pair` dá os bytes exatos de chave e valor (ex.: `"\u00E9"` em `(43, 51)`); substituir só o span do valor por novos bytes deixa o resto idêntico **[E: exp_libs.py]**.
- Parser é tolerante a erro: JSON inválido não lança exceção, marca `root_node.has_error = True` — precisa checar explicitamente **[E: exp_libs.py]**.
- O texto do nó é o literal cru; para obter o valor decodificado é preciso decodificar o literal (ex.: `json.loads` do span).
- Dependência binária (wheels nativos) — impacto no PyInstaller é tema do ticket de compatibilidade de stack.

### 3.4 Edição cirúrgica com scanner próprio sobre a stdlib
- Prova de conceito de ~30 linhas: percorre o texto com regex de espaços + `json.decoder.scanstring` (strings) + `raw_decode` (números/literais), gerando `(caminho, início, fim)` de cada valor string folha. Substituir só o span por `json.dumps(novo, ensure_ascii=…)` preserva todo o resto, inclusive `"A" : `, `1e5` e `\u00e9` vizinhos **[E: exp_edit.py]**.
- Quando nada muda, o texto original é gravado como está → bytes idênticos por construção.
- Custos: depende de API interna não documentada (`scanstring`) ou de reimplementar o lexer de strings; tratamento de erro, arrays e inserção/remoção ficam por conta própria.
- A grafia de **valores editados** ainda precisa de política (ex.: preservar `ensure_ascii` detectado, `\/`), pois o literal novo é gerado do zero.

### 3.5 Outros
- `tomlkit`/`ruamel.yaml` fazem round-trip de TOML/YAML, não de JSON estrito; não se aplicam diretamente. A pesquisa não encontrou um equivalente maduro de `tomlkit` para JSON estrito em Python além de `json-five` (que é JSON5).

## 4. Tabela comparativa

| Critério | stdlib reserializar c/ estilo detectado | json-five (modelo) | tree-sitter-json (spans) | scanner próprio + stdlib (spans) |
|---|---|---|---|---|
| Bytes idênticos sem mudanças | Só em arquivos canônicos | ✅ medido | ✅ (não reescreve) | ✅ (não reescreve) |
| Só linhas tocadas mudam no diff | ❌ normaliza o arquivo todo em desvios | ✅ | ✅ | ✅ |
| Tabs / 2 / 4 espaços | ✅ (indent detectado) | ✅ | ✅ | ✅ |
| CRLF, BOM, newline final | Reaplicar por fora | ✅ (BOM como `\ufeff` na str) | ✅ (bytes crus) | ✅ (texto cru) |
| `\u00E9`/`\/`/escape misto | ❌ | ✅ | ✅ | ✅ (vizinhos) |
| Números (`1e5`) | ❌ | ✅ | ✅ | ✅ |
| Inserir chave nova | Trivial (dict) | Manual no modelo | Manual (inserir texto) | Manual (inserir texto) |
| Detecta duplicadas | `object_pairs_hook` | Lista `keys` | Percorrer pares | No próprio scanner |
| Validação JSON estrito | ✅ | ❌ aceita JSON5 | ❌ tolerante (`has_error`) | ✅ (usa decoder da stdlib) |
| Desempenho (10k folhas) | 0,002 s | 1,34 s | não medido | não medido |
| Dependências | nenhuma | `json-five`, `sly`, `regex` (puro Python) | binárias (`tree-sitter`) | nenhuma (usa API interna) |
| Esforço próprio | baixo | médio | médio | médio-alto |

## 5. Implicações para o i18n Reviewer

1. A premissa "preservar exatamente estilo e ordem" **não é atendida** pela stdlib reserializando em todos os casos: desvios de formatação (escapes, compacto, espaço antes de `:`) seriam normalizados no arquivo inteiro na primeira gravação. Atende-se apenas se os arquivos reais forem canônicos — o ticket de formato dos lang files do Foundry pode medir isso.
2. "Nada mudou → bytes idênticos" só é **garantido por construção** em abordagens que não reescrevem o texto (spans: tree-sitter ou scanner próprio) ou no modelo json-five; na stdlib é garantia empírica dependente do arquivo.
3. Independentemente da abordagem, há decisões de política para o valor **editado**: grafia (`é` vs `\u00e9`, `\/`) e, para inserção, formato/posição da chave nova (plano vs. aninhado) — escopo do ticket do writer.
4. Leitura deve usar **bytes** (ou `utf-8-sig`) para não quebrar com BOM, e registrar se havia BOM para regravá-lo.
5. Chaves duplicadas: a stdlib descarta silenciosamente a primeira; detectar exige `object_pairs_hook` (ou percorrer pares no CST/modelo). Isso alimenta a validação pré-produção.
6. json-five e tree-sitter são permissivos (JSON5 / tolerante a erro): se adotados, é preciso validar também com a stdlib antes de gravar. O custo de 1,34 s/10k chaves do json-five é relevante para arquivos tipo dnd5e.
