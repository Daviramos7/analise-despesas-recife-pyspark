-- Staging: só renomeia e seleciona. Nenhuma regra de negócio aqui.
select
    -- grão
    ano_movimentacao                 as ano,
    mes_movimentacao                 as mes,
    unidade_codigo,
    empenho_numero,
    subempenho,

    -- unidade orçamentária
    orgao_codigo,
    orgao_nome,
    unidade_nome,

    -- classificação econômica
    categoria_economica_codigo,
    categoria_economica_nome,
    grupo_despesa_codigo,
    grupo_despesa_nome,
    modalidade_aplicacao_codigo,
    modalidade_aplicacao_nome,
    elemento_codigo,
    elemento_nome,
    subelemento_codigo,
    subelemento_nome,

    -- classificação funcional-programática
    funcao_codigo,
    funcao_nome,
    subfuncao_codigo,
    subfuncao_nome,
    programa_codigo,
    programa_nome,
    acao_codigo,
    acao_nome,

    fonte_recurso_codigo,
    fonte_recurso_nome,

    credor_codigo,
    credor_nome,

    -- atributos degenerados
    empenho_modalidade_nome          as modalidade_empenho,
    modalidade_licitacao_nome        as modalidade_licitacao,

    -- medidas (fluxo mensal; negativo = anulação/estorno)
    valor_empenhado,
    valor_liquidado,
    valor_pago
from {{ source('raw', 'despesas') }}
