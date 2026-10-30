-- Classificação econômica achatada: categoria > grupo > modalidade > elemento > subelemento.
--
-- O significado de elemento/subelemento depende do CAMINHO COMPLETO dos 5 códigos:
--   3.1.90.92.026 = ACORDO JUDICIAL
--   3.3.90.92.026 = MATERIAL ODONTOLÓGICO
-- Grão = os 5 códigos. O teste unique_combinacao garante 1 nome por caminho.
with classificacoes as (
    select distinct
        categoria_economica_codigo,  categoria_economica_nome,
        grupo_despesa_codigo,        grupo_despesa_nome,
        modalidade_aplicacao_codigo, modalidade_aplicacao_nome,
        elemento_codigo,             elemento_nome,
        subelemento_codigo,          subelemento_nome
    from {{ ref('stg_despesas') }}
)
select
    row_number() over (
        order by categoria_economica_codigo, grupo_despesa_codigo,
                 modalidade_aplicacao_codigo, elemento_codigo, subelemento_codigo
    ) as sk_classif_economica,
    *
from classificacoes
