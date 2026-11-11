---
id: 12
title: Política do corretor ortográfico
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: [4, 10, 17]
parent: map
---

## Question

Dados os limites reais do `pyspellchecker`, como o corretor se comporta?

- Mantém `pyspellchecker` ou troca de motor para atingir pt-BR/es/fr/de com qualidade? *(Research 004 recomenda pyenchant/Hunspell + dicionários LibreOffice; a spec inicial fixava pyspellchecker — confirmar a troca.)*
- Idiomas além do dia 1 (ex.: `eo` do hearthbound): suportar qualquer dicionário Hunspell que o usuário instalar?
- Mapeamento código do Foundry (`pt-BR`, `es`, `fr`, `de`) → dicionário; idioma sem dicionário → coluna sem corretor.
- Dicionário pessoal: global ou por projeto; "Adicionar ao dicionário" no menu de contexto.
- Tokens ignorados automaticamente: placeholders/enrichers/HTML (da política de placeholders), termos do glossário, palavras em MAIÚSCULAS, números, tokens de ≤2 letras (h/m/ft), URLs, palavras idênticas à string base. *(Research 004: o ruído restante do Hunspell no hearthbound vem quase todo daqui.)* Inclui spans técnicos que parecem texto (`&Reference[Perception]`, `rule="Difficult Terrain"`, slugs do pf2e): só rótulos são checados.
- Quando verificar: ao editar, ao abrir o projeto (todas as células), sob demanda — custo em arquivos grandes.

## Resolução

- **Motor (substitui `pyspellchecker` da spec inicial):** `pyenchant` (provider Hunspell) atrás de uma interface própria (`SpellService`: `check`, `suggest`, `add_personal`), mantendo desacoplamento caso o motor mude no futuro.
- **Dicionários empacotados e extensibilidade:** empacotar `pt_BR` (VERO), `es_ES`, `fr_FR` (Grammalecte) e `de_DE` (`de_DE_frami`) como arquivos `.aff/.dic` separados (com respectivos avisos/licenças), além de suportar qualquer `.aff/.dic` adicional colocado pelo usuário em `%APPDATA%\i18n-reviewer\enchant\hunspell\` (via `ENCHANT_CONFIG_DIR`).
- **Mapeamento e idioma sem dicionário:** mapeamento automático tag Foundry → Enchant (`pt-BR` → `pt_BR`, `es` → `es_ES`, `fr` → `fr_FR`, `de` → `de_DE`, com fallback por prefixo do idioma). Se não houver dicionário disponível (ex.: `eo` sem arquivo instalado), o corretor fica desligado na coluna com aviso discreto indicando a pasta de dicionários do usuário.
- **Dicionário pessoal:** arquivo PWL **global** por idioma em `ENCHANT_CONFIG_DIR` (alimentado por *"Adicionar ao dicionário"* no menu de contexto), combinado com o **glossário do projeto** para termos específicos do módulo.
- **Tokenização e tokens ignorados:**
  - Reutiliza o extrator do [ticket 010](010-politica-placeholders.md) para mascarar spans técnicos (`{x}`, `{{hbs}}`, HTML/XML, URLs e partes técnicas de enrichers como `&Reference[Perception]` ou slugs), checando apenas texto natural e rótulos traduzíveis.
  - Ignora também: termos do glossário ativo (originais e traduções aceitas), palavras totalmente em MAIÚSCULAS, números/fórmulas de dados (`1d20`), tokens com ≤ 2 letras (`h`, `m`, `ft`) e palavras idênticas à string base.
  - Preserva palavras com hífen (`guarda-costas`, `peut-être`) e apóstrofos (`l'arme`) na consulta ao Hunspell.
- **Desempenho e severidade:** `check()` leve em tempo real ao editar e em lote assíncrono/lazy para o projeto; `suggest()` calculado **apenas sob demanda** no menu de contexto. Erro ortográfico é sempre **aviso visual** (nunca bloqueia Enviar para Produção).
- **Confiabilidade no Windows:** contorno para o bug de caminhos não-ASCII do Hunspell MinGW (caminho curto 8.3 ou pasta ASCII controlada) + autoverificação com palavra-sentinela na carga do dicionário para nunca falhar em silêncio.


