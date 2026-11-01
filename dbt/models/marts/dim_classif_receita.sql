-- Natureza da receita achatada: categoria > origem > espécie > rubrica > alínea > subalínea > local.
-- Mesma lição das despesas: o nome depende do CAMINHO (origem 1 = "Impostos" nas receitas
-- correntes e "Operações de crédito" nas de capital). Grão = os 7 códigos.
with naturezas as (
    select distinct
        categoria_receita_codigo, categoria_receita_nome,
        origem_codigo,  origem_nome,
        especie_codigo, especie_nome,
        rubrica_codigo, rubrica_nome,
        alinea_codigo,  alinea_nome,
        subalinea_codigo, subalinea_nome,
        receita_local_codigo, receita_local_nome
    from {{ ref('stg_receitas') }}
)
select
    row_number() over (
        order by categoria_receita_codigo, origem_codigo, especie_codigo, rubrica_codigo,
                 alinea_codigo, subalinea_codigo, receita_local_codigo
    ) as sk_classif_receita,
    *,
    categoria_receita_codigo = '7' as intraorcamentaria
from naturezas
