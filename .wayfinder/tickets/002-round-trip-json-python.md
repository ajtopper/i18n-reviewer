---
id: 2
title: Round-trip fiel de JSON em Python
type: research
mode: AFK
status: closed
assignee: research-agent
blocked_by: []
parent: map
---

## Question

Quais técnicas e bibliotecas permitem ler um JSON, alterar valores/inserir/remover chaves e reescrevê-lo **preservando** estilo e ordem: indentação (tabs, 2/4 espaços), ordem de chaves, estrutura plana vs. aninhada vs. mista, escapes (`ensure_ascii`, `\u00e9` vs. `é`, `\/`), BOM, newline final, CRLF vs. LF?

- `json` stdlib (`object_pairs_hook`, detecção de indentação) vs. bibliotecas de edição preservando formato (ex.: `json5`, `tomlkit`-like para JSON, edição cirúrgica por spans/tokens).
- Detecção de chaves duplicadas na leitura.
- Custo/risco de cada abordagem e o que garante round-trip **byte a byte** quando nada muda.

Achados em `.wayfinder/research/002-round-trip-json-python.md`.

## Resolução

- A stdlib (`loads` → `dumps` com indent/CRLF/BOM/newline final detectados) dá bytes idênticos **só em arquivos canônicos**; normaliza `\/`, `\u00E9`, formato compacto, `"A" : ` e números (`1e5` → `100000.0`) no arquivo inteiro (medido).
- Ordem de chaves é preservada (`dict` ordenado desde 3.7); duplicadas: "última vence" silenciosamente, detectáveis com `object_pairs_hook`. BOM: `str` com BOM levanta erro, `bytes` com BOM é aceito (`utf-8-sig`).
- `json-five` (`ModelLoader`/`ModelDumper`) fez round-trip idêntico em todos os casos e permite editar valores no modelo, mas aceita JSON5 (não valida JSON estrito) e é ~650× mais lento na leitura (1,34 s para 10k chaves).
- Edição cirúrgica por spans (tree-sitter-json, ou scanner próprio sobre `json.decoder.scanstring`) garante "nada mudou → bytes idênticos" por construção e diff mínimo; custo é implementar inserção/remoção e validação.
- Opções levantadas, não decididas: a escolha fica com [Estratégia do writer com preservação de estilo](007-writer-preservacao-estilo.md).
- Achados completos: [research/002-round-trip-json-python.md](../research/002-round-trip-json-python.md).
