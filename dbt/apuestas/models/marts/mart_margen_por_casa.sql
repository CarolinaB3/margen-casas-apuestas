-- ¿Qué casa cobra más margen? Margen por casa, momento y jornada.

with mercados as (

    select distinct
        partido_id,
        casa_codigo,
        momento,
        overround
    from {{ ref('int_probabilidades_implicitas') }}

),

partidos as (

    select partido_id, jornada
    from {{ ref('stg_partidos') }}

),

casas as (

    select * from {{ ref('casas') }}

)

select
    m.casa_codigo,
    c.nombre                    as casa,
    m.momento,
    p.jornada,
    count(*)                    as partidos,
    avg(m.overround)            as margen_promedio,
    min(m.overround)            as margen_minimo,
    max(m.overround)            as margen_maximo
from mercados m
left join partidos p on p.partido_id = m.partido_id
left join casas c on c.codigo = m.casa_codigo
group by 1, 2, 3, 4
