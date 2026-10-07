# Margen y acierto de las casas de apuestas

Pipeline de datos con Apache Airflow que responde, semana a semana en la Premier League,
**qué casa de apuestas cobra más margen y cuál predice mejor los resultados**.

> En construcción. Proyecto final del curso PEDE/9 Apache Airflow.

## Fuentes

| Fuente | Tipo | Qué trae |
|--------|------|----------|
| football-data.co.uk | Archivo CSV (entregado por SFTP) | Resultados y cuotas de apertura y cierre por casa |
| football-data.org API v4 | API REST | Calendario, estado del partido y equipos |

## Estructura

| Carpeta | Contenido |
|---------|-----------|
| `dags/` | DAGs de Airflow (solo orquestación) |
| `include/apuestas/` | Lógica de negocio pura, probada con pytest |
| `dbt/apuestas/` | Proyecto Dbt (staging, intermedia, marts) |
| `tests/` | Tests de pytest |
| `sftp/entrada/` | Carpeta que expone el servidor SFTP local |
| `sql/` | Scripts de Snowflake (setup y consultas de consumo) |
| `docs/` | Diagrama y documentación |
| `.github/workflows/` | CI con GitHub Actions |

## Cómo levantarlo

Pendiente: se completa con el `docker-compose.yaml`.
