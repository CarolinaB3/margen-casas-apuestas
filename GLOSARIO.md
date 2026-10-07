# Glosario de negocio

Términos clave del pipeline, con su dueño y dónde se calculan.
Dueño de todos los datos: **equipo-datos**.

| Término | Definición | Dónde vive |
|---------|------------|------------|
| **Cuota** | Lo que paga la casa por cada unidad apostada si se acierta. Cuota 1,30: se apuesta 1 y se reciben 1,30. Siempre es mayor que 1. | `stg_cuotas.cuota` |
| **Momento** | `apertura` (primera cuota publicada) o `cierre` (última antes del partido). | `stg_cuotas.momento` |
| **Probabilidad implícita** | `1 / cuota`. La probabilidad que sugiere la cuota, con el margen de la casa incluido. | `int_probabilidades_implicitas.prob_implicita` |
| **Overround (margen)** | Cuánto pasa de 100 % la suma de las probabilidades implícitas de local, empate y visita. Es la ganancia de la casa. Ej.: 1,30 / 6,00 / 8,50 → 105,35 % → margen de 5,35 %. | `int_probabilidades_implicitas.overround` |
| **Probabilidad normalizada** | La implícita dividida por la suma total: suma 100 %. Es la predicción "limpia" de la casa. | `int_probabilidades_implicitas.prob_normalizada` |
| **Brier score** | Error cuadrático entre lo que predijo la casa y lo que pasó (1 si pasó, 0 si no), sumado sobre los 3 resultados. 0 = predicción perfecta; más bajo = mejor. | `mart_acierto_por_casa.brier_promedio` |
| **Cuota de cierre** | La última cuota antes del partido. Incorpora toda la información del mercado; por eso suele predecir mejor que la de apertura. | `stg_cuotas` con `momento = 'cierre'` |
| **Jornada** | Fecha del calendario de la liga (1 a 38). Sale de la API. | `stg_partidos.jornada` |
