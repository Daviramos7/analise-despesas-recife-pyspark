-- Dimensão de tempo no grão de MÊS (o dado de origem não tem dia).
-- Uma linha por (ano, mês) presente na staging.

with meses as (
    select distinct ano, mes
    from {{ ref('stg_despesas') }}
)

select
    ano * 100 + mes                                   as sk_mes,
    make_date(ano, mes, 1)                            as data_inicio_mes,
    ano,
    mes,
    ((mes - 1) / 3) + 1                               as trimestre,  -- divisão inteira
    case when mes <= 6 then 1 else 2 end              as semestre,
    -- CASE em vez de to_char(): não depende do locale do servidor
    case mes
        when 1  then 'Janeiro'   when 2  then 'Fevereiro' when 3  then 'Março'
        when 4  then 'Abril'     when 5  then 'Maio'      when 6  then 'Junho'
        when 7  then 'Julho'     when 8  then 'Agosto'    when 9  then 'Setembro'
        when 10 then 'Outubro'   when 11 then 'Novembro'  when 12 then 'Dezembro'
    end                                               as nome_mes,
    ano::text || '-' || lpad(mes::text, 2, '0')       as ano_mes
from meses
