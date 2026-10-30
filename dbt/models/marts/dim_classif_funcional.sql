-- Classificação funcional-programática: função > subfunção > programa > ação.
-- Responde "em quê" se gastou (Saúde, Educação...).
with classificacoes as (
    select distinct
        funcao_codigo,    funcao_nome,
        subfuncao_codigo, subfuncao_nome,
        programa_codigo,  programa_nome,
        acao_codigo,      acao_nome
    from {{ ref('stg_despesas') }}
)
select
    row_number() over (
        order by funcao_codigo, subfuncao_codigo, programa_codigo, acao_codigo
    ) as sk_classif_funcional,
    *
from classificacoes
