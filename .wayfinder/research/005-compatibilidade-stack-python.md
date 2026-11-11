# Achados — Compatibilidade da stack com o Python instalado

Ticket: [Compatibilidade da stack com o Python instalado](../tickets/005-compatibilidade-stack-python.md)
Data da pesquisa: 2026-11-11. Python local: **3.14.7** (`python --version` → `Python 3.14.7`, build MSC v.1944 64 bit AMD64).

> Nota de método: as fontes primárias foram a **API JSON do PyPI** (`https://pypi.org/pypi/<pacote>/json` — metadados `requires_python`, classifiers e lista de wheels), changelogs oficiais no repositório de cada projeto e a documentação do Qt for Python. O MCP Context7 não estava acessível como ferramenta nesta sessão; a documentação foi lida diretamente nas URLs oficiais citadas.

## 1. Versões atuais e suporte a Python 3.14 (Windows)

| Pacote | Última versão (upload) | `requires_python` | Classifiers 3.14 | Wheel Windows |
|---|---|---|---|---|
| PySide6 | 6.12.0 (2026-10-08) | `<3.16,>=3.10` | 3.10–3.15 | `pyside6-6.12.0-cp310-abi3-win_amd64.whl` (+ `win_arm64`) |
| PySide6-Essentials | 6.12.0 (2026-10-08) | `<3.16,>=3.10` | 3.10–3.15 | `pyside6_essentials-6.12.0-cp310-abi3-win_amd64.whl` |
| shiboken6 | 6.12.0 (2026-10-08) | `<3.16,>=3.10` | 3.10–3.15 | `shiboken6-6.12.0-cp310-abi3-win_amd64.whl` |
| pyinstaller | 6.22.3 (2026-09-12) | `<3.16,>=3.8` | 3.8–3.15 | `pyinstaller-6.22.3-py3-none-win_amd64.whl` (+ win32, win_arm64) |
| pyinstaller-hooks-contrib | 2026.10 (2026-11-10) | `>=3.8` | (sem classifiers de versão) | `py3-none-any` |
| pyspellchecker | 0.9.1 (2026-10-10) | `>=3.10` | 3.10–3.14 | `py3-none-any` (Python puro) |

