---
id: 6
title: Chaves faltantes e órfãs entre base e destinos
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [1, 16]
parent: map
---

## Question

Quando o conjunto de chaves da base (ex.: `en.json`) difere de um destino, o que a ferramenta mostra e o que ela grava?

- Chave na base e ausente no destino: aparece como linha pendente? Ao traduzir, é **criada** no arquivo de produção? Em que posição (seguindo a ordem da base)?
- Chave só no destino (órfã): exibida? marcada? removível — e só com confirmação explícita?
- Valor vazio `""` vs. chave ausente vs. valor idêntico à base: são estados distintos para o filtro "Apenas Pendentes"?
- Conflito estrutural (a base tem `A.B` como objeto e o destino tem `A.B` como string).
- **Categorias plurais:** o destino pode legitimamente ter sufixos que a base não tem (`.zero/.one/.two/.few/.many/.other` — pt-BR/es/fr têm `.many`, en não). Aceitar conforme `Intl.PluralRules` do idioma e avisar quando falta uma categoria exigida? (ver [research 003](../research/003-sintaxes-embutidas-foundry.md))

## Resolução

- **Chaves na base e ausentes no destino (`missing`):** aparecem em *Apenas Pendentes*; só são **criadas** no arquivo de produção se receberem tradução. Na escrita, são inseridas na **posição relativa da base** (logo após o vizinho/ancestral anterior da base já presente no destino, ou no topo do bloco / fim do arquivo se não houver anterior).
- **Chaves órfãs (só no destino):** exibidas na tabela com badge `ÓRFÃ` (ao final ou via filtro); **nunca** são apagadas automaticamente. O usuário pode acionar *"Remover chave(s) órfã(s)"* com confirmação explícita (entra como `dirty` de remoção até **Enviar para Produção**).
- **Categorias plurais (CLDR / `Intl.PluralRules`):** sob prefixos plurais da base (`.one`/`.other` etc.), sufixos plurais legítimos do idioma de destino (ex.: `.many` em `pt-BR`, `es`, `fr`) **não** são tratados como órfãos; categorias exigidas pelo idioma que ainda não existem no destino são sugeridas/exibidas como pendentes (`missing`), usando a forma `.other` da base como referência.
- **Distinção `missing` × `""` × igual à base:**
  - `missing`: chave ausente no arquivo destino (pendente).
  - `""` (string vazia existente no destino): mostra alerta `[vazia]` e entra em *Apenas Pendentes* (no Foundry, `""` impede o fallback para o inglês).
  - Valor igual à base: entra em *Apenas Pendentes* enquanto `unreviewed` (com marcador discreto `= base`); ao ser marcado `reviewed`, sai de Pendentes.
- **Conflito estrutural (folha × objeto no mesmo caminho entre base e destino):** exibe as linhas conflitantes como somente-leitura na célula afetada com alerta de **Conflito estrutural** e impede escrita automática de chaves que colidiriam com folha/ramo existente no arquivo de destino.


