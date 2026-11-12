# 02: Edição inline/expandida, ciclo de status, filtros, busca e Undo/Redo

**What to build:** O revisor navega, filtra, busca e edita traduções na tabela multilíngue com fluidez por teclado. Cada célula de destino mantém o modelo em dois eixos (`review_status` × `dirty` derivado), renderizando os badges sem sobrepor o texto. Textos curtos/médios são editados inline (`F2`) e textos longos no Editor Expandido (`Shift+F2`) lado a lado com a base; o revisor pode aprovar células sem editar (`Ctrl+Enter` avançando para a próxima pendente), reverter para o valor de produção, marcar órfãs para remoção com confirmação e desfazer/refazer qualquer operação na sessão (`Ctrl+Z` / `Ctrl+Y`), mantendo fluidez mesmo em pacotes de 10 000+ chaves.

**Blocked by:** 01: Tracer bullet — abrir pacote Foundry e exibir tabela multilíngue de leitura

**Status:** done

```python
# Máquina de estados de célula (derivada do protótipo e decisões)
@dataclass
class CellState:
    prod_value: str | None
    local_value: str | None
    marked_for_deletion: bool = False
    review_status: Literal["unreviewed", "reviewed", "stale"] = "unreviewed"
    previous_base: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.local_value is None

    @property
    def is_dirty(self) -> bool:
        return (self.local_value != self.prod_value) or self.marked_for_deletion
```

- [x] Editar uma célula para um valor diferente de `prod_value` torna `is_dirty = True` e define `review_status = "unreviewed"`; editar de volta para o texto idêntico ao `prod_value` (ou acionar *"Reverter para produção"*) limpa `is_dirty` automaticamente.
- [x] Ação explícita *"Marcar como Revisado"* (`Ctrl+Enter`, botão no Inspector ou menu de contexto) define `review_status = "reviewed"` (inclusive sem editar a célula, exceto quando `missing`) e `Ctrl+Enter` avança automaticamente para a próxima célula pendente; `Ctrl+Down` pula para a próxima célula pendente sem alterar o estado atual.
- [x] Chaves `ÓRFÃ` podem ser marcadas/desmarcadas para remoção mediante confirmação explícita (`marked_for_deletion = True`, contando como `dirty`), nunca sendo removidas automaticamente.
- [x] O delegate reserva margem superior (~18 px) para que os badges no canto superior direito (`OK` verde, `EDITADO` amarelo, `EDITADO · OK` amarelo, `STALE` lilás, `MISSING` cinza, `ÓRFÃ`) nunca sobreponham a primeira linha de texto.
- [x] A altura das linhas na tabela respeita um teto (~5 linhas / ~110 px com corte visual), com edição inline (`F2` / duplo clique via `QPlainTextEdit`) e **Editor Expandido** (`Shift+F2` ou botão no Inspector) exibindo Base × Tradução lado a lado.
- [x] Filtros na toolbar para *Todas*, *Apenas Pendentes* (`missing`, `stale`, `unreviewed` ou string vazia `""`) e *Apenas Editadas* (`is_dirty = True`), combinados com busca (`Ctrl+F`) com debounce de 150 ms sobre texto pré-normalizado e cache de altura de linha por largura de coluna.
- [x] `QUndoStack` (`Ctrl+Z` / `Ctrl+Y`) na sessão cobrindo edição de texto, mudança de `review_status`, reversão para produção e marcação/desmarcação de remoção de órfãs.
- [x] Testes `pytest` + `pytest-qt` cobrindo todas as transições de `CellState`, filtros, Undo/Redo, atalhos de navegação/revisão e responsividade com fixture sintética de 10 000 chaves.

