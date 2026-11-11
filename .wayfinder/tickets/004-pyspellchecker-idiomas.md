---
id: 4
title: pyspellchecker para pt-BR, es, fr, de
type: research
mode: AFK
status: closed
assignee: research-agent
blocked_by: []
parent: map
---

## Question

O `pyspellchecker` atende revisão ortográfica em pt-BR, es, fr e de com qualidade aceitável?

- Dicionários embutidos disponíveis, origem e tamanho; o dicionário `pt` mistura pt-PT e pt-BR? Exemplos de falsos positivos/negativos típicos (acentuação pós-Acordo, "fato/facto", "ação/acção").
- Carga de dicionários customizados/pessoais, frequência de palavras, adição em runtime, persistência.
- Tokenização: como lidar com hífens, apóstrofos (fr: `l'arme`), maiúsculas, palavras com acento, e tokens que devem ser ignorados (placeholders, termos do glossário).
- Desempenho (tempo de carga, `candidates()` em textos longos) e empacotamento no PyInstaller (`collect_data_files('spellchecker')`).
- Alternativas caso a qualidade em pt-BR seja insuficiente (Hunspell via `spylls`/`cyhunspell`, dicionários LibreOffice VERO) — custo de troca.

Achados em `.wayfinder/research/004-pyspellchecker-idiomas.md`.

## Resolução

- **Não atende.** O `pt` do pyspellchecker é uma lista **pt-PT** (rejeita `ônibus`, `econômico`, `contato`, `registro`, `percepção`); o `es` não tem flexões (`puede`, `horas`, `hay` desconhecidas); `fr` marca toda elisão (`l'arme`); `de` marca compostos; não existe `eo`.
- Nas traduções reais do Hearthbound: pyspellchecker marca **4,4%** (pt-BR) e **24,5%** (es) das ocorrências; Hunspell marca **0,7%** e **2,1%**, quase só nomes próprios, inglês e siglas.
- **Motor recomendado: `pyenchant` (provider hunspell, wheel win_amd64 com DLLs) + dicionários LibreOffice** (`pt_BR` VERO, `es_ES`, `fr_FR`, `de_DE_frami`, `eo`), atrás de uma interface própria; PWL nativo resolve o dicionário pessoal; existe hook oficial do PyInstaller.
- Descartados: `spylls` (sugestões levam 45–107 s), `cyhunspell` (sem wheel após cp39), `hunspell`/`phunspell` (só sdist).
- Tokenização e mascaramento (placeholders, `@UUID[...]`, HTML, glossário, siglas) ficam por conta do app em qualquer motor.
- Achados completos: [004-pyspellchecker-idiomas.md](../research/004-pyspellchecker-idiomas.md)
