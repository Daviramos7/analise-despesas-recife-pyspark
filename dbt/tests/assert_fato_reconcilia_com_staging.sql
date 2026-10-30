-- Reconciliação: a fato não pode perder nem duplicar linhas/valores nos joins.
-- (inner join que não casa some em silêncio: este teste pega isso)
with s as (
    select count(*) as linhas, sum(valor_empenhado) as emp,
           sum(valor_liquidado) as liq, sum(valor_pago) as pag
    from {{ ref('stg_despesas') }}
),
f as (
    select count(*) as linhas, sum(valor_empenhado) as emp,
           sum(valor_liquidado) as liq, sum(valor_pago) as pag
    from {{ ref('fato_despesa_movimento') }}
)
select s.*, f.*
from s cross join f
where s.linhas <> f.linhas or s.emp <> f.emp or s.liq <> f.liq or s.pag <> f.pag
