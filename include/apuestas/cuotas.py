"""Lectura del CSV de football-data.co.uk y cálculos de margen y acierto.

Todo acá es Python puro: se prueba con pytest sin levantar Airflow.

Formato del CSV (temporada 2025/26):
- Columnas base: Div, Date (dd/mm/yyyy), HomeTeam, AwayTeam, FTHG, FTAG, FTR (H/D/A).
- Por casa, cuotas de apertura `<CASA>H/D/A` y de cierre `<CASA>CH/CD/CA`.
  Ej.: B365H, B365D, B365A, B365CH, B365CD, B365CA.
- El archivo viene con BOM (utf-8-sig).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path

COLUMNAS_BASE = ("Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR")

# Casas de apuestas que se analizan (código del CSV -> nombre). Max/Avg son agregados
# del mercado y BFE es un exchange (no cobra margen en la cuota), por eso no están.
CASAS = {
    "B365": "Bet365",
    "BFD": "Betfred",
    "BMGM": "BetMGM",
    "BV": "BetVictor",
    "BW": "Bwin",
    "CL": "Coral",
    "LB": "Ladbrokes",
    "PS": "Pinnacle",
    "WH": "William Hill",
}

RESULTADOS = ("H", "D", "A")
MOMENTOS = {"apertura": "", "cierre": "C"}


class ColumnasFaltantesError(ValueError):
    """El CSV no trae las columnas mínimas para el análisis."""


class CuotaInvalidaError(ValueError):
    """Una cuota decimal tiene que ser mayor que 1."""


def columnas_de_casa(casa: str) -> list[str]:
    """Las 6 columnas de una casa: apertura y cierre para H/D/A."""
    return [f"{casa}{sufijo}{r}" for sufijo in MOMENTOS.values() for r in RESULTADOS]


def casas_presentes(columnas: Iterable[str]) -> list[str]:
    """Casas que traen sus 6 columnas completas en el archivo."""
    disponibles = set(columnas)
    return [c for c in CASAS if set(columnas_de_casa(c)) <= disponibles]


def validar_columnas(columnas: Iterable[str]) -> list[str]:
    """Valida el encabezado y devuelve las casas presentes.

    Falla si falta una columna base o si no hay ninguna casa completa: sin eso
    el pipeline no puede calcular nada y conviene cortar con un error claro.
    """
    columnas = list(columnas)
    faltantes = [c for c in COLUMNAS_BASE if c not in columnas]
    if faltantes:
        raise ColumnasFaltantesError(f"Faltan columnas base en el CSV: {', '.join(faltantes)}")
    casas = casas_presentes(columnas)
    if not casas:
        raise ColumnasFaltantesError(
            "El CSV no trae ninguna casa con cuotas completas de apertura y cierre "
            f"(se buscaron: {', '.join(CASAS)})"
        )
    return casas


def _decodificar(origen: str | Path | bytes) -> str:
    if isinstance(origen, bytes):
        return origen.decode("utf-8-sig")
    return Path(origen).read_text(encoding="utf-8-sig")


def parsear_fecha(valor: str) -> date:
    """football-data.co.uk usa dd/mm/yyyy (y en temporadas viejas dd/mm/yy)."""
    for formato in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha con formato desconocido: {valor!r}")


def leer_cuotas_csv(origen: str | Path | bytes) -> list[dict[str, str]]:
    """Lee el CSV (ruta o bytes), valida columnas y devuelve las filas con partido.

    - Quita el BOM.
    - Descarta filas vacías al final del archivo.
    - Normaliza `Date` a ISO (yyyy-mm-dd) para que Snowflake no dependa del formato.
    """
    lector = csv.DictReader(io.StringIO(_decodificar(origen)))
    validar_columnas(lector.fieldnames or [])
    filas = []
    for fila in lector:
        if not (fila.get("HomeTeam") or "").strip():
            continue
        fila = {k: (v or "").strip() for k, v in fila.items() if k}
        fila["Date"] = parsear_fecha(fila["Date"]).isoformat()
        filas.append(fila)
    return filas


def filas_a_ndjson(filas: Iterable[Mapping[str, str]]) -> str:
    """Una fila JSON por partido: así Snowflake la carga como VARIANT.

    Guardar cada fila como objeto JSON hace que la carga no se rompa si una
    temporada agrega o quita columnas: dbt elige qué columnas leer.
    """
    return "".join(json.dumps(dict(f), ensure_ascii=False) + "\n" for f in filas)


def url_csv_temporada(temporada: int, division: str = "E0") -> str:
    """URL del CSV de una temporada: 2026 (2026/27) -> .../mmz4281/2627/E0.csv."""
    codigo = f"{temporada % 100:02d}{(temporada + 1) % 100:02d}"
    return f"https://www.football-data.co.uk/mmz4281/{codigo}/{division}.csv"


def filtrar_archivos_csv(nombres: Iterable[str]) -> list[str]:
    """Del listado del SFTP, solo los CSV (descarta .gitkeep y otros)."""
    return sorted(n for n in nombres if n.lower().endswith(".csv"))


# ---------------------------------------------------------------------------
# Cálculos
# ---------------------------------------------------------------------------


def probabilidades_implicitas(cuotas: Mapping[str, float]) -> dict[str, float]:
    """1 / cuota para cada resultado."""
    for resultado, cuota in cuotas.items():
        if cuota is None or cuota <= 1:
            raise CuotaInvalidaError(f"Cuota inválida para {resultado}: {cuota!r}")
    return {r: 1 / c for r, c in cuotas.items()}


def calcular_overround(cuotas: Mapping[str, float]) -> float:
    """Margen de la casa: cuánto pasa de 1 la suma de probabilidades implícitas."""
    return sum(probabilidades_implicitas(cuotas).values()) - 1


def normalizar_probabilidades(cuotas: Mapping[str, float]) -> dict[str, float]:
    """Probabilidades sin margen: cada implícita dividida por la suma total."""
    implicitas = probabilidades_implicitas(cuotas)
    total = sum(implicitas.values())
    return {r: p / total for r, p in implicitas.items()}


def brier_score(probabilidades: Mapping[str, float], resultado_real: str) -> float:
    """Error cuadrático de la predicción contra lo que pasó (0 = perfecta)."""
    if resultado_real not in probabilidades:
        raise ValueError(f"Resultado {resultado_real!r} no está entre {list(probabilidades)}")
    return sum((p - (1.0 if r == resultado_real else 0.0)) ** 2 for r, p in probabilidades.items())
