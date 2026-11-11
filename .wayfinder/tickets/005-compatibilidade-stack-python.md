---
id: 5
title: Compatibilidade da stack com o Python instalado
type: research
mode: AFK
status: closed
assignee: research-agent
blocked_by: []
parent: map
---

## Question

A máquina de desenvolvimento tem **Python 3.14.7**; a spec pede 3.11+. Quais versões de `PySide6`, `PyInstaller` e `pyspellchecker` suportam 3.14 no Windows hoje (wheels publicados, hooks do PyInstaller para PySide6), e qual deve ser a versão-alvo de Python e o conjunto de versões fixadas no `requirements.txt`?

Achados em `.wayfinder/research/005-compatibilidade-stack-python.md`.

## Resolução

- Toda a stack suporta oficialmente Python 3.14 no Windows: PySide6 ≥ 6.10.1 (wheels `cp310-abi3`), PyInstaller ≥ 6.15.0, pyspellchecker 0.9.1 (Python puro).
- Verificado de verdade em 3.14.7: hello-world PySide6 6.12.0 + pyspellchecker (pt/es/fr/de) congelado com PyInstaller 6.22.3 `--onedir --windowed` roda (~107 MB com Essentials).
- Hooks de PySide6 estão no próprio PyInstaller; **não há hook para pyspellchecker** — `--collect-data spellchecker` é obrigatório (sem ele: `ValueError ... (pt) does not exist!`).
- Usar `PySide6-Essentials` em vez do meta-pacote `PySide6` (evita Addons/WebEngine/Pdf).
- Versão-alvo: **CPython 3.14.x 64-bit**; `requirements.txt` fixado nos achados.
- pyspellchecker só tem dicionário `pt` genérico (não `pt-BR`).

Achados: [005-compatibilidade-stack-python.md](../research/005-compatibilidade-stack-python.md)
