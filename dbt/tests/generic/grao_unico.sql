{# Teste genérico: o grão (unidade, empenho, subempenho, ano, mês) não pode repetir #}
{% test grao_unico(model) %}
select unidade_codigo, empenho_numero, subempenho, ano, mes, count(*) as qtd
from {{ model }}
group by 1, 2, 3, 4, 5
having count(*) > 1
{% endtest %}
