-- Unidade orçamentária com o órgão como atributo (drill-up unidade -> órgão).
-- Profiling: cada unidade pertence a exatamente 1 órgão e tem 1 nome.
with unidades as (
    select distinct unidade_codigo, unidade_nome, orgao_codigo, orgao_nome
    from {{ ref('stg_despesas') }}
)
select
    row_number() over (order by unidade_codigo) as sk_unidade,
    unidade_codigo,
    unidade_nome,
    orgao_codigo,
    orgao_nome
from unidades
