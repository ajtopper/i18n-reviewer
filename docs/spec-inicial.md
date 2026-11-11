# Especificação Técnica Inicial: i18n Reviewer

> Documento de entrada do mapa Wayfinder (`.wayfinder/map.md`). Registro fiel da ideia original;
> decisões posteriores vivem nos tickets e **prevalecem** sobre este texto.

## 1. Stack e Ferramental

- **Linguagem & Runtime:** Python 3.11+
- **Interface Gráfica:** `PySide6` (`QTableView`, `QAbstractTableModel`, `QStyledItemDelegate`)
- **Sugestões Ortográficas:** `pyspellchecker`
- **Compilação Windows:** `pyinstaller` (configuração `--onedir --windowed`)

## 2. Arquitetura de Pastas

```text
i18n-reviewer/
├── app/
│   ├── core/
│   │   ├── json_handler.py     # Flatten e unflatten de JSONs aninhados
│   │   ├── project_manager.py  # Manipulação e serialização do .i18nproj
│   │   ├── backup_manager.py   # Criação de snapshots .bak e restauração
│   │   ├── glossary_service.py # Linter de termos e correspondências de RPG
│   │   └── spell_service.py    # Wrapper do pyspellchecker
│   ├── ui/
│   │   ├── main_window.py      # Janela principal, layouts e toolbar
│   │   ├── table_model.py      # QAbstractTableModel com suporte a multilinguagem
│   │   ├── delegates.py        # Renderizadores de célula, badges de status e menus
│   │   ├── glossary_dialog.py  # Interface para CRUD e importação de termos
│   │   └── backup_dialog.py    # Visualizador de versões e botão de rollback
│   └── main.py                 # Ponto de entrada
├── spec/
│   └── build.spec              # Configuração PyInstaller com dados do pyspellchecker
└── requirements.txt
```

## 3. Módulos do Sistema e Regras de Negócio

### Módulo A: Motor de Dados e JSON (`json_handler.py`)

- **Flattening:** converte dicionários aninhados em chaves pontuadas para preencher as linhas da tabela.
  Entrada `{"ACTOR": {"Type": {"Character": "Personagem"}}}` → chave `ACTOR.Type.Character`.
- **Unflattening:** reverte as chaves pontuadas para a árvore aninhada com `indent=2, ensure_ascii=False`.
  *(Revisto no charting: a escrita deve preservar estilo e ordem originais — ver mapa.)*

### Módulo B: Gestão de Projetos (`project_manager.py`)

- Extensão `.i18nproj` (JSON).
- Armazena metadados da sessão, caminhos absolutos/relativos dos arquivos de origem, snapshot dos textos
  originais, edições não enviadas para produção e o status de cada chave (`original`, `edited`, `reviewed`).
- Permite fechar e reabrir o app sem perder trabalho e sem alterar os arquivos do módulo até a aprovação.

### Módulo C: Pipeline de Produção e Segurança (`backup_manager.py`)

- Pasta oculta `.i18n_backups/` no diretório de destino.
- **Enviar para Produção:**
  1. Cópia íntegra do arquivo original com carimbo de data/hora (ex.: `pt-BR_2026-11-11_164500.bak`).
  2. Validação do payload JSON em memória (sintaxe, chaves corrompidas).
  3. Escrita atômica: grava `pt-BR.json.tmp` e substitui via `os.replace`.
- **Restaurar Backup:** lista os `.bak` por data/hora e reverte o arquivo de produção com um clique.

### Módulo D: Memória de Tradução e Glossário Local (`glossary_service.py`)

- Armazenamento em `glossary.json` (ex.: `"Spell Slot": "Espaço de Magia"`).
- Linter: detecta termos cadastrados na string base e alerta se a tradução não contém o equivalente.
- Ações rápidas: sugestão via `Ctrl + Space` e menu de contexto para adicionar regras a partir da tabela.

### Módulo E: Verificação Ortográfica (`spell_service.py`)

- `pyspellchecker` configurado no idioma da coluna de destino.
- Lista de palavras desconhecidas e menu de contexto com sugestões de substituição.

## 4. Design da Interface (UI/UX)

- **Toolbar:** Novo / Abrir / Salvar Projeto; filtros *Todas*, *Apenas Pendentes*, *Apenas Editadas*,
  *Inconsistências de Glossário*; botão primário **Enviar para Produção**; botão **Restaurar Backup**.
- **Tabela:** Col. 1 `KEY_PATH` (somente leitura); Col. 2 idioma de referência (somente leitura);
  Col. 3+ idiomas de destino (editáveis com duplo clique ou `F2`).
  Status: verde suave = revisado; amarelo suave = editado (não enviado); borda/ícone = alerta de glossário ou ortografia.
- **Painel lateral/rodapé:** contagem de caracteres, variáveis em chaves (`{name}`), sugestões do glossário/corretor.

## 5. Build Windows

```bash
pyinstaller --noconfirm --onedir --windowed --name "i18n-reviewer" --collect-data spellchecker --add-data "app;app" app/main.py
# ou
pyinstaller spec/build.spec
```

- `--onedir` (não `--onefile`): inicialização rápida, estabilidade com plugins Qt, dados locais acessíveis.
- `build.spec`: `datas` com `collect_data_files('spellchecker')`, `console=False`, `icon` opcional.
- Saída: `dist/i18n-reviewer/i18n-reviewer.exe`; distribuição via `.zip` ou Inno Setup.

