---
id: 15
title: Política para arquivos de idioma malformados
type: grilling
mode: HITL
status: closed
assignee: coordinator
blocked_by: []
parent: map
---

## Question

O que a ferramenta faz ao abrir (e ao enviar para produção) arquivos que o próprio Foundry já trata mal?

- **Chaves duplicadas** (caso real: tormenta20 `pt-BR`): o Foundry usa a última. Bloquear, alertar, mostrar ambas? Qual ocorrência o writer edita?
- **Folha seguida de ramo com o mesmo prefixo** (`"A.B": "x"` e depois `"A.B.C": "y"`): o Foundry **descarta o arquivo inteiro**. Bloquear a abertura, alertar, oferecer correção?
- **Conflito entre arquivos do mesmo `lang`** no mesmo pacote (mesma chave em dois arquivos — o último vence).
- A ferramenta pode **corrigir** esses defeitos (alterando o arquivo além das edições do usuário) ou só apontar?

> Insumo: [research 001](../research/001-formato-lang-files-foundry.md).

## Resolução

- **Princípio geral:** o app **nunca** reestrutura ou apaga chaves malformadas automaticamente fora das edições do usuário; ele diagnostica, aponta linhas exatas e espelha o que o Foundry realmente lê.
- **Chaves duplicadas no mesmo arquivo:** abre normalmente apontando as linhas duplicadas; exibe e edita a **última ocorrência** (a efetiva no `JSON.parse`/Foundry); alerta com confirmação ao Enviar para Produção sem apagar a ocorrência antiga sozinho.
- **Erros fatais no Foundry (JSON com erro de sintaxe ou folha antes de ramo `"A": "str"` antes de `"A.B": "x"`):** o arquivo abre em modo diagnóstico/somente-leitura exibindo erro e número de linha, **bloqueando Enviar para Produção** para aquele arquivo até ser corrigido (não trava os demais arquivos do projeto).
- **Sobrescrita silenciosa no `expandObject` (`"A.C"` antes de `"A": {...}` ou ramo seguido de folha `"A"`):** abre apontando chaves/linhas que serão descartadas pelo Foundry com alerta antes de enviar.
- **Conflito entre múltiplos arquivos do mesmo `lang`:** permite abrir e editar normalmente, sinalizando a colisão e qual arquivo vence na ordem do manifest (sem mover chaves entre arquivos).
- **Valores não-string (`null`, número, booleano, array):** exibidos como **somente-leitura** com tag `[não-string]` (e alerta quando a base espera uma string).


