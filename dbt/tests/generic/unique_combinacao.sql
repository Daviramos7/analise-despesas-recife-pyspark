{# Teste genérico: a combinação de colunas não pode repetir. #}
{% test unique_combinacao(model, colunas) %}
select {{ colunas | join(', ') }}, count(*) as qtd
from {{ model }}
group by {{ colunas | join(', ') }}
having count(*) > 1
{% endtest %}
