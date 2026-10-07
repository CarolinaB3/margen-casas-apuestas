"""El CSV simulado tiene que pasar por el mismo lector que el real y ser creíble."""

from collections import Counter
from datetime import date

import pytest

from apuestas.cuotas import calcular_overround, leer_cuotas_csv
from apuestas.datos_simulados import (
    CASAS_SIMULADAS,
    EQUIPOS,
    fixture,
    generar_csv_simulado,
    probabilidades_reales,
)


def test_fixture_ida_y_vuelta_completo():
    jornadas = fixture(list(EQUIPOS))
    assert len(jornadas) == 38
    assert all(len(j) == 10 for j in jornadas)
    cruces = Counter(p for j in jornadas for p in j)
    assert len(cruces) == 20 * 19  # cada par se enfrenta una vez de local y otra de visita
    assert set(cruces.values()) == {1}


def test_cada_equipo_juega_una_vez_por_jornada():
    for jornada in fixture(list(EQUIPOS)):
        equipos = [e for partido in jornada for e in partido]
        assert len(equipos) == len(set(equipos)) == 20


def test_probabilidades_reales_suman_uno_y_favorecen_al_mejor():
    p = probabilidades_reales("Liverpool", "Sunderland")
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["H"] > p["A"]


def test_csv_simulado_pasa_por_el_lector_real():
    filas = leer_cuotas_csv(generar_csv_simulado(date(2025, 9, 1)))
    assert len(filas) == 30  # 3 jornadas (15/08, 22/08, 29/08) de 10 partidos
    assert filas[0]["Date"] == "2025-08-15"


def test_es_deterministico():
    assert generar_csv_simulado(date(2025, 10, 1)) == generar_csv_simulado(date(2025, 10, 1))


def test_margenes_creibles_y_pinnacle_cobra_menos():
    filas = leer_cuotas_csv(generar_csv_simulado(date(2026, 1, 31)))

    def margen_promedio(casa):
        valores = [
            calcular_overround({r: float(f[f"{casa}{r}"]) for r in "HDA"}) for f in filas
        ]
        return sum(valores) / len(valores)

    margenes = {c: margen_promedio(c) for c in CASAS_SIMULADAS}
    assert all(0 < m < 0.12 for m in margenes.values())
    assert min(margenes, key=margenes.get) == "PS"


def test_la_temporada_sale_de_la_fecha():
    filas = leer_cuotas_csv(generar_csv_simulado(date(2026, 9, 1)))
    assert filas[0]["Date"] == "2026-08-15"  # temporada 2026/27
    assert len(filas) == 30


def test_antes_del_inicio_no_hay_partidos():
    assert leer_cuotas_csv(generar_csv_simulado(date(2026, 8, 1))) == []
