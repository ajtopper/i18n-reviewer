# 06: Glossário em 2 níveis (Global + Projeto), linter terminológico, Ctrl+Space e CSV/JSON

**What to build:** O usuário gerencia um glossário em dois níveis — **Global** (`%APPDATA%\i18n-reviewer\glossary.json`) e **Por Projeto** (`project_glossary` no `.i18nproj`, onde o projeto sobrescreve termos iguais do global) — com suporte a múltiplas traduções/flexões aceitas por idioma, termos *"Não traduzir"* (`do_not_translate`), `case_sensitive` e importação/exportação em JSON e CSV. O linter verifica consistência terminológica ignorando spans técnicos, alimenta o filtro *Inconsistências de Glossário*, oferece inserção rápida via `Ctrl+Space` no editor e permite adicionar termos a partir da tabela.

**Blocked by:** 05: Proteção de placeholders, enrichers e HTML (destaque, validação em cascata e exceções)

**Status:** done

- [x] Combina o glossário Global (`%APPDATA%\i18n-reviewer\glossary.json`) e o glossário Por Projeto (`project_glossary` no `.i18nproj`), onde entradas do projeto com o mesmo termo-fonte sobrescrevem as do global.
- [x] Diálogo de gerenciamento do glossário permite criar, editar e remover entradas (escolhendo escopo Global ou Projeto) com `term`, `source_variants` (plurais/flexões na fonte), `case_sensitive` (padrão `false`), `do_not_translate` (padrão `false`), `notes` e `translations: {lang: [preferida, ...aceitas]}`, além de importar e exportar em `glossary.json` e `CSV`.
- [x] O linter aplica antes o extrator do Ticket 05 para mascarar spans técnicos (`{x}`, `{{hbs}}`, partes técnicas de enrichers como `&Reference[Perception]`, URLs, tags HTML/XML), casando termos na base por limite de palavra (`\b`) onde o termo mais longo vence sobreposições (`"Spell Slot"` vence `"Spell"`).
- [x] Células `missing` ou vazias não disparam alerta de glossário; quando uma célula traduzida não contém nenhuma variante aceita do termo encontrado na base (ou o termo original intacto quando `do_not_translate=True`), emite **aviso** visual (faixa âmbar + detalhe no Inspector, alimentando o filtro *Inconsistências de Glossário*, nunca bloqueando o envio e aceitando *"Ignorar este alerta"*).
- [x] Pressionar `Ctrl+Space` no editor (inline ou expandido) abre popup com os termos do glossário detectados na string base e insere a tradução escolhida na posição do cursor (ou preenche a célula se vazia); a 3ª seção do menu de contexto permite aplicar a tradução preferida ou abrir *"Adicionar termo ao glossário..."* já pré-preenchido com a seleção.
- [x] O cálculo do linter roda de forma assíncrona em `QThreadPool` ao carregar/atualizar o glossário e síncronamente na célula sendo editada.
- [x] Testes `pytest` + `pytest-qt` cobrindo precedência Projeto > Global, termo mais longo vencendo sobreposição, `do_not_translate`, `case_sensitive`, variantes de flexão, mascaramento de spans técnicos, importação/exportação CSV/JSON e inserção via `Ctrl+Space`.

