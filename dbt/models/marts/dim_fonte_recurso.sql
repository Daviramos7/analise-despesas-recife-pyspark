-- Dimensão de fonte de recurso. Uma linha por código de fonte.

with fontes as (
    select distinct
        fonte_recurso_codigo,
        fonte_recurso_nome
    from {{ ref('stg_despesas') }}
)

select
    -- sk sem significado de negócio; order by garante que é determinística
    row_number() over (order by fonte_recurso_codigo) as sk_fonte_recurso,
    fonte_recurso_codigo,
    fonte_recurso_nome
from fontes
