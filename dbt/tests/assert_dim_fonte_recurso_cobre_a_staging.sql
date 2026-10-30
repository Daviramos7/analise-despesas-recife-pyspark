-- Todo código de fonte da staging precisa existir na dimensão. Retornar linhas = falha.
select distinct s.fonte_recurso_codigo
from {{ ref('stg_despesas') }} s
left join {{ ref('dim_fonte_recurso') }} d
  on d.fonte_recurso_codigo = s.fonte_recurso_codigo
where d.sk_fonte_recurso is null
