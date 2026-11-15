# 04: Pré-compilação de glossário e validação/ortografia compartilhada em background

**What to build:** Reduzir drasticamente o tempo de CPU e a contenção de GIL/lock durante a validação em segundo plano de pacotes grandes com glossário e corretor Hunspell: adicionar cache LRU em `term_boundary_pattern`, introduzir um matcher pré-compilado de glossário (`CompiledGlossary`) com pré-filtragem rápida por substring mantendo compatibilidade com as funções públicas existentes, permitir o reuso por linha e por célula de tokens protegidos, máscaras técnicas e palavras da base já extraídos dentro do worker de validação, verificar disponibilidade do dicionário antes de mascarar texto no serviço ortográfico agrupando consultas de cache/dicionário sob uma única aquisição de lock por célula, e restringir repinturas intermediárias da viewport durante lotes em background apenas quando linhas visíveis forem afetadas.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Expressões regulares de fronteira de termo são reutilizadas via cache sem recompilação repetida a cada célula e entrada de glossário.
- [ ] O worker de validação em background compila o glossário uma única vez por execução, pré-computa os dados protegidos/glossário/ortografia da base uma única vez por linha e reutiliza os tokens da tradução entre validação, glossário e corretor ortográfico.
- [ ] Os resultados (`ValidationIssue` de tokens protegidos, glossário e ortografia, incluindo exceções ignoradas e casos-sensíveis) produzidos pelo caminho otimizado são idênticos aos das funções públicas diretas.
- [ ] O serviço de ortografia não mascara texto quando não há dicionário disponível para o idioma e reduz aquisições de lock para uma por célula avaliada.
- [ ] Testes automatizados nos seams de `ValidationRunnable`, glossário e serviço ortográfico validam equivalência exata dos diagnósticos e ganho expressivo de throughput em lotes grandes.
