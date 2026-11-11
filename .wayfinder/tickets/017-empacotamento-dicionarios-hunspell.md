---
id: 17
title: Empacotamento de dicionários Hunspell
type: research
mode: AFK
status: closed
assignee: research-agent
blocked_by: [4]
parent: map
---

## Question

Se o motor for pyenchant/Hunspell, dá para distribuí-lo no executável?

- **Licenças** dos `.aff/.dic` candidatos (pt_BR VERO, es_ES, fr_FR, de_DE_frami, eo — este GPLv3) e do próprio pyenchant/libenchant/hunspell; o que cada uma exige para redistribuição num binário e que restrições impõe à licença do app.
- **Build congelado:** PyInstaller `--onedir --windowed` com pyenchant 3.3.0 + dicionários extras via `ENCHANT_CONFIG_DIR`/hunspell funciona em Python 3.14 no Windows? (`hook-enchant` oficial existe, não testado.) Tamanho resultante.
- Como o usuário poderia adicionar dicionários próprios depois (pasta em `%APPDATA%`?).

Achados em `.wayfinder/research/017-empacotamento-dicionarios-hunspell.md`.

## Resolução

- **Build congelado funciona em Python 3.14 Windows:** `pyenchant 3.3.0` + PyInstaller 6.22.3 (`--onedir --windowed`) com `hook-enchant` oficial empacota e roda `pt_BR`, `es_ES`, `fr_FR`, `de_DE` e `eo` (via `ENCHANT_CONFIG_DIR\hunspell`), inclusive com PWL em diretório gravável.
- **Tamanho e enxugamento:** o onedir cru gera **120,4 MB** (149 arquivos) e arrasta 48 DLLs MSYS2 não usadas, incluindo `readline` e `gettext-tools` (GPLv3); mantendo só as 10 DLLs do provider `hunspell` e `en_US`, cai para **38,8 MB** (50 arquivos / **14,8 MB** em `.zip`).
- **Bug silencioso em caminhos não-ASCII:** o build MinGW do `hunspell` no wheel falha silenciosamente ao abrir `.aff/.dic` em pastas com acento (rejeita todas as palavras sem lançar exceção); requer contorno (ex.: caminho curto 8.3 ou pasta ASCII controlada) e autoverificação por palavra-sentinela.
- **Restrições de licença:** `pt_BR` (LGPLv3/MPL) e `es_ES`/`fr_FR` (LGPLv3/MPL 2.0) são compatíveis com distribuição em arquivo de dados separado; `de_DE_frami` e `eo` são **GPL** (a exceção OASIS não se aplica porque o app salva JSON); `pyenchant` é LGPL-2.1 (recomenda `module_collection_mode='py'` no `.spec`).
- **Dicionários do usuário:** basta definir `ENCHANT_CONFIG_DIR` para um diretório exclusivo e gravável do app (ex.: `%APPDATA%\i18n-reviewer\enchant`), permitindo soltar `<lang>.aff`/`.dic` em `hunspell\`.
- Ver detalhes completos em [017-empacotamento-dicionarios-hunspell.md](../research/017-empacotamento-dicionarios-hunspell.md).

