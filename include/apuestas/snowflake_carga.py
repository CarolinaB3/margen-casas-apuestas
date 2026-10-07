"""Sentencias para cargar archivos de MinIO a Snowflake.

Snowflake está en la nube y no ve el MinIO local, así que Airflow baja el archivo
y lo sube a un stage interno con PUT. Después COPY INTO lo carga en RAW.

La carga es idempotente por fecha: primero borra lo cargado para esa fecha y
después copia con FORCE=TRUE. Re-correr el mismo día no duplica filas.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

STAGE = "RAW.STAGE_CARGA"
TABLAS = {"CUOTAS", "PARTIDOS"}
VARIABLES_REQUERIDAS = ("account", "login", "warehouse", "database", "role")


class ConfiguracionSnowflakeError(RuntimeError):
    """Falta configurar Snowflake en el .env o la llave privada en secrets/."""


def validar_config_snowflake(config: Mapping[str, Any], ruta_llave: str | None) -> None:
    """Falla con un mensaje que dice exactamente qué completar."""
    faltan = [
        f"SNOWFLAKE_{c.upper().replace('LOGIN', 'USER')}"
        for c in VARIABLES_REQUERIDAS
        if not config.get(c)
    ]
    if faltan:
        raise ConfiguracionSnowflakeError(
            f"Faltan valores de Snowflake en el .env: {', '.join(faltan)}"
        )
    if not ruta_llave or not Path(ruta_llave).is_file():
        raise ConfiguracionSnowflakeError(
            f"No existe la llave privada {ruta_llave!r}: generala con "
            "include/apuestas/llaves.py (ver README)"
        )


def _validar(tabla: str, fecha_carga: str) -> str:
    tabla = tabla.upper()
    if tabla not in TABLAS:
        raise ValueError(f"Tabla no permitida: {tabla!r}. Válidas: {sorted(TABLAS)}")
    date.fromisoformat(fecha_carga)  # evita meter texto arbitrario en el SQL
    return tabla


def ruta_en_stage(tabla: str, fecha_carga: str) -> str:
    tabla = _validar(tabla, fecha_carga)
    return f"@{STAGE}/{tabla.lower()}/fecha={fecha_carga}/"


def sentencias_carga(tabla: str, archivo_local: str, fecha_carga: str) -> list[str]:
    """PUT al stage + DELETE de la fecha + COPY INTO, en ese orden."""
    tabla = _validar(tabla, fecha_carga)
    if "'" in archivo_local:
        raise ValueError("La ruta del archivo no puede contener comillas simples")
    destino = ruta_en_stage(tabla, fecha_carga)
    return [
        f"PUT 'file://{archivo_local}' {destino} OVERWRITE = TRUE AUTO_COMPRESS = TRUE",
        f"DELETE FROM RAW.{tabla} WHERE fecha_carga = '{fecha_carga}'",
        (
            f"COPY INTO RAW.{tabla} (datos, archivo, fecha_carga) "
            f"FROM (SELECT $1, METADATA$FILENAME, TO_DATE('{fecha_carga}') FROM {destino}) "
            "FILE_FORMAT = (TYPE = JSON) FORCE = TRUE"
        ),
    ]


def partidos_a_ndjson(datos: Mapping[str, Any]) -> str:
    """Un partido por línea: cada uno queda como una fila VARIANT en RAW.PARTIDOS."""
    partidos: Iterable[Mapping[str, Any]] = datos.get("matches", [])
    return "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in partidos)
