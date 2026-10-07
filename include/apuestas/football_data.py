"""Cliente mínimo de la API v4 de football-data.org.

La API pide una key en el header `X-Auth-Token` y en el plan gratis limita a
10 consultas por minuto. Ante un 429 indica cuánto esperar en `Retry-After` o en
`X-RequestCounter-Reset` (segundos).

Manejo de errores:
- 429 -> se espera lo que indica la API y se reintenta, hasta `max_reintentos`.
  Si se agotan, `RateLimitError`: Airflow lo reintenta con backoff exponencial.
- 401/403 -> `CredencialInvalidaError`: reintentar no lo arregla, hay que fallar ya.
- Otros 4xx/5xx -> `requests.HTTPError`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests

URL_BASE = "https://api.football-data.org/v4"
ESPERA_POR_DEFECTO = 60
ESPERA_MAXIMA = 120


class CredencialInvalidaError(RuntimeError):
    """La API rechazó la key (401/403). No tiene sentido reintentar."""


class RateLimitError(RuntimeError):
    """Se superó el límite de consultas y se agotaron los reintentos internos."""

    def __init__(self, mensaje: str, espera_segundos: int):
        super().__init__(mensaje)
        self.espera_segundos = espera_segundos


def segundos_de_espera(cabeceras: dict[str, str] | Any) -> int:
    """Cuánto pide esperar la API; acotado para no colgar la tarea."""
    for nombre in ("Retry-After", "X-RequestCounter-Reset"):
        valor = cabeceras.get(nombre)
        if valor is not None and str(valor).strip().isdigit():
            return min(int(valor), ESPERA_MAXIMA)
    return ESPERA_POR_DEFECTO


class FootballDataClient:
    def __init__(
        self,
        api_key: str,
        url_base: str = URL_BASE,
        sesion: requests.Session | None = None,
        max_reintentos: int = 3,
        dormir: Callable[[float], None] = time.sleep,
        timeout: int = 30,
    ):
        if not api_key:
            raise CredencialInvalidaError(
                "Falta la API key de football-data.org: completá FOOTBALL_DATA_API_KEY en .env"
            )
        self.url_base = url_base.rstrip("/")
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({"X-Auth-Token": api_key})
        self.max_reintentos = max_reintentos
        self.dormir = dormir
        self.timeout = timeout

    def _get(self, ruta: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.url_base}/{ruta.lstrip('/')}"
        for intento in range(self.max_reintentos + 1):
            respuesta = self.sesion.get(url, params=params, timeout=self.timeout)
            if respuesta.status_code in (401, 403):
                raise CredencialInvalidaError(
                    f"football-data.org rechazó la key (HTTP {respuesta.status_code}). "
                    "Revisá FOOTBALL_DATA_API_KEY."
                )
            if respuesta.status_code == 429:
                espera = segundos_de_espera(respuesta.headers)
                if intento == self.max_reintentos:
                    raise RateLimitError(
                        f"Límite de consultas superado tras {self.max_reintentos} reintentos",
                        espera_segundos=espera,
                    )
                self.dormir(espera)
                continue
            respuesta.raise_for_status()
            return respuesta.json()
        raise AssertionError("inalcanzable")  # pragma: no cover

    def obtener_partidos(self, competicion: str = "PL", temporada: int = 2025) -> dict[str, Any]:
        """Todos los partidos de la temporada (año de inicio: 2025 = 2025/26)."""
        datos = self._get(f"competitions/{competicion}/matches", params={"season": temporada})
        if "matches" not in datos:
            raise ValueError("Respuesta inesperada de la API: falta la clave 'matches'")
        return datos


def resumir_partidos(datos: dict[str, Any]) -> dict[str, int]:
    """Cuántos partidos hay por estado (para el log y para validar la descarga)."""
    resumen: dict[str, int] = {}
    for partido in datos.get("matches", []):
        estado = partido.get("status", "DESCONOCIDO")
        resumen[estado] = resumen.get(estado, 0) + 1
    return resumen
