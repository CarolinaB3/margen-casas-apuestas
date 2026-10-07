-- Partidos de la API, con los nombres de equipo traducidos a los del CSV
-- para poder cruzar las dos fuentes por fecha + local + visitante.

with ultima_carga as (

    select datos
    from {{ source('raw', 'partidos') }}
    qualify fecha_carga = max(fecha_carga) over ()

),

partidos as (

    select
        datos:id::int                                  as partido_api_id,
        -- El CSV usa la fecha local de Inglaterra; la API, UTC.
        to_date(convert_timezone(
            'UTC', 'Europe/London',
            try_to_timestamp_ntz(datos:utcDate::string, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        ))
                                                       as fecha,
        datos:matchday::int                            as jornada,
        datos:status::string                           as estado,
        datos:homeTeam:shortName::string               as local_api,
        datos:awayTeam:shortName::string               as visitante_api,
        datos:score:fullTime:home::int                 as goles_local,
        datos:score:fullTime:away::int                 as goles_visitante
    from ultima_carga

),

equipos as (

    select * from {{ ref('equipos') }}

)

select
    md5(p.fecha || '|' || coalesce(el.nombre_csv, p.local_api) || '|'
        || coalesce(ev.nombre_csv, p.visitante_api))   as partido_id,
    p.partido_api_id,
    p.fecha,
    p.jornada,
    p.estado,
    coalesce(el.nombre_csv, p.local_api)               as equipo_local,
    coalesce(ev.nombre_csv, p.visitante_api)           as equipo_visitante,
    p.goles_local,
    p.goles_visitante
from partidos p
left join equipos el on el.nombre_api = p.local_api
left join equipos ev on ev.nombre_api = p.visitante_api
