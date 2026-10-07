"""Tests de las sentencias de carga a Snowflake (sin conexión)."""

import json

import pytest

from apuestas.snowflake_carga import partidos_a_ndjson, ruta_en_stage, sentencias_carga


def test_orden_put_delete_copy():
    put, delete, copy = sentencias_carga("cuotas", "/tmp/cuotas.ndjson", "2026-10-05")
    destino = "@RAW.STAGE_CARGA/cuotas/fecha=2026-10-05/"
    assert put.startswith(f"PUT 'file:///tmp/cuotas.ndjson' {destino}")
    assert "OVERWRITE = TRUE" in put
    assert delete == "DELETE FROM RAW.CUOTAS WHERE fecha_carga = '2026-10-05'"
    assert copy.startswith("COPY INTO RAW.CUOTAS (datos, archivo, fecha_carga)")
    assert "TYPE = JSON" in copy


def test_copy_lee_solo_la_carpeta_de_la_fecha():
    _, _, copy = sentencias_carga("partidos", "/tmp/p.ndjson", "2026-10-05")
    assert "@RAW.STAGE_CARGA/partidos/fecha=2026-10-05/" in copy
    assert "FORCE = TRUE" in copy  # junto con el DELETE, re-correr no duplica


def test_rechaza_tabla_no_permitida():
    with pytest.raises(ValueError, match="no permitida"):
        sentencias_carga("usuarios; DROP TABLE x", "/tmp/a", "2026-10-05")


@pytest.mark.parametrize("fecha", ["05/10/2026", "2026-10-05' OR 1=1", ""])
def test_rechaza_fecha_invalida(fecha):
    with pytest.raises(ValueError):
        ruta_en_stage("cuotas", fecha)


def test_rechaza_ruta_con_comillas():
    with pytest.raises(ValueError, match="comillas"):
        sentencias_carga("cuotas", "/tmp/a'b.ndjson", "2026-10-05")


def test_partidos_a_ndjson_un_partido_por_linea():
    datos = {"matches": [{"id": 1, "status": "FINISHED"}, {"id": 2, "status": "SCHEDULED"}]}
    lineas = partidos_a_ndjson(datos).splitlines()
    assert [json.loads(linea)["id"] for linea in lineas] == [1, 2]


def test_partidos_a_ndjson_sin_partidos():
    assert partidos_a_ndjson({"matches": []}) == ""
