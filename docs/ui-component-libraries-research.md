# Pesquisa de Bibliotecas de Componentes de UI e Modernização Visual para o `i18n-reviewer`

Este documento consolida uma pesquisa baseada em fontes primárias sobre opções de modernização da interface gráfica do **i18n-reviewer**, avaliando desde a hipótese de migração para **CustomTkinter** até bibliotecas de componentes, temas QSS, ícones e recursos nativos do **Qt 6 / PySide6**.

---

## 1. Contexto Atual da Aplicação

De acordo com [pyproject.toml](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/pyproject.toml) e [requirements.txt](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/requirements.txt), o projeto utiliza:

- **Python**: `>=3.14`
- **Framework GUI**: `PySide6-Essentials==6.12.0` e `shiboken6==6.12.0` (além de `pyenchant==3.3.0`)
- **Arquitetura de UI (`QtWidgets`)**:
  - Janela principal em `QMainWindow` ([app/ui/main_window.py](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/app/ui/main_window.py)) com `QSplitter`, `QToolBar`, `QStatusBar`, `QUndoStack` e `QThreadPool`.
  - Grade principal baseada no padrão Model/View do Qt: `QTableView` + `QAbstractTableModel` / proxy (`TranslationTableModel`, `PackageFilterProxyModel`) + `QStyledItemDelegate` customizado (`StatusCellDelegate` em [app/ui/delegates.py](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/app/ui/delegates.py)).
  - Editor de texto com destaque de tokens via `QSyntaxHighlighter` (`TokenHighlighter` em [app/ui/highlighter.py](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/app/ui/highlighter.py)).
  - Múltiplos diálogos especializados baseados em `QDialog` e `QDialogButtonBox` (`OpenPackageDialog`, `ExpandedEditorDialog`, `PublishDialog`, `BackupDialog`, `ConflictResolutionDialog`, `GlossaryDialog`, `CustomEnrichersDialog`).
  - **Estilização atual**: Não há tema global nem `QPalette`/QSS centralizado; existem apenas ajustes pontuais (ex.: `setStyleSheet` em [app/ui/conflict_dialog.py](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/app/ui/conflict_dialog.py)).

---

## 2. Análise sobre o CustomTkinter (Por que não migrar)

- **Repositório**: https://github.com/TomSchimansky/CustomTkinter
- **Licença**: MIT
- **Versão mais recente**: `6.0.0` (via PyPI / GitHub)
- **Arquitetura**: Biblioteca construída inteiramente sobre o `tkinter` padrão do Python, utilizando elementos `tkinter.Canvas` com desenho customizado para bordas arredondadas, suporte a HighDPI e alternância entre modo claro/escuro (`CTk`, `CTkToplevel`, `CTkFrame`).

### Por que a migração de PySide6 para CustomTkinter não faz sentido

1. **Reescrita total da camada de UI**: Todos os widgets, layouts, sinais/slots e diálogos de `PySide6.QtWidgets` teriam que ser reescritos do zero para `CTk*`.
2. **Ausência de tabela/modelo nativo**: O CustomTkinter **não possui widget nativo de tabela ou treeview**. A documentação e discussões oficiais apontam o uso de `ttk.Treeview` como contorno (que não herda automaticamente o tema dinâmico do CustomTkinter e sofre de inconsistências visuais/bugs de renderização) ou wrappers da comunidade como `CTkTable`. Não existe equivalente ao par `QTableView` + `QAbstractTableModel` + `QStyledItemDelegate` para virtualização de grandes volumes de linhas, ordenação/filtragem via proxy e pintura customizada de células de status.
3. **Perda de recursos críticos já implementados**:
   - `QSyntaxHighlighter` (`TokenHighlighter`): `CTkTextbox` é um wrapper sobre `tkinter.Text` voltado para texto simples; replicar destaque sintático reativo de tokens/placeholders exigiria manipulação manual de índices (`"linha.coluna"`) e `tags` do Tk, com menor desempenho em textos longos.
   - Infraestrutura integrada do Qt usada no app (`QUndoStack`, `QSplitter`, `QFileSystemWatcher`, `QThreadPool`, `QDialogButtonBox`).

**Conclusão**: Migrar para CustomTkinter representaria um retrocesso técnico e alto custo de reescrita. A modernização visual deve permanecer no ecossistema **PySide6**.