Fonte: API JSON do PyPI de cada pacote — [PySide6](https://pypi.org/pypi/PySide6/json), [PySide6-Essentials](https://pypi.org/pypi/PySide6-Essentials/json), [shiboken6](https://pypi.org/pypi/shiboken6/json), [pyinstaller](https://pypi.org/pypi/pyinstaller/json), [pyinstaller-hooks-contrib](https://pypi.org/pypi/pyinstaller-hooks-contrib/json), [pyspellchecker](https://pypi.org/pypi/pyspellchecker/json).

**Observação sobre os wheels do PySide6:** são wheels `abi3` (Limited API / Stable ABI) com tag mínima `cp310` — um único wheel serve todas as versões de CPython permitidas por `requires_python`. Portanto o que limita 3.14 é o metadado `requires_python`, não a existência de um wheel por versão (PyPI, lista de arquivos acima).

### Desde quando há suporte a 3.14

- **PySide6:** 6.10.0 (2025-10-08) ainda declarava `<3.14`; o primeiro release com `<3.15` é **6.10.1 (2025-11-20)** (PyPI, histórico de releases). O changelog do 6.10.1 registra *"[PYSIDE-3147] Python 3.14 is now supported."* ([changes-6.10.1](https://code.qt.io/cgit/pyside/pyside-setup.git/plain/doc/changelogs/changes-6.10.1?h=6.10)). A linha 6.11.x exige ≥3.10 e o 6.12.0 adiciona *"[PYSIDE-3221] Initial support for Python 3.15"* ([changes-6.12.0](https://code.qt.io/cgit/pyside/pyside-setup.git/plain/doc/changelogs/changes-6.12.0?h=6.12)).
- **PyInstaller:** até 6.14.2 `requires_python` era `<3.14`; **6.15.0 (2025-08-03)** — *"Add Python 3.14 support. (#9192)"*; 6.21.0 (2026-06-13) — *"Add support for Python 3.15. (#9456)"* ([CHANGES.rst](https://github.com/pyinstaller/pyinstaller/blob/develop/doc/CHANGES.rst); PyPI, histórico).
- **pyspellchecker:** Python puro; 0.9.1 declara classifier 3.14 (PyPI).

**Mínimos para 3.14:** PySide6 ≥ 6.10.1, PyInstaller ≥ 6.15.0, pyspellchecker 0.9.x.

## 2. Hooks do PyInstaller para PySide6 e pyspellchecker

- Os hooks de **PySide6 vivem no próprio PyInstaller** (não no hooks-contrib), desde *"Add hooks for PySide6. (#5865)"* e mantidos a cada versão do Qt (ex.: 6.11.0 adiciona hook para `PySide6.QtGraphsWidgets`; 6.2.0/6.6.0 atualizam para PySide6 6.6/6.7) ([CHANGES.rst](https://github.com/pyinstaller/pyinstaller/blob/develop/doc/CHANGES.rst)).
- A página do Qt for Python sobre PyInstaller ainda contém uma seção *"Status of Qt 6 Support — As of March 2021, Qt 6 is not supported yet … using --onefile is not possible"* ([deployment-pyinstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)). **Essa nota está desatualizada**: o changelog do PyInstaller documenta os hooks desde então e o experimento abaixo congelou um app PySide6 6.12 sem `windeployqt`. O restante da página (usar venv; aviso de que um PySide6 no PATH do sistema é preferido ao do venv; `--windowed`) continua válido.
- **Não existe hook para `spellchecker`** no pyinstaller-hooks-contrib (`_pyinstaller_hooks_contrib/stdhooks/hook-spellchecker.py` → HTTP 404 no branch `master` do [repositório](https://github.com/pyinstaller/pyinstaller-hooks-contrib)). Os dicionários (`spellchecker/resources/*.json.gz`) **precisam** de `--collect-data spellchecker` (ou `collect_data_files('spellchecker')` no `.spec`) — confirmado experimentalmente (seção 4, teste C).

## 3. pyspellchecker e os idiomas do dia 1

O README oficial lista `es`, `fr`, `pt`, `de` entre os idiomas suportados ([README.rst](https://github.com/barrust/pyspellchecker/blob/master/README.rst)). Recursos empacotados no 0.9.1: `ar, de, en, es, eu, fa, fr, it, lv, nl, pt, ru` (`.json.gz`, observado no build). Os dicionários são gerados a partir de frequências do OpenSubtitles (README). **Não há dicionário `pt-BR` distinto** — só `pt` genérico.

## 4. Experimentos (venvs descartáveis, fora do repo)

Local: `C:\Users\ajtop\.gemini\antigravity\brain\7362d1f6-13de-43a8-a414-89bc2c833cc8\scratch\` (`venv-stack`, `venv-ess`, `stack-hello*`). Script `hello.py`: cria `SpellChecker` para pt/es/fr/de, abre uma `QLabel`, grava `selftest.txt` ao lado do executável após 1,5 s e sai.

| Teste | Ambiente | Resultado |
|---|---|---|
| A. `pip install PySide6 pyinstaller pyspellchecker` | Python 3.14.7, venv limpo | OK, só wheels binários. Resolveu PySide6 6.12.0 (+ **Addons, WebEngine, Pdf** 6.12.0), pyinstaller 6.22.3, hooks-contrib 2026.10, pyspellchecker 0.9.1, shiboken6 6.12.0, altgraph 0.17.5, pefile 2024.8.26, pywin32-ctypes 0.2.3, packaging 26.3, setuptools 84.2.1 |
| A'. Execução não-congelada | idem | Janela visível; `pt: traducao → tradução`, `fr: tradution → traduction`, `de: ubersetzung → übersetzung`, `es: tradusion → None` |
| B. `pyinstaller --onedir --windowed --collect-data spellchecker` com **PySide6 completo** | venv-stack | Build OK; `hello.exe` exit 0, mesma saída do A', acentos corretos. **126,4 MB / 183 arquivos** |
| B'. Mesmo build com **apenas PySide6-Essentials 6.12.0** | venv-ess | Build OK; exe exit 0, mesma saída. **106,9 MB / 173 arquivos** |
| C. Build **sem** `--collect-data spellchecker` (Essentials, `--console`) | venv-ess | Build OK, mas em runtime: `ValueError: The provided dictionary language (pt) does not exist!`; pasta `_internal\spellchecker\resources` ausente |

Conclusões dos experimentos:

- A stack inteira **funciona em Python 3.14.7 no Windows**, incluindo o build congelado `--onedir --windowed`.
- `pip install PySide6` puxa WebEngine/Addons/Pdf (downloads grandes); o app só precisa de QtWidgets/QtCore/QtGui → instalar **`PySide6-Essentials`** basta e encolhe o venv. No dist o PyInstaller já só coleta os módulos importados, então a diferença no build foi ~20 MB.
- `--collect-data spellchecker` é **obrigatório**.

## 5. Recomendação

**Versão-alvo de Python: 3.14** (testado em 3.14.7). Todas as dependências suportam oficialmente; o `requires_python` de PySide6 6.12 e PyInstaller 6.22 vai até 3.15, então há folga. O piso técnico das dependências fixadas é 3.10 (PySide6 6.11+/pyspellchecker 0.9.x), mas como o executável embute o próprio interpretador, só importa a versão usada no build: fixar build/CI oficial em **CPython 3.14.x 64-bit**. A menção "3.11+" da spec inicial fica superada.

`requirements.txt` recomendado (runtime + build, versões fixadas e verificadas no teste B'):

```text
# Runtime
PySide6-Essentials==6.12.0
shiboken6==6.12.0
pyspellchecker==0.9.1

# Build (PyInstaller --onedir --windowed --collect-data spellchecker)
pyinstaller==6.22.3
pyinstaller-hooks-contrib==2026.10
altgraph==0.17.5
pefile==2024.8.26
pywin32-ctypes==0.2.3
packaging==26.3
setuptools==84.2.1
```

> [!NOTE]
> Se se preferir separar, mover a seção "Build" para `requirements-build.txt`. Evitar `PySide6` (meta-pacote) para não arrastar `PySide6_Addons`/`PySide6_WebEngine`.
