-- Regra contábil da fonte: previsto atualizado = previsto inicial + acréscimo, linha a linha.
select *
from {{ ref('stg_receitas') }}
where valor_previsto_atualizado <> valor_previsto_inicial + valor_previsto_acrescimo