---

## 3. Tabela Comparativa das Opções para PySide6

| Opção | Tipo | Suporte a PySide6 (Py 3.14) | Licença | Esforço de Adoção | Prós | Contras |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fusion + QPalette + QStyleHints + QSS** | Nativo Qt 6 (`PySide6-Essentials`) | Sim (nativo 6.12.0) | LGPLv3 (já no projeto) | **Baixo** | Zero dependências novas; suporte nativo a `colorScheme` (Light/Dark); preserva `StatusCellDelegate` e `TokenHighlighter`. | Exige escrever/manter QSS próprio para acabamento mais refinado. |
| **qt-material** | Tema QSS drop-in | Sim | BSD-2-Clause | **Baixo** | Aplicação em 1 linha (`apply_stylesheet`); vários temas dark/light prontos; não exige reescrever widgets. | Visual genérico Material; requer testes com `StatusCellDelegate` e cores customizadas. |
| **QDarkStyleSheet** | Tema QSS drop-in | Sim (`load_stylesheet_pyside6`) | MIT (código) / CC-BY 4.0 (assets) | **Baixo** | Muito maduro e estável; cobre praticamente todos os `QtWidgets` padrão (incluindo `QTableView`). | Apenas um estilo visual (escuro/claro clássico); estética menos moderna que Fluent/WinUI 3. |
| **pyqtdarktheme** *(original)* | Tema QSS + QPalette | **Restrito** (trava Python `<3.12`) | MIT | **Baixo** *(se usar fork)* | Visual flat moderno (dark/light). | **Sem manutenção ativa** (último release v2.1.0 em dez/2022); exige fork (`pyqtdarktheme-fork`) no Python 3.14. |
| **QtAwesome** | Biblioteca de Ícones | Sim (via `QtPy`) | MIT (código) + licenças das fontes | **Baixo** | Milhares de ícones vetoriais (Font Awesome, MDI, Phosphor, Codicons) com cor dinâmica; inclui `qta-browser`. | Apenas iconografia (complementar a um tema). |
| **PySide6-Fluent-Widgets** | Biblioteca de Componentes (Fluent Design) | Sim (branch `PySide6`) | **GPLv3** (ou licença comercial paga) | **Médio–Alto** | Visual Windows 11 / Fluent muito polido; possui `TableView` compatível com `QAbstractTableModel` e `TableItemDelegate`. | Licença **GPLv3** (incompatível com distribuição fechada sem compra de licença); exige trocar classes de widgets/janelas. |
| **QMaterialWidgets** | Biblioteca de Componentes (Material 3) | Sim (`PySide6-Material-Widgets`) | **GPLv3** (ou comercial paga) | **Médio–Alto** | Componentes Material Design 3 modernos. | Licença **GPLv3**; vários componentes avançados ficam restritos à versão paga (Premium). |
| **PySide6-Frameless-Window** | Janela sem bordas / Barra de título moderna | Sim (`PySideSix-Frameless-Window`) | **LGPLv3** | **Médio** | Barra de título moderna (estilo Win11) compatível com PySide6 sob LGPLv3. | Focado apenas na moldura da janela; requer adaptação de `QMainWindow`/`QDialog`. |
| **Qt Quick / QML (`FluentWinUI3` / `Material`)** | UI Declarativa (QML) | Sim (incluso em `PySide6-Essentials`) | LGPLv3 | **Muito Alto** | Estilos nativos modernos (`Material`, `FluentWinUI3` no Qt 6.8+). | Exige reescrever toda a UI de `QtWidgets` para QML; `QSyntaxHighlighter` e `QTableView` atuais não são reaproveitados diretamente. |

---

## 4. Detalhamento das Bibliotecas e Links Diretos

### 4.1. Recursos Nativos do Qt 6 (`PySide6-Essentials==6.12.0`)

