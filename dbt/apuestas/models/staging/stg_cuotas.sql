-- Cuotas en formato largo: una fila por partido x casa x momento x resultado.
-- El CSV trae una columna por combinación (ej. B365H, B365CH); acá se "dan vuelta".
-- Solo se usa la última carga: cada archivo trae la temporada completa hasta la fecha.

{% set momentos = [('apertura', ''), ('cierre', 'C')] %}
{% set resultados = ['H', 'D', 'A'] %}
{% set combinaciones = [] %}
{% for casa in var('casas') %}
  {% for momento, sufijo in momentos %}
    {% for resultado in resultados %}
      {% do combinaciones.append((casa, momento, sufijo, resultado)) %}
    {% endfor %}
  {% endfor %}
{% endfor %}

with ultima_carga as (

    select datos
    from {{ source('raw', 'cuotas') }}
    qualify fecha_carga = max(fecha_carga) over ()

),

partidos as (

    select
        try_to_date(datos:"Date"::string)        as fecha,
        datos:"HomeTeam"::string                 as equipo_local,
        datos:"AwayTeam"::string                 as equipo_visitante,
        try_to_number(datos:"FTHG"::string)      as goles_local,
        try_to_number(datos:"FTAG"::string)      as goles_visitante,
        nullif(datos:"FTR"::string, '')          as resultado_real,
        datos
    from ultima_carga

),

largo as (

    {% for casa, momento, sufijo, resultado in combinaciones %}
    select
        fecha,
        equipo_local,
        equipo_visitante,
        goles_local,
        goles_visitante,
        resultado_real,
        '{{ casa }}'      as casa_codigo,
        '{{ momento }}'   as momento,
        '{{ resultado }}' as resultado,
        try_to_double(datos:"{{ casa }}{{ sufijo }}{{ resultado }}"::string) as cuota
    from partidos
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select
    md5(fecha || '|' || equipo_local || '|' || equipo_visitante)                as partido_id,
    md5(fecha || '|' || equipo_local || '|' || equipo_visitante || '|'
        || casa_codigo || '|' || momento || '|' || resultado)                   as cuota_id,
    fecha,
    equipo_local,
    equipo_visitante,
    goles_local,
    goles_visitante,
    resultado_real,
    casa_codigo,
    momento,
    resultado,
    cuota
from largo
where cuota is not null
