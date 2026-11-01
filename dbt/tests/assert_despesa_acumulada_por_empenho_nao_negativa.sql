-- Anulação num mês é legítima, mas o ACUMULADO de um empenho no ano não deveria ficar negativo.
-- Grão = empenho (unidade + número). NÃO subempenho: a folha usa 1 subempenho por mês e o
-- ajuste anual entra num subempenho novo, negativo, que é correto no conjunto do empenho.
-- severity warn: o dado oficial de 2023 tem violações reais, documentadas em docs/qualidade.md.
{{ config(severity='warn') }}
select unidade_codigo, empenho_numero,
       sum(valor_empenhado) as emp, sum(valor_liquidado) as liq, sum(valor_pago) as pag
from {{ ref('stg_despesas') }}
group by 1, 2
having sum(valor_empenhado) < 0 or sum(valor_liquidado) < 0 or sum(valor_pago) < 0