- **Documentação oficial Qt Style Hints / Color Scheme**: https://doc.qt.io/qt-6/qstylehints.html
- **Documentação `QtQuick.Controls` FluentWinUI3**: https://doc.qt.io/qt-6/qtquickcontrols-fluentwinui3.html
- **Documentação `QtQuick.Controls` Material**: https://doc.qt.io/qt-6/qtquickcontrols-material.html
- **Pacote PyPI `PySide6-Essentials`**: https://pypi.org/project/PySide6-Essentials/
- **Observações técnicas**:
  - **Qt Widgets (recomendado)**: Desde o Qt 6.5, `QGuiApplication.styleHints().colorScheme()` detecta o tema do sistema (`Light`/`Dark`) e emite `colorSchemeChanged`. A partir do Qt 6.8, `setColorScheme()` e `unsetColorScheme()` permitem alternar o esquema programaticamente. Combinado com `app.setStyle("fusion")`, um `QPalette` bem calibrado e um QSS enxuto, obtém-se tema claro/escuro consistente em todas as plataformas sem novas dependências.
  - **Qt Quick / QML**: Embora `PySide6-Essentials` já inclua `QtQml`, `QtQuick` e `QtQuickControls2` (sem necessidade de `PySide6-Addons` para controles básicos), adotá-lo no `i18n-reviewer` significaria reescrever a interface imperativa atual (`QtWidgets`).

### 4.2. QSS / Temas Drop-in (Sem reescrever widgets)

1. **qt-material**
   - **Repositório**: https://github.com/UN-GCPDS/qt-material
   - **Documentação e exemplos**: https://qt-material.readthedocs.io/
   - **Exemplos no repositório**: diretório `examples/full_features` no GitHub.
   - **Licença**: BSD-2-Clause.
   - **Uso com PySide6**: `pip install qt-material` e `apply_stylesheet(app, theme='dark_teal.xml')`.

2. **QDarkStyleSheet**
   - **Repositório**: https://github.com/ColinDuquesnoy/QDarkStyleSheet
   - **Documentação**: https://qdarkstylesheet.readthedocs.io/
   - **Galeria visual (Screenshots)**: https://qdarkstylesheet.readthedocs.io/en/latest/screenshots.html
   - **Licença**: MIT (código) e CC-BY 4.0 (imagens/ícones).
   - **Uso com PySide6**: `qdarkstyle.load_stylesheet_pyside6()`.

