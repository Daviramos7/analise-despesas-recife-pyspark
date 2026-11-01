# Qualidade de dados: o que os testes encontraram

Total de testes: 86 testes de dados no dbt + 97 no pytest (limpeza, API, agente, evals, feedback, app).
Este arquivo registra **achados do dado oficial**, não bugs do pipeline.

## 1. Empenhos com acumulado anual negativo (WARN)

Teste: `dbt/tests/assert_despesa_acumulada_por_empenho_nao_negativa.sql`, no grão de empenho
(unidade + número).

| unidade | empenho | empenhado | liquidado | pago |
|---|---:|---:|---:|---:|
| 14.01 | 216 | -566,56 | -566,56 | -566,56 |
| 14.01 | 5213 | -1.612.972,56 | 486.176,72 | 486.176,72 |
| 23.01 | 864 | -200,00 | -200,00 | -200,00 |
| 16.01 | 57 | 64,20 | -64,20 | 0,00 |

Exemplo: o empenho 5213 empenhou R$ 748.570,38 em agosto e anulou R$ 2.361.542,94 em dezembro.
Hipótese provável: o empenho original é de exercício anterior e o dataset só traz 2023. Isso não
foi confirmado.

**Decisão:** é dado oficial, então não é corrigido. O teste fica em `severity: warn` e aparece em
toda execução, e esta página documenta os casos.

> **Lição de grão:** a primeira versão do teste rodava por **subempenho** e apontava 9 casos. A
> folha usa um subempenho por mês (81…92), e o ajuste anual cai num subempenho novo, negativo. Isso
> está correto no conjunto do empenho. Mudar o grão do teste eliminou os falsos positivos.

## 2. Pago maior que liquidado no ano (WARN)

Teste: `assert_pago_nao_excede_liquidado_por_empenho.sql`.

| unidade | empenho | liquidado | pago |
|---|---:|---:|---:|
| 16.01 | 57 | -64,20 | 0,00 |
| 32.01 | 66 | 0,00 | 89.000,00 |
| 48.01 | 5376 | 2.751,72 | 11.006,88 |

## 3. Regra de limpeza removida: "canonizar nome por código"

A v0.2 trocava nomes "inconsistentes" do mesmo código pelo mais frequente. A investigação mostrou
que **não eram inconsistências**: o nome depende do caminho completo da classificação. A elemento
13, por exemplo, é "OBRIGAÇÕES PATRONAIS" na modalidade 90 e "CONTRIBUIÇÕES PATRONAIS" na 91.
A regra estava rotulando errado **293 linhas**. Foi removida, e a unicidade nome-por-caminho virou
teste (`unique_combinacao` nas dimensões de classificação).

## 4. Mesma empresa com vários códigos de credor

São 572 nomes com mais de um código. O caso foi descoberto pelos **evals**: o gabarito por SQL dava
R$ 253.709.274,72 pagos à Caixa, enquanto a API (que agrupava por código) dava R$ 246.198.067,71.
A API passou a consolidar por nome. Ver `docs/schema.md`.
