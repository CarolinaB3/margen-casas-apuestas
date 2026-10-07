{#
  Una cuota decimal siempre es mayor que 1 (pagar menos de lo apostado no tiene sentido).
  Una cuota <= 1 indica un error de la fuente: se avisa (warn) y se descarta en la capa intermedia.
#}
{% test cuota_mayor_a_uno(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} <= 1

{% endtest %}