3. **PyQtDarkTheme (`pyqtdarktheme`)** *(não recomendado na versão original)*
   - **Repositório**: https://github.com/5yutan5/PyQtDarkTheme
   - **Status**: Última release oficial `v2.1.0` em 25/12/2022; metadados restringem Python `<3.12`, falhando na instalação padrão com Python 3.14. Caso haja interesse específico nesse visual, existe o fork comunitário `pyqtdarktheme-fork` (https://pypi.org/project/pyqtdarktheme-fork/), porém com menor garantia de longo prazo que `qt-material` ou `QDarkStyleSheet`.
   - **Licença**: MIT.

4. **PySide6-Frameless-Window** *(complementar)*
   - **Repositório (branch PySide6)**: https://github.com/zhiyiYo/PyQt-Frameless-Window/tree/PySide6
   - **PyPI**: https://pypi.org/project/PySideSix-Frameless-Window/
   - **Licença**: LGPLv3 (alinhada ao PySide6).
   - **Uso**: Substitui a barra de título nativa por uma moldura moderna integrada ao tema no Windows/macOS/Linux.

### 4.3. Bibliotecas de Ícones

- **QtAwesome**
  - **Repositório**: https://github.com/spyder-ide/qtawesome
  - **Documentação**: https://qtawesome.readthedocs.io/
  - **Explorador visual de ícones**: Comando `qta-browser` instalado junto com o pacote (`pip install qtawesome`).
  - **Licença**: MIT para o código; conjuntos de ícones inclusos seguem suas licenças originais (Font Awesome / Elusive: SIL OFL; Phosphor: MIT; Material Design Icons / Remix Icon: Apache 2.0; Codicons: CC-BY 4.0).
  - **Observação**: Suporta PySide6 via `QtPy`, permitindo trocar cores de ícones dinamicamente conforme o tema (claro/escuro).

### 4.4. Bibliotecas Completas de Componentes (Design Systems)

1. **PySide6-Fluent-Widgets**
   - **Repositório (branch PySide6)**: https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/PySide6
   - **Documentação oficial**: https://qfluentwidgets.com/
   - **Galeria visual / Demo**: diretório `examples/gallery/demo.py` no repositório (cobre botões, `TableView`, navegação, `InfoBar`, `Dialog`, `FluentWindow`, `AcrylicLabel`).
   - **PyPI**: https://pypi.org/project/PySide6-Fluent-Widgets/ (`pip install "PySide6-Fluent-Widgets[full]"`).
   - **Licença**: **GPLv3** para uso open-source/não comercial; exige compra de licença comercial para software proprietário/fechado.
   - **Compatibilidade com o projeto**: O `qfluentwidgets.TableView` herda de `QTableView` e aceita `QAbstractTableModel` + `TableItemDelegate`.

2. **QMaterialWidgets**
   - **Repositório**: https://github.com/zhiyiYo/QMaterialWidgets
   - **Exemplos no repositório**: `examples/button/demo.py` e demais pastas em `examples/`.
   - **PyPI**: `PySide6-Material-Widgets`.
   - **Licença**: **GPLv3** (não comercial) + licença comercial paga; além disso, componentes avançados ficam restritos à versão Premium.

---

## 5. Recomendação Prática por Nível de Esforço para o `i18n-reviewer`

### Nível 1 — Baixo Esforço / Alto Retorno (Recomendado para adoção imediata)
1. **Padronização visual com `Fusion` + `QPalette` + `QStyleHints.colorScheme()` + QSS modular**, ou **adoção direta de `qt-material` / `QDarkStyleSheet`**.
2. **Adicionar `QtAwesome`** para padronizar ícones da `QToolBar`, botões de ação e indicadores de validação/revisão com suporte automático a Light/Dark.
3. **Refinar o `StatusCellDelegate` ([app/ui/delegates.py](file:///c:/Users/ajtop/OneDrive/Documents/CODE/i18n-reviewer/app/ui/delegates.py))** para usar tokens de cor centralizados (adaptáveis a modo claro e escuro) e melhor espaçamento/tipografia na `QTableView`.
- *Por que escolher*: Mantém 100% da arquitetura testada (`QTableView`, `QAbstractTableModel`, `TokenHighlighter`, `QDialog`), evita problemas de licença GPLv3 e entrega melhoria visual imediata.

### Nível 2 — Médio Esforço
- Combinar **Nível 1** com **`PySide6-Frameless-Window`** (LGPLv3) para modernizar a barra de título no Windows 11, além de consolidar espaçamentos, cards/painéis (`QFrame`) e hierarquia tipográfica nos diálogos.

### Nível 3 — Alto Esforço (Apenas se o projeto aceitar licença GPLv3 ou licença comercial)
- Migrar gradualmente janelas, barras de ferramentas, diálogos e a `QTableView` para **`PySide6-Fluent-Widgets`** (`FluentWindow`, `TableView`, `InfoBar`, `CommandBar`), aproveitando que o modelo `TranslationTableModel` (`QAbstractTableModel`) continua compatível.

---

## 6. Fontes Primárias Consultadas

- CustomTkinter (GitHub & PyPI): https://github.com/TomSchimansky/CustomTkinter | https://pypi.org/project/customtkinter/
- PyQt-Fluent-Widgets / PySide6-Fluent-Widgets: https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/PySide6 | https://qfluentwidgets.com/ | https://pypi.org/project/PySide6-Fluent-Widgets/
- QMaterialWidgets: https://github.com/zhiyiYo/QMaterialWidgets
- qt-material: https://github.com/UN-GCPDS/qt-material | https://qt-material.readthedocs.io/
- QDarkStyleSheet: https://github.com/ColinDuquesnoy/QDarkStyleSheet | https://qdarkstylesheet.readthedocs.io/en/latest/screenshots.html
- PyQtDarkTheme & fork: https://github.com/5yutan5/PyQtDarkTheme | https://pypi.org/project/pyqtdarktheme-fork/
- PyQt-Frameless-Window / PySide6-Frameless-Window: https://github.com/zhiyiYo/PyQt-Frameless-Window/tree/PySide6 | https://pypi.org/project/PySideSix-Frameless-Window/
- QtAwesome: https://github.com/spyder-ide/qtawesome | https://qtawesome.readthedocs.io/
- Documentação Oficial Qt 6 & PySide6-Essentials: https://doc.qt.io/qt-6/qstylehints.html | https://doc.qt.io/qt-6/qtquickcontrols-fluentwinui3.html | https://doc.qt.io/qt-6/qtquickcontrols-material.html | https://pypi.org/project/PySide6-Essentials/
