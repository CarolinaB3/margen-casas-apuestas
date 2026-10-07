"""Tests de la lógica de cuotas: lectura del CSV y cálculos de margen y acierto."""

import json

import pytest

from apuestas.cuotas import (
    ColumnasFaltantesError,
    CuotaInvalidaError,
    brier_score,
    calcular_overround,
    casas_presentes,
    filas_a_ndjson,
    filtrar_archivos_csv,
    leer_cuotas_csv,
    normalizar_probabilidades,
    probabilidades_implicitas,
)

# Primer partido real de la Premier 2025/26 (Bet365, apertura).
LIVERPOOL_BOURNEMOUTH = {"H": 1.30, "D": 6.00, "A": 8.50}

ENCABEZADO = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
    "B365H,B365D,B365A,PSH,PSD,PSA,"
    "B365CH,B365CD,B365CA,PSCH,PSCD,PSCA"
)
FILA = (
    "E0,15/08/2025,20:00,Liverpool,Bournemouth,4,2,H,"
    "1.3,6,8.5,1.28,6.56,9.07,"
    "1.29,6.25,9,1.29,6.55,9.75"
)


def _csv(*lineas: str, bom: bool = True) -> bytes:
    texto = "\n".join(lineas) + "\n"
    return ("﻿" + texto if bom else texto).encode("utf-8")


# ---------------------------------------------------------------------------
# Cálculos
# ---------------------------------------------------------------------------


def test_probabilidades_implicitas_son_inversa_de_la_cuota():
    p = probabilidades_implicitas(LIVERPOOL_BOURNEMOUTH)
    assert p["H"] == pytest.approx(0.7692, abs=1e-4)
    assert p["D"] == pytest.approx(0.1667, abs=1e-4)
    assert p["A"] == pytest.approx(0.1176, abs=1e-4)


def test_overround_del_ejemplo_real():
    assert calcular_overround(LIVERPOOL_BOURNEMOUTH) == pytest.approx(0.0535, abs=1e-4)


def test_probabilidades_normalizadas_suman_uno():
    norm = normalizar_probabilidades(LIVERPOOL_BOURNEMOUTH)
    assert sum(norm.values()) == pytest.approx(1.0)
    assert norm["H"] == pytest.approx(0.7301, abs=1e-4)


def test_normalizar_mantiene_el_orden_de_favoritismo():
    norm = normalizar_probabilidades(LIVERPOOL_BOURNEMOUTH)
    assert norm["H"] > norm["D"] > norm["A"]


def test_brier_del_ejemplo_real():
    norm = normalizar_probabilidades(LIVERPOOL_BOURNEMOUTH)
    assert brier_score(norm, "H") == pytest.approx(0.1103, abs=1e-4)


def test_brier_castiga_mas_si_gana_el_no_favorito():
    norm = normalizar_probabilidades(LIVERPOOL_BOURNEMOUTH)
    assert brier_score(norm, "A") > brier_score(norm, "H")


def test_brier_prediccion_perfecta_es_cero():
    assert brier_score({"H": 1.0, "D": 0.0, "A": 0.0}, "H") == 0.0


def test_brier_rechaza_resultado_desconocido():
    with pytest.raises(ValueError):
        brier_score({"H": 0.5, "D": 0.3, "A": 0.2}, "X")


@pytest.mark.parametrize("cuota", [1.0, 0.5, 0, None])
def test_cuota_menor_o_igual_a_uno_es_invalida(cuota):
    with pytest.raises(CuotaInvalidaError):
        probabilidades_implicitas({"H": cuota, "D": 3.0, "A": 4.0})


# ---------------------------------------------------------------------------
# Lectura del CSV
# ---------------------------------------------------------------------------


def test_lee_csv_con_bom_y_normaliza_la_fecha():
    filas = leer_cuotas_csv(_csv(ENCABEZADO, FILA))
    assert len(filas) == 1
    assert filas[0]["Div"] == "E0"  # sin el BOM pegado al nombre de la columna
    assert filas[0]["Date"] == "2025-08-15"
    assert filas[0]["HomeTeam"] == "Liverpool"


def test_lee_csv_sin_bom():
    assert len(leer_cuotas_csv(_csv(ENCABEZADO, FILA, bom=False))) == 1


def test_lee_desde_un_archivo(tmp_path):
    ruta = tmp_path / "E0.csv"
    ruta.write_bytes(_csv(ENCABEZADO, FILA))
    assert leer_cuotas_csv(ruta)[0]["AwayTeam"] == "Bournemouth"


def test_descarta_filas_vacias_al_final():
    assert len(leer_cuotas_csv(_csv(ENCABEZADO, FILA, ",,,,,,,"))) == 1


def test_fecha_con_anio_de_dos_digitos():
    fila = FILA.replace("15/08/2025", "15/08/25")
    assert leer_cuotas_csv(_csv(ENCABEZADO, fila))[0]["Date"] == "2025-08-15"


def test_falta_columna_base():
    encabezado = ENCABEZADO.replace("FTR,", "")
    fila = FILA.replace(",H,", ",", 1)
    with pytest.raises(ColumnasFaltantesError, match="FTR"):
        leer_cuotas_csv(_csv(encabezado, fila))


def test_sin_ninguna_casa_completa():
    with pytest.raises(ColumnasFaltantesError, match="ninguna casa"):
        leer_cuotas_csv(_csv("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A"))


def test_casas_presentes_exige_apertura_y_cierre():
    columnas = ENCABEZADO.split(",") + ["BWH", "BWD", "BWA"]  # BW sin cierre
    assert casas_presentes(columnas) == ["B365", "PS"]


def test_filtrar_archivos_csv_descarta_gitkeep():
    assert filtrar_archivos_csv([".gitkeep", "E0.csv", "notas.txt"]) == ["E0.csv"]


def test_filas_a_ndjson_una_linea_json_por_partido():
    filas = leer_cuotas_csv(_csv(ENCABEZADO, FILA, FILA.replace("Liverpool", "Arsenal")))
    lineas = filas_a_ndjson(filas).splitlines()
    assert len(lineas) == 2
    assert json.loads(lineas[1])["HomeTeam"] == "Arsenal"
