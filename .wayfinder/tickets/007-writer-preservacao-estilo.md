---
id: 7
title: Estratégia do writer com preservação de estilo
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [1, 2, 6, 15]
parent: map
---

## Question

Dado que a escrita em produção deve preservar exatamente o estilo e a ordem de chaves de cada arquivo, qual é a estratégia do `json_handler` para gravar?

- Abordagem: reserializar com estilo detectado vs. edição cirúrgica dos valores no texto original.
- Inserção de chaves novas em arquivos planos, aninhados e mistos: qual forma a chave nova assume e onde entra.
- Garantia de "nada mudou → bytes idênticos" e de que só as linhas tocadas aparecem num diff git.
- Representação interna: a tabela usa chaves pontuadas; como lidar com chaves que contêm `.` literal.
- Grafia do valor **editado**: se o arquivo usa escapes `\u00e9`, o texto novo sai escapado ou literal? E em arquivos com escape misto?
- Edição por spans resolve **alteração de valor**, não **inserção**: quando o destino tem estilo diferente da base (ex. vision-t20: `en` plano, `pt-BR` aninhado), a chave nova segue o estilo do destino ou da base, e com que indentação?

> Insumo: research 001 mostrou que core, dnd5e e daggerheart **não** são canônicos para `json.dumps` — preservação exata exige escrita por spans para esses casos.

## Resolução

- **Motor de leitura e edição (`json_handler.py`):** **scanner JSON próprio estrito em Python puro** (sem dependência binária nativa no PyInstaller) que mapeia os spans exatos de chaves, valores folha e objetos pai no texto original, aliado a `json.loads` estrito antes de gravar em produção.
- **Preservação byte a byte e diff mínimo:** arquivos sem edições não são alterados; arquivos editados têm apenas os spans modificados reescritos, preservando BOM, EOL (`CRLF`/`LF`), newline final, indentação, linhas em branco, objetos inline, separadores e ordem exata das linhas não tocadas.
- **Representação interna:** caminho lógico expandido (equivalente ao `expandObject` do Foundry) associado ao span exato da folha no arquivo (editando o span da **última ocorrência** quando houver chave duplicada, conforme [015](015-arquivos-malformados.md)).
- **Inserção de chaves novas (`missing` traduzida):** inserida na posição relativa da base ([006](006-chaves-faltantes-orfas.md)) no **estilo do próprio arquivo de destino** (plano no plano, aninhado no aninhado criando os objetos intermediários necessários; em misto, dentro do objeto pai se existir ou seguindo o estilo do bloco/vizinho), com a indentação e EOL detectados do destino (copia da base só se o destino for novo/vazio).
- **Grafia de escapes nos valores editados:** usa `ensure_ascii=True` (`\uXXXX`) apenas se o arquivo de destino inteiro escapar todos os não-ASCII; caso contrário (UTF-8 literal ou misto), usa UTF-8 literal (`ensure_ascii=False`) sem tocar os escapes das linhas não editadas.
- **Remoção de chaves órfãs:** remoção cirúrgica do par e da vírgula adjacente preservando o entorno, podando objetos pai que ficarem vazios após a remoção.


