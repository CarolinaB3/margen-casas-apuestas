-- ¿Qué casa predice mejor? Brier score promedio por casa y momento (más bajo = mejor).

with probabilidades as (

    select *
    from {{ ref('int_probabilidades_implicitas') }}
    where resultado_real in ('H', 'D', 'A')  -- solo partidos ya jugados

),

brier_por_partido as (

    select
        partido_id,
        casa_codigo,
        momento,
        sum(power(prob_normalizada - iff(resultado = resultado_real, 1, 0), 2)) as brier
    from probabilidades
    group by 1, 2, 3

),

casas as (

    select * from {{ ref('casas') }}

)

select
    b.casa_codigo,
    c.nombre                                                    as casa,
    b.momento,
    count(*)                                                    as partidos_evaluados,
    avg(b.brier)                                                as brier_promedio,
    rank() over (partition by b.momento order by avg(b.brier))  as ranking
from brier_por_partido b
left join casas c on c.codigo = b.casa_codigo
group by 1, 2, 3
