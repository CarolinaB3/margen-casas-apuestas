"""Estructura del DAG principal: que cumpla lo que pide el enunciado (sección 5.1)."""

from datetime import timedelta
from pathlib import Path

import pytest
from airflow.models import DagBag
from airflow.providers.sftp.sensors.sftp import SFTPSensor

CARPETA_DAGS = Path(__file__).resolve().parent.parent / "dags"


@pytest.fixture(scope="module")
def dag():
    bolsa = DagBag(dag_folder=str(CARPETA_DAGS), include_examples=False)
    assert bolsa.import_errors == {}
    return bolsa.get_dag("margen_casas_apuestas")


def test_schedule_semanal_sin_catchup(dag):
    assert dag.schedule_interval == "0 7 * * 1"
    assert dag.catchup is False


def test_tiene_los_task_groups_del_pipeline(dag):
    grupos = set(dag.task_group.children)
    assert {"ingesta_archivo", "ingesta_api", "carga_snowflake", "transformacion_dbt"} <= grupos


def test_sensor_sftp_en_modo_reschedule(dag):
    sensor = dag.get_task("ingesta_archivo.esperar_csv_en_sftp")
    assert isinstance(sensor, SFTPSensor)
    assert sensor.mode == "reschedule"


def test_api_reintenta_con_backoff_exponencial(dag):
    tarea = dag.get_task("ingesta_api.descargar_partidos")
    assert tarea.retries >= 3
    assert tarea.retry_exponential_backoff is True
    assert tarea.max_retry_delay <= timedelta(minutes=15)


def test_todas_las_tareas_tienen_owner_propio(dag):
    assert {t.owner for t in dag.tasks} == {"equipo-datos"}


def test_dbt_corre_despues_de_la_carga(dag):
    primer_modelo = dag.get_task("transformacion_dbt.stg_cuotas.run")
    previas = primer_modelo.get_flat_relative_ids(upstream=True)
    assert "carga_snowflake.cargar_cuotas" in previas
    assert "carga_snowflake.cargar_partidos" in previas


def test_dbt_tiene_los_cinco_modelos_con_sus_tests(dag):
    modelos = {
        "stg_cuotas",
        "stg_partidos",
        "int_probabilidades_implicitas",
        "mart_margen_por_casa",
        "mart_acierto_por_casa",
    }
    ids = {t.task_id for t in dag.tasks}
    for modelo in modelos:
        assert f"transformacion_dbt.{modelo}.run" in ids
        assert f"transformacion_dbt.{modelo}.test" in ids


def test_ninguna_credencial_en_el_codigo_de_los_dags():
    sospechosos = ("password=", "api_key=\"", "token=\"", "secret=\"")
    for archivo in CARPETA_DAGS.glob("*.py"):
        texto = archivo.read_text(encoding="utf-8").lower()
        for patron in sospechosos:
            assert patron not in texto, f"{archivo.name} contiene {patron!r}"
