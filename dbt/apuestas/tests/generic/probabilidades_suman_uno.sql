{#
  Las probabilidades normalizadas de un mismo mercado (partido + casa + momento)
  tienen que sumar 1. Si no suman, todo el análisis de acierto está mal.
  Devuelve los mercados que se pasan de la tolerancia (el test falla si hay filas).
#}
{% test probabilidades_suman_uno(model, column_name, agrupar_por, tolerancia=0.001) %}

select
    {{ agrupar_por | join(', ') }},
    sum({{ column_name }}) as suma
from {{ model }}
group by {{ agrupar_por | join(', ') }}
having abs(sum({{ column_name }}) - 1) > {{ tolerancia }}

{% endtest %}
