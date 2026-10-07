-- =============================================================================
-- Consumo: las preguntas de negocio que responde el pipeline.
-- Correr en Snowsight después de un run exitoso del DAG margen_casas_apuestas.
-- =============================================================================

-- SYSADMIN hereda los permisos de PIPELINE_ROL (ver sql/setup.sql).
USE ROLE SYSADMIN;
USE WAREHOUSE APUESTAS_WH;
USE SCHEMA APUESTAS.ANALYTICS;

-- 1. ¿Qué casa cobra más margen? (promedio ponderado por partidos, en %)
SELECT
    casa,
    momento,
    SUM(partidos)                                                   AS partidos,
    ROUND(SUM(margen_promedio * partidos) / SUM(partidos) * 100, 2) AS margen_pct
FROM mart_margen_por_casa
GROUP BY casa, momento
ORDER BY momento, margen_pct DESC;

-- 2. ¿Qué casa predice mejor? (Brier score: más bajo = mejor)
SELECT
    ranking,
    casa,
    momento,
    partidos_evaluados,
    ROUND(brier_promedio, 4) AS brier_promedio
FROM mart_acierto_por_casa
ORDER BY momento, ranking;

-- 3. ¿El mercado aprende? Acierto en apertura vs. cierre por casa
SELECT
    a.casa,
    ROUND(a.brier_promedio, 4)                     AS brier_apertura,
    ROUND(c.brier_promedio, 4)                     AS brier_cierre,
    ROUND(a.brier_promedio - c.brier_promedio, 4)  AS mejora_al_cierre
FROM mart_acierto_por_casa a
JOIN mart_acierto_por_casa c
  ON c.casa_codigo = a.casa_codigo
 AND c.momento = 'cierre'
WHERE a.momento = 'apertura'
ORDER BY mejora_al_cierre DESC;

-- 4. Evolución del margen por jornada (para un gráfico de líneas)
SELECT jornada, casa, ROUND(margen_promedio * 100, 2) AS margen_pct
FROM mart_margen_por_casa
WHERE momento = 'apertura'
  AND jornada IS NOT NULL
ORDER BY jornada, casa;
