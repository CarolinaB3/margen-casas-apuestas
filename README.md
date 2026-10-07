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

## Cómo levantarlo (Windows / PowerShell)

Requisitos: Docker Desktop con backend WSL2 (6 GB de RAM recomendados) y Git.

```powershell
git clone <url-del-repo>
cd margen-casas-apuestas

# 1. Crear el .env a partir de la plantilla y completar TODOS los valores
Copy-Item .env.example .env
notepad .env

# 2. Levantar todo (la primera vez tarda varios minutos: construye la imagen)
docker compose up -d --build

# 3. Verificar que los servicios estén arriba
docker compose ps
```

| Servicio | URL | Usuario |
|----------|-----|---------|
| Airflow | http://localhost:8080 | `_AIRFLOW_WWW_USER_USERNAME` del `.env` |
| MinIO (consola) | http://localhost:9001 | `MINIO_ROOT_USER` del `.env` |
| SFTP | `localhost:2222` | `SFTP_USER` del `.env` |

`airflow-init` y `minio-init` aparecen como `Exited (0)`: es lo esperado, son tareas
de una sola vez (migrar la base de Airflow y crear el bucket y el usuario de MinIO).

Para apagar: `docker compose down`. Para borrar además los datos: `docker compose down -v`.

## Tests

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install "apache-airflow==2.10.5" -r requirements.txt -r requirements-dev.txt `
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.12.txt"
ruff check .
pytest
```
