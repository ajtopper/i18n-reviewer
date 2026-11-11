---
id: 16
title: Escolha da base e múltiplos arquivos por idioma
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: []
parent: map
---

## Question

Como o projeto define o idioma de referência e organiza pacotes com vários arquivos por idioma?

- **Base:** sempre `en` (o fallback do Foundry)? E pacotes cujo `en` aponta para outro idioma (tormenta20 → `pt-BR.json`) ou sem `en`? Usuário escolhe na criação do projeto?
- **N arquivos por `lang`:** visão unificada (as chaves de todos os arquivos numa só coluna, rastreando o arquivo de origem de cada chave) ou um arquivo por vez? Chave nova vai para qual arquivo?
- **Entradas condicionais** (`system`/`module` na entrada de `languages`): mostrar todas, filtrar?
- **Caixa do código de idioma** (`pt-BR` vs `pt-br` são distintos para o core): alertar?

> Insumo: [research 001](../research/001-formato-lang-files-foundry.md).

## Resolução

- **Escolha da base:** pré-seleciona `en` automaticamente quando existir no manifest (ou o 1º idioma disponível), permitindo ao usuário trocar o idioma base ou apontar um arquivo de referência externo (caso de módulos que só declaram a tradução, ex. `fvtt-brasil`).
- **Múltiplos arquivos por `lang`:** **visão unificada** na coluna do idioma (na ordem do manifest, rastreando o arquivo de origem de cada chave e exibindo-o no Inspector, com filtro opcional por arquivo). Novas chaves são direcionadas ao arquivo-espelho correspondente ao da base (mapeado no projeto) ou ao arquivo principal selecionado pelo usuário.
- **Entradas condicionais (`system` / `module`):** todas carregadas por padrão (com opção de desmarcar na criação do projeto), mostrando o vínculo condicional no cabeçalho/Inspector.
- **Caixa do código de idioma:** nunca modifica automaticamente o manifest; emite aviso discreto caso o código fuja do padrão BCP-47 (ex.: `pt-br`) ou haja colisões que diferem só por maiúsculas/minúsculas.
- **Fronteira de entrada:** entradas com `path` HTTP remoto são ignoradas/marcadas como não-editáveis com aviso ao criar o projeto; arquivos não declarados em `languages[]` (ex.: compêndios do Babele) ficam fora de escopo.


