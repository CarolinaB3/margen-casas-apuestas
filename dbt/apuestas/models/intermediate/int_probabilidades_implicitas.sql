-- Probabilidad implícita (1/cuota), margen (overround) y probabilidad normalizada
-- para cada mercado: un partido, una casa y un momento (apertura o cierre).

with cuotas as (

    select *
    from {{ ref('stg_cuotas') }}
    where cuota > 1  -- una cuota <= 1 es un error de la fuente (stg avisa con un test)

),

implicitas as (

    select
        *,
        1 / cuota as prob_implicita
    from cuotas

),

por_mercado as (

    select
        *,
        sum(prob_implicita) over (partition by partido_id, casa_codigo, momento) as suma_implicitas,
        count(*) over (partition by partido_id, casa_codigo, momento)            as resultados_con_cuota
    from implicitas

)

select
    partido_id,
    cuota_id,
    fecha,
    equipo_local,
    equipo_visitante,
    resultado_real,
    casa_codigo,
    momento,
    resultado,
    cuota,
    prob_implicita,
    suma_implicitas - 1               as overround,
    prob_implicita / suma_implicitas  as prob_normalizada
from por_mercado
-- Sin las 3 cuotas (local, empate, visita) no se puede calcular el margen.
where resultados_con_cuota = 3
