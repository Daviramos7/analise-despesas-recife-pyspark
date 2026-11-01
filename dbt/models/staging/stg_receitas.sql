-- Staging: só renomeia e seleciona. Valores são fluxos mensais.
select
    ano,
    mes,
    orgao_codigo, orgao_nome,
    unidade_codigo, unidade_nome,
    fonte_recurso_codigo, fonte_recurso_nome,

    -- natureza da receita (o nome depende do CAMINHO completo dos códigos)
    categoria_receita_codigo,    categoria_receita_nome,
    fonte_origem_receita_codigo  as origem_codigo,
    fonte_origem_receita_nome    as origem_nome,
    subfonte_receita_codigo      as especie_codigo,
    subfonte_receita_nome        as especie_nome,
    rubrica_receita_codigo       as rubrica_codigo,
    rubrica_receita_nome         as rubrica_nome,
    alinea_receita_codigo        as alinea_codigo,
    alinea_receita_nome          as alinea_nome,
    subalinea_receita_codigo     as subalinea_codigo,
    subalinea_receita_nome       as subalinea_nome,
    receita_local_codigo,
    receita_local_nome,

    receita_prevista             as valor_previsto_inicial,
    receita_prevista_acrescimo   as valor_previsto_acrescimo,
    receita_prevista_atualizada  as valor_previsto_atualizado,
    receita_arrecadada           as valor_arrecadado
from {{ source('raw', 'receitas') }}
