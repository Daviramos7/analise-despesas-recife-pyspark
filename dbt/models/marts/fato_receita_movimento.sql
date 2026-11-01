-- Fato: 1 linha = movimento mensal de uma natureza de receita, por unidade e fonte.
-- Medidas são FLUXOS do mês: a previsão inicial cai em janeiro e os acréscimos nos
-- meses seguintes, então somar o ano dá o valor anual sem dupla contagem.
select
    u.sk_unidade,
    m.sk_mes,
    fr.sk_fonte_recurso,
    n.sk_classif_receita,

    s.valor_previsto_inicial,
    s.valor_previsto_acrescimo,
    s.valor_previsto_atualizado,
    s.valor_arrecadado
from {{ ref('stg_receitas') }} s
join {{ ref('dim_unidade') }} u on u.unidade_codigo = s.unidade_codigo
join {{ ref('dim_mes') }} m on m.ano = s.ano and m.mes = s.mes
join {{ ref('dim_fonte_recurso') }} fr on fr.fonte_recurso_codigo = s.fonte_recurso_codigo
join {{ ref('dim_classif_receita') }} n
    on  n.categoria_receita_codigo = s.categoria_receita_codigo
    and n.origem_codigo            = s.origem_codigo
    and n.especie_codigo           = s.especie_codigo
    and n.rubrica_codigo           = s.rubrica_codigo
    and n.alinea_codigo            = s.alinea_codigo
    and n.subalinea_codigo         = s.subalinea_codigo
    and n.receita_local_codigo     = s.receita_local_codigo
