-- Dimensão CONFORMADA: compartilhada por despesa e receita.
-- Unidade orçamentária com o órgão como atributo (drill-up unidade -> órgão).
with unidades as (
    select unidade_codigo, unidade_nome, orgao_codigo, orgao_nome from {{ ref('stg_despesas') }}
    union
    select unidade_codigo, unidade_nome, orgao_codigo, orgao_nome from {{ ref('stg_receitas') }}
)
select
    row_number() over (order by unidade_codigo) as sk_unidade,
    unidade_codigo,
    unidade_nome,
    orgao_codigo,
    orgao_nome
from unidades
