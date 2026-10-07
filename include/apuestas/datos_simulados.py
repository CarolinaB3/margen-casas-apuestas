"""CSV de cuotas simulado, con el mismo formato que football-data.co.uk.

El enunciado permite simular una fuente si la real no está disponible (sección 12).
Se usa como respaldo cuando no se puede bajar el CSV real.

Cómo se genera (determinístico para una misma semilla):
- 20 equipos de la Premier 2025/26 con una fuerza de ataque y defensa.
- Fixture de ida y vuelta (38 jornadas), una por semana desde el 15 de agosto.
- Goles con un modelo de Poisson; de ahí salen las probabilidades reales de H/D/A.
- Cada casa cobra su propio margen sobre esas probabilidades (más ruido), en apertura y
  un poco menos en cierre, cuando el mercado ya ajustó.
"""

from __future__ import annotations

import csv
import io
import math
import random
from datetime import date, timedelta

from apuestas.cuotas import CASAS

# (ataque, defensa): más alto = mejor. Valores aproximados para que el resultado sea creíble.
EQUIPOS = {
    "Liverpool": (0.45, 0.35), "Arsenal": (0.40, 0.45), "Man City": (0.45, 0.30),
    "Chelsea": (0.30, 0.25), "Newcastle": (0.25, 0.20), "Aston Villa": (0.20, 0.10),
    "Tottenham": (0.25, 0.00), "Man United": (0.10, 0.05), "Brighton": (0.15, 0.00),
    "Crystal Palace": (0.05, 0.15), "Bournemouth": (0.10, 0.00), "Brentford": (0.10, -0.05),
    "Fulham": (0.05, 0.00), "Nott'm Forest": (0.05, 0.10), "West Ham": (0.00, -0.10),
    "Everton": (-0.05, 0.05), "Wolves": (-0.05, -0.10), "Leeds": (-0.10, -0.10),
    "Burnley": (-0.20, -0.05), "Sunderland": (-0.20, -0.15),
}

# Margen típico de cada casa (Pinnacle es conocida por cobrar poco).
MARGENES = {
    "B365": 0.055, "BFD": 0.065, "BMGM": 0.060, "BV": 0.050, "BW": 0.060,
    "CL": 0.065, "LB": 0.065, "PS": 0.025, "WH": 0.060,
}
CASAS_SIMULADAS = [c for c in CASAS if c != "WH"]  # el CSV 2025/26 ya no trae William Hill


def fixture(equipos: list[str]) -> list[list[tuple[str, str]]]:
    """Ida y vuelta por el método del círculo: 2 * (n - 1) jornadas de n / 2 partidos."""
    rotacion = equipos[:]
    ida = []
    for jornada in range(len(equipos) - 1):
        partidos = []
        for i in range(len(equipos) // 2):
            a, b = rotacion[i], rotacion[-1 - i]
            partidos.append((a, b) if (jornada + i) % 2 == 0 else (b, a))
        ida.append(partidos)
        rotacion = [rotacion[0], rotacion[-1], *rotacion[1:-1]]
    vuelta = [[(b, a) for a, b in partidos] for partidos in ida]
    return ida + vuelta


def _poisson(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _goles_esperados(local: str, visitante: str) -> tuple[float, float]:
    ata_l, def_l = EQUIPOS[local]
    ata_v, def_v = EQUIPOS[visitante]
    return math.exp(0.30 + ata_l - def_v), math.exp(0.05 + ata_v - def_l)


def probabilidades_reales(local: str, visitante: str) -> dict[str, float]:
    lam_l, lam_v = _goles_esperados(local, visitante)
    p = {"H": 0.0, "D": 0.0, "A": 0.0}
    for gl in range(11):
        for gv in range(11):
            prob = _poisson(lam_l, gl) * _poisson(lam_v, gv)
            p["H" if gl > gv else "D" if gl == gv else "A"] += prob
    total = sum(p.values())
    return {r: v / total for r, v in p.items()}


def _goles(lam: float, azar: random.Random) -> int:
    limite, k, producto = math.exp(-lam), 0, azar.random()
    while producto > limite:
        k += 1
        producto *= azar.random()
    return k


def _cuotas(probs: dict[str, float], margen: float, ruido: float, azar: random.Random):
    cuotas = {}
    for r, p in probs.items():
        estimada = max(p * (1 + azar.uniform(-ruido, ruido)), 0.01)
        cuotas[r] = max(round(1 / (estimada * (1 + margen)), 2), 1.01)
    return cuotas


def generar_csv_simulado(hasta: date, semilla: int | None = None) -> bytes:
    """CSV (con BOM, como el real) de la temporada de `hasta`, jugado hasta esa fecha."""
    temporada = hasta.year if hasta.month >= 7 else hasta.year - 1
    inicio = date(temporada, 8, 15)
    azar = random.Random(temporada if semilla is None else semilla)
    columnas = ["Div", "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
    for casa in CASAS_SIMULADAS:
        columnas += [f"{casa}{r}" for r in "HDA"]
    for casa in CASAS_SIMULADAS:
        columnas += [f"{casa}C{r}" for r in "HDA"]

    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=columnas, lineterminator="\n")
    escritor.writeheader()
    for numero, partidos in enumerate(fixture(list(EQUIPOS))):
        dia = inicio + timedelta(weeks=numero)
        if dia > hasta:
            break
        for local, visitante in partidos:
            probs = probabilidades_reales(local, visitante)
            lam_l, lam_v = _goles_esperados(local, visitante)
            gl, gv = _goles(lam_l, azar), _goles(lam_v, azar)
            fila = {
                "Div": "E0",
                "Date": dia.strftime("%d/%m/%Y"),
                "Time": "15:00",
                "HomeTeam": local,
                "AwayTeam": visitante,
                "FTHG": gl,
                "FTAG": gv,
                "FTR": "H" if gl > gv else "D" if gl == gv else "A",
            }
            for casa in CASAS_SIMULADAS:
                apertura = _cuotas(probs, MARGENES[casa], 0.08, azar)
                cierre = _cuotas(probs, MARGENES[casa] * 0.9, 0.03, azar)
                for r in "HDA":
                    fila[f"{casa}{r}"] = apertura[r]
                    fila[f"{casa}C{r}"] = cierre[r]
            escritor.writerow(fila)
    return ("﻿" + salida.getvalue()).encode("utf-8")
