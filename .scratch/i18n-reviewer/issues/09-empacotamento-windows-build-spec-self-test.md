# 09: Empacotamento Windows (spec/build.spec), enxugamento de DLLs, licenças e --self-test

**What to build:** Configuração final de empacotamento e distribuição do aplicativo para Windows 64-bit com PyInstaller (`--onedir --windowed`), enxugando módulos Qt ociosos e as ~38 DLLs MSYS2/nuspell não usadas do `pyenchant`, empacotando os dicionários Hunspell (`en_US`, `pt_BR`, `es_ES`, `fr_FR`, `de_DE`) e a pasta `licenses/`, e adicionando o modo `--self-test` ao executável congelado para validar automaticamente que o build abre o Qt offscreen e carrega os 4 dicionários com palavra-sentinela sem depender do Python instalado.

**Blocked by:** 04: Writer cirúrgico por spans, backups agrupados e pipeline Enviar para Produção / Restaurar, 07: Corretor ortográfico Hunspell (pyenchant), dicionário pessoal e contorno não-ASCII no Windows, 08: Tradução completa da interface e mensagens para Inglês Internacional

**Status:** done

- [x] `requirements.txt` e `requirements-dev.txt` fixam as versões validadas para CPython 3.14.x 64-bit (`PySide6-Essentials==6.12.0`, `shiboken6==6.12.0`, `pyenchant==3.3.0`, `pyinstaller==6.22.3`, `pyinstaller-hooks-contrib==2026.10`, `pytest`, `pytest-qt`).
- [x] `spec/build.spec` compila em modo `--onedir --windowed` (`dist/i18n-reviewer/i18n-reviewer.exe`), excluindo módulos Qt não usados (`QtWebEngine*`, `QtQml`, `QtQuick`, `Qt3D*`, `QtMultimedia*`, `QtPdf*`).
- [x] `spec/build.spec` filtra os binários/dados do `enchant` para manter apenas `libenchant-2`, `enchant_hunspell` e suas 8 DLLs dependentes (removendo `nuspell`/ICU e DLLs MSYS2/GPLv3 não carregadas como `readline` e `gettext-tools`), configura `module_collection_mode={'enchant': 'py'}` (conformidade LGPL-2.1) e empacota os dicionários `en_US`, `pt_BR`, `es_ES`, `fr_FR` e `de_DE`.
- [x] O pacote gerado inclui a pasta `licenses/` com os avisos de copyright, textos de licença (LGPL-2.1, LGPL-3.0, MPL-2.0, GPL) e links/instruções para obtenção das formas-fonte dos dicionários e bibliotecas, além de script Inno Setup opcional no repositório e geração de `.zip` portátil.
- [x] O ponto de entrada suporta a flag `--self-test`, que inicializa a aplicação Qt em modo offscreen, instancia os componentes principais, carrega `pt_BR`, `es_ES`, `fr_FR` e `de_DE` no `SpellService` passando na verificação por palavra-sentinela e encerra com código `0` (ou código `!= 0` com diagnóstico em caso de falha).
- [x] O comando `pyinstaller spec/build.spec` conclui sem erros e a execução subsequente de `dist/i18n-reviewer/i18n-reviewer.exe --self-test` passa com `exit 0` ( inclusive quando executado a partir de um caminho contendo caracteres acentuados).

