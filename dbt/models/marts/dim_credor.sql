-- Credor (fornecedor, pessoa jurídica/física ou folha).
-- O código '0' ("CREDOR NÃO INFORMADO", ~6 mil linhas de folha de pessoal) vira
-- uma linha normal marcada com credor_informado = false, em vez de null na fato.
with credores as (
    select distinct credor_codigo, credor_nome
    from {{ ref('stg_despesas') }}
)
select
    row_number() over (order by credor_codigo) as sk_credor,
    credor_codigo,
    credor_nome,
    credor_codigo <> '0'                        as credor_informado
from credores
