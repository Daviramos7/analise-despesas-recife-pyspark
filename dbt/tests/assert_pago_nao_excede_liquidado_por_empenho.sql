-- No acumulado do ano, um empenho não deveria ter pago mais do que liquidou.
-- severity warn: violações reais no dado oficial, documentadas em docs/qualidade.md.
{{ config(severity='warn') }}
select unidade_codigo, empenho_numero,
       sum(valor_liquidado) as liq, sum(valor_pago) as pag
from {{ ref('stg_despesas') }}
group by 1, 2
having sum(valor_pago) > sum(valor_liquidado) + 0.01
