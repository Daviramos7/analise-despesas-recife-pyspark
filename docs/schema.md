# Schema de dados

Fonte: Portal de Dados Abertos do Recife, **despesas** e **receitas orçamentárias de 2023**.
Banco: PostgreSQL. Camadas: `raw` (carga do PySpark) → `staging` (views dbt) → `marts` (tabelas dbt).

## Regras que valem para tudo

- **Granularidade de tempo: mês.** Não existe data por dia.
- **Todas as medidas são fluxos mensais.** Somar meses dá o total do período, sem dupla contagem.
- **Negativo é legítimo.** Na despesa, é anulação/estorno. Na receita, é dedução. Nunca filtrar.
- **O nome de uma classificação depende do caminho completo de códigos**, não do código isolado.
  Exemplo na despesa: o subelemento `92.026` é "ACORDO JUDICIAL" em `3.1.90.92.026` e
  "MATERIAL ODONTOLÓGICO" em `3.3.90.92.026`. Exemplo na receita: a origem `1` é "IMPOSTOS"
  nas receitas correntes e "OPERAÇÕES DE CRÉDITO" nas de capital.
- **Valores em `numeric(18,2)`**, em reais. A API devolve os valores como string decimal, pra não perder centavo.

## Star schema (`marts`)

```
                 dim_mes ─────────────┐
                    │                 │
dim_credor ── fato_despesa_movimento  │  fato_receita_movimento ── dim_classif_receita
                │   │   │             │      │        │
dim_classif_economica  │  dim_classif_funcional      │
                    │                 │              │
                 dim_unidade ─────────┴──────────────┘   (conformadas: unidade, mês, fonte)
                 dim_fonte_recurso ──────────────────────┘
```

| Tabela | Linhas (2023) | Grão |
|---|---:|---|
| `fato_despesa_movimento` | 127.119 | movimento mensal de 1 subempenho numa unidade orçamentária |
| `fato_receita_movimento` | 5.633 | movimento mensal de 1 natureza de receita, por unidade e fonte |
| `dim_unidade` *(conformada)* | 59 | unidade orçamentária; órgão é atributo (drill-up) |
| `dim_mes` *(conformada)* | 12 | mês; `sk_mes` = AAAAMM |
| `dim_fonte_recurso` *(conformada)* | 61 | fonte de recurso (53 da despesa + 8 só da receita) |
| `dim_credor` | 8.687 | código de credor; `'0'` = "CREDOR NÃO INFORMADO" (folha) |
| `dim_classif_economica` | 415 | caminho categoria › grupo › modalidade › elemento › subelemento |
| `dim_classif_funcional` | 206 | função › subfunção › programa › ação |
| `dim_classif_receita` | 705 | categoria › origem › espécie › rubrica › alínea › subalínea › local |

**Dimensões conformadas:** unidade, mês e fonte vêm da **união** das duas fontes. Assim, despesa
e receita se cruzam pela mesma chave, que é o que permite o endpoint de comparativo.

### Medidas

| Fato | Coluna | Significado |
|---|---|---|
| despesa | `valor_empenhado` | reservado no orçamento |
| despesa | `valor_liquidado` | bem/serviço entregue e reconhecido. **É o padrão para "quanto foi gasto".** |
| despesa | `valor_pago` | dinheiro efetivamente saiu |
| receita | `valor_previsto_inicial` | previsão da LOA (cai em janeiro) |
| receita | `valor_previsto_acrescimo` | reestimativas ao longo do ano |
| receita | `valor_previsto_atualizado` | inicial + acréscimo (testado linha a linha) |
| receita | `valor_arrecadado` | efetivamente arrecadado |

### Intraorçamentárias

São operações entre órgãos da própria prefeitura: aparecem como receita (categoria `7`) num órgão
e como despesa (modalidade `91`) em outro. O comparativo receita × despesa **as exclui por padrão**,
pra não contar o mesmo real duas vezes. Com elas, a receita fica em R$ 7.882.016.730,69 e a despesa
liquidada em R$ 7.803.361.234,91. Sem elas, R$ 7.470.518.433,33 contra R$ 7.400.194.125,67.

### Credores

A fonte cadastra a mesma empresa com códigos diferentes. São 572 nomes com mais de um código; a
CAIXA ECONOMICA FEDERAL, por exemplo, tem 5. A dimensão mantém o grão por código, e a API consolida
**por nome** no ranking, devolvendo a lista de códigos junto.
