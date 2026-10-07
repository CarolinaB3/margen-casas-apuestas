"""DAG principal: margen y acierto de las casas de apuestas (Premier League)."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.hooks.base import BaseHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.sftp.hooks.sftp import SFTPHook
from airflow.providers.sftp.sensors.sftp import SFTPSensor
from airflow.utils.task_group import TaskGroup
from cosmos import DbtTaskGroup, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import InvocationMode, LoadMode

from apuestas.cuotas import ColumnasFaltantesError, filas_a_ndjson, leer_cuotas_csv
from apuestas.football_data import (
    CredencialInvalidaError,
    FootballDataClient,
    resumir_partidos,
    temporada_de,
)
from apuestas.snowflake_carga import (
    ConfiguracionSnowflakeError,
    partidos_a_ndjson,
    sentencias_carga,
    validar_config_snowflake,
)

# Connections (definidas por variables de entorno en docker-compose.yaml).
CONN_SFTP = "sftp_proveedor"
CONN_MINIO = "minio_s3"
CONN_API = "football_data_api"
CONN_SNOWFLAKE = "snowflake_default"

BUCKET = "raw"
CARPETA_SFTP = "entrada"
ARCHIVO_CUOTAS = "E0.csv"
COMPETICION = "PL"

# dbt vive en un virtualenv aparte dentro de la imagen; en CI se pasa otra ruta.
DBT_EJECUTABLE = os.getenv("DBT_EXECUTABLE_PATH", "/home/airflow/dbt_venv/bin/dbt")
DBT_PROYECTO = Path(__file__).resolve().parent.parent / "dbt" / "apuestas"

DOC = """
### Margen y acierto de las casas de apuestas

Responde, semana a semana en la Premier League, **qué casa cobra más margen** y
**cuál predice mejor** los resultados.

1. `ingesta_archivo`: espera el CSV de cuotas en el SFTP del proveedor (sensor en
   `reschedule`), lo valida y lo guarda en MinIO `raw/cuotas/fecha=<ds>/`.
2. `ingesta_api`: baja los partidos de football-data.org (reintentos con backoff ante
   el límite de 10 consultas por minuto) a MinIO `raw/partidos/fecha=<ds>/`.
3. `carga_snowflake`: de MinIO a Snowflake con `PUT` al stage interno y `COPY INTO`
   en `RAW` (idempotente por fecha).
4. `transformacion_dbt`: Cosmos ejecuta dbt (staging, intermedia, marts) con tests
   después de cada modelo.

**Resultado:** `ANALYTICS.MART_MARGEN_POR_CASA` y `ANALYTICS.MART_ACIERTO_POR_CASA`.

