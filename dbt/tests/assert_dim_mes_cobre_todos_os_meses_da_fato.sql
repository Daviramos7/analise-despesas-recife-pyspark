-- Todo (ano, mês) da staging precisa existir na dim_mes. Retornar linhas = falha.
select distinct s.ano, s.mes
from {{ ref('stg_despesas') }} s
left join {{ ref('dim_mes') }} d
  on d.ano = s.ano and d.mes = s.mes
where d.sk_mes is null
