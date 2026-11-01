-- A fato de receita não pode perder nem duplicar linhas/valores nos joins.
with s as (
    select count(*) as linhas, sum(valor_arrecadado) as arr, sum(valor_previsto_atualizado) as prev
    from {{ ref('stg_receitas') }}
),
f as (
    select count(*) as linhas, sum(valor_arrecadado) as arr, sum(valor_previsto_atualizado) as prev
    from {{ ref('fato_receita_movimento') }}
)
select s.*, f.* from s cross join f
where s.linhas <> f.linhas or s.arr <> f.arr or s.prev <> f.prev