**Dueño:** equipo-datos. **Fuentes:** football-data.co.uk (CSV) y football-data.org (API).
"""


@dag(
    dag_id="margen_casas_apuestas",
    description="Margen y acierto de las casas de apuestas en la Premier League",
    schedule="0 7 * * 1",  # lunes 07:00 UTC, después de la jornada del fin de semana
    start_date=datetime(2025, 8, 11),
    catchup=False,
    max_active_runs=1,
    doc_md=DOC,
    tags=["proyecto-final", "apuestas"],
    default_args={
        "owner": "equipo-datos",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
)
def margen_casas_apuestas():
    with TaskGroup("ingesta_archivo", tooltip="CSV de cuotas: SFTP -> MinIO"):
        # Espera un CSV modificado en este intervalo: así no reprocesa el de la semana pasada.
        esperar_csv = SFTPSensor(
            task_id="esperar_csv_en_sftp",
            sftp_conn_id=CONN_SFTP,
            path=f"{CARPETA_SFTP}/{ARCHIVO_CUOTAS}",
            newer_than="{{ data_interval_start }}",
            mode="reschedule",
            poke_interval=timedelta(minutes=5).total_seconds(),
            timeout=timedelta(hours=6).total_seconds(),
        )

        @task
        def subir_csv_a_minio(ds: str | None = None) -> str:
            sftp = SFTPHook(ssh_conn_id=CONN_SFTP)
            with tempfile.TemporaryDirectory() as tmp:
                local = os.path.join(tmp, ARCHIVO_CUOTAS)
                sftp.retrieve_file(f"{CARPETA_SFTP}/{ARCHIVO_CUOTAS}", local)
                try:
                    filas = leer_cuotas_csv(local)  # valida antes de guardarlo
                except ColumnasFaltantesError as error:
                    # Reintentar no arregla un archivo mal formado: falla de inmediato.
                    raise AirflowFailException(f"CSV inválido: {error}") from error
                clave = f"cuotas/fecha={ds}/{ARCHIVO_CUOTAS}"
                S3Hook(aws_conn_id=CONN_MINIO).load_file(
                    local, key=clave, bucket_name=BUCKET, replace=True
                )
            print(f"{len(filas)} partidos con cuotas -> s3://{BUCKET}/{clave}")
            return clave

        clave_cuotas = subir_csv_a_minio()
        esperar_csv >> clave_cuotas

    with TaskGroup("ingesta_api", tooltip="Partidos: API -> MinIO"):

        @task(
            retries=4,
            retry_delay=timedelta(minutes=1),
            retry_exponential_backoff=True,
            max_retry_delay=timedelta(minutes=15),
        )
        def descargar_partidos(ds: str | None = None) -> str:
            conexion = BaseHook.get_connection(CONN_API)
            url_base = f"{(conexion.host or 'https://api.football-data.org').rstrip('/')}/v4"
            try:
                datos = FootballDataClient(conexion.password, url_base=url_base).obtener_partidos(
                    COMPETICION, temporada_de(date.fromisoformat(ds))
                )
            except CredencialInvalidaError as error:
                raise AirflowFailException(str(error)) from error
            # RateLimitError y errores de red se propagan: Airflow reintenta con backoff.
            clave = f"partidos/fecha={ds}/partidos.json"
            S3Hook(aws_conn_id=CONN_MINIO).load_string(
                json.dumps(datos, ensure_ascii=False), key=clave, bucket_name=BUCKET, replace=True
            )
            print(f"Partidos por estado: {resumir_partidos(datos)} -> s3://{BUCKET}/{clave}")
            return clave

        clave_partidos = descargar_partidos()

    with TaskGroup("carga_snowflake", tooltip="MinIO -> Snowflake RAW") as carga:

        @task
        def cargar_en_snowflake(tabla: str, clave: str, ds: str | None = None) -> None:
            from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

            conexion = BaseHook.get_connection(CONN_SNOWFLAKE)
            config = {**conexion.extra_dejson, "login": conexion.login}
            try:
                validar_config_snowflake(config, config.get("private_key_file"))
            except ConfiguracionSnowflakeError as error:
                raise AirflowFailException(str(error)) from error

            contenido = S3Hook(aws_conn_id=CONN_MINIO).read_key(key=clave, bucket_name=BUCKET)
            if tabla == "cuotas":
                ndjson = filas_a_ndjson(leer_cuotas_csv(contenido.encode("utf-8")))
            else:
                ndjson = partidos_a_ndjson(json.loads(contenido))

            with tempfile.TemporaryDirectory() as tmp:
                local = os.path.join(tmp, f"{tabla}_{ds}.ndjson")
                Path(local).write_text(ndjson, encoding="utf-8")
                SnowflakeHook(snowflake_conn_id=CONN_SNOWFLAKE).run(
                    sentencias_carga(tabla, local, ds)
                )
            print(f"{ndjson.count(chr(10))} filas cargadas en RAW.{tabla.upper()} ({ds})")

        cargar_en_snowflake.override(task_id="cargar_cuotas")("cuotas", clave_cuotas)
        cargar_en_snowflake.override(task_id="cargar_partidos")("partidos", clave_partidos)

    transformacion = DbtTaskGroup(
        group_id="transformacion_dbt",
        project_config=ProjectConfig(DBT_PROYECTO),
        profile_config=ProfileConfig(
            profile_name="apuestas",
            target_name="prod",
            profiles_yml_filepath=DBT_PROYECTO / "profiles.yml",
        ),
        execution_config=ExecutionConfig(
            dbt_executable_path=DBT_EJECUTABLE,
            invocation_mode=InvocationMode.SUBPROCESS,
        ),
        render_config=RenderConfig(
            load_method=LoadMode.DBT_LS,
            dbt_executable_path=DBT_EJECUTABLE,
            invocation_mode=InvocationMode.SUBPROCESS,
            # Los tests que miran dos modelos (relationships cuotas -> partidos) van en
            # una tarea propia que espera a ambos; si no, corren antes de que exista
            # stg_partidos y fallan en la primera ejecución sobre una base vacía.
            should_detach_multiple_parents_tests=True,
        ),
        default_args={"retries": 1},
    )

    carga >> transformacion


margen_casas_apuestas()
