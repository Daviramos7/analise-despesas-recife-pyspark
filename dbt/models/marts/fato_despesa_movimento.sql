-- Fato: 1 linha = movimento mensal de 1 subempenho numa unidade orçamentária.
-- Medidas são FLUXOS do mês (aditivas no tempo). Negativo = anulação/estorno.
select
    u.sk_unidade,
    c.sk_credor,
    m.sk_mes,
    e.sk_classif_economica,
    f.sk_classif_funcional,
    fr.sk_fonte_recurso,

    -- dimensões degeneradas / atributos do empenho
    s.empenho_numero,
    s.subempenho,
    s.modalidade_empenho,
    s.modalidade_licitacao,

    s.valor_empenhado,
    s.valor_liquidado,
    s.valor_pago
from {{ ref('stg_despesas') }} s
join {{ ref('dim_unidade') }} u
    on u.unidade_codigo = s.unidade_codigo
join {{ ref('dim_credor') }} c
    on c.credor_codigo = s.credor_codigo
join {{ ref('dim_mes') }} m
    on m.ano = s.ano and m.mes = s.mes
join {{ ref('dim_classif_economica') }} e
    on  e.categoria_economica_codigo  = s.categoria_economica_codigo
    and e.grupo_despesa_codigo        = s.grupo_despesa_codigo
    and e.modalidade_aplicacao_codigo = s.modalidade_aplicacao_codigo
    and e.elemento_codigo             = s.elemento_codigo
    and e.subelemento_codigo          = s.subelemento_codigo
join {{ ref('dim_classif_funcional') }} f
    on  f.funcao_codigo    = s.funcao_codigo
    and f.subfuncao_codigo = s.subfuncao_codigo
    and f.programa_codigo  = s.programa_codigo
    and f.acao_codigo      = s.acao_codigo
join {{ ref('dim_fonte_recurso') }} fr
    on fr.fonte_recurso_codigo = s.fonte_recurso_codigo
