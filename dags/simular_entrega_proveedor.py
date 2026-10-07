"""Simula al proveedor que deja el CSV de cuotas en su SFTP cada semana.

En la vida real el archivo lo deja un tercero; acá lo bajamos de football-data.co.uk
y lo subimos al SFTP local, así el sensor del DAG principal tiene algo real que esperar.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import date, datetime, timedelta

import requests
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.providers.sftp.hooks.sftp import SFTPHook

from apuestas.cuotas import ColumnasFaltantesError, leer_cuotas_csv, url_csv_temporada
from apuestas.datos_simulados import generar_csv_simulado
from apuestas.football_data import temporada_de

log = logging.getLogger(__name__)

CONN_SFTP = "sftp_proveedor"
CARPETA_SFTP = "entrada"
ARCHIVO = "E0.csv"

DOC = """
### Simulación de la entrega del proveedor

Baja el CSV de cuotas de la Premier (temporada de la fecha del run) desde football-data.co.uk y lo
deja en `entrada/E0.csv` del SFTP local. Corre los lunes a las 06:00 UTC, una hora antes
del DAG `margen_casas_apuestas`, que lo espera con un sensor.

La URL se puede cambiar con la Variable de Airflow `url_csv_cuotas`.

**Respaldo:** si el sitio no responde, se genera un CSV simulado con el mismo formato
(`include/apuestas/datos_simulados.py`), como permite el enunciado. Con la Variable
`usar_datos_simulados` = `true` se fuerza la simulación.
"""


def obtener_csv(hasta: date) -> bytes:
    """CSV real de football-data.co.uk; si no se puede bajar, uno simulado.

    El enunciado permite simular la fuente si la real no está disponible. La Variable
    `usar_datos_simulados` = "true" fuerza la simulación (útil para demos sin internet).
    """
    if Variable.get("usar_datos_simulados", default_var="false").lower() == "true":
        log.warning("Variable usar_datos_simulados=true: se usan datos simulados")
        return generar_csv_simulado(hasta)
    url = Variable.get("url_csv_cuotas", default_var=url_csv_temporada(temporada_de(hasta)))
    try:
        respuesta = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        respuesta.raise_for_status()
        return respuesta.content
    except requests.RequestException as error:
        log.warning("No se pudo bajar %s (%s): se usan datos simulados", url, error)
        return generar_csv_simulado(hasta)


@dag(
    dag_id="simular_entrega_proveedor",
    description="Deja el CSV de cuotas en el SFTP, como lo haría el proveedor",
    schedule="0 6 * * 1",
    start_date=datetime(2025, 8, 11),
    catchup=False,
    doc_md=DOC,
    tags=["proyecto-final", "simulacion"],
    default_args={
        "owner": "equipo-datos",
        "retries": 3,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
    },
)
def simular_entrega_proveedor():
    @task
    def descargar_y_subir_al_sftp(ds: str | None = None) -> int:
        contenido = obtener_csv(date.fromisoformat(ds))
        try:
            filas = leer_cuotas_csv(contenido)
        except ColumnasFaltantesError as error:
            raise AirflowFailException(f"El CSV no es válido: {error}") from error

        sftp = SFTPHook(ssh_conn_id=CONN_SFTP)
        destino = f"{CARPETA_SFTP}/{ARCHIVO}"
        temporal = f"{destino}.parcial"
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, ARCHIVO)
            with open(local, "wb") as archivo:
                archivo.write(contenido)
            # Se sube con otro nombre y se renombra al final:
            # el sensor nunca ve un archivo a medias.
            sftp.store_file(temporal, local)
        conexion = sftp.get_conn()
        if sftp.path_exists(destino):
            conexion.remove(destino)
        conexion.rename(temporal, destino)
        print(f"{len(filas)} partidos -> sftp:{destino}")
        return len(filas)

    descargar_y_subir_al_sftp()


simular_entrega_proveedor()
