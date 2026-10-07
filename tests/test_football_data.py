"""Tests del cliente de football-data.org con respuestas simuladas (sin red)."""

from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from apuestas.football_data import (
    ESPERA_MAXIMA,
    CredencialInvalidaError,
    FootballDataClient,
    RateLimitError,
    resumir_partidos,
    segundos_de_espera,
    temporada_de,
)

PARTIDOS = {
    "matches": [
        {"id": 1, "status": "FINISHED"},
        {"id": 2, "status": "FINISHED"},
        {"id": 3, "status": "SCHEDULED"},
    ]
}


def _respuesta(status: int, json_body=None, headers=None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.json.return_value = json_body or {}
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    else:
        r.raise_for_status.return_value = None
    return r


def _cliente(*respuestas, **kwargs):
    sesion = MagicMock()
    sesion.headers = {}
    sesion.get.side_effect = list(respuestas)
    esperas = []
    cliente = FootballDataClient("key-de-prueba", sesion=sesion, dormir=esperas.append, **kwargs)
    return cliente, sesion, esperas


def test_envia_la_key_en_el_header():
    _, sesion, _ = _cliente(_respuesta(200, PARTIDOS))
    assert sesion.headers["X-Auth-Token"] == "key-de-prueba"


def test_obtener_partidos_ok():
    cliente, sesion, _ = _cliente(_respuesta(200, PARTIDOS))
    datos = cliente.obtener_partidos("PL", 2025)
    assert len(datos["matches"]) == 3
    url = sesion.get.call_args.args[0]
    assert url.endswith("/competitions/PL/matches")
    assert sesion.get.call_args.kwargs["params"] == {"season": 2025}


def test_429_espera_lo_que_pide_la_api_y_reintenta():
    cliente, sesion, esperas = _cliente(
        _respuesta(429, headers={"X-RequestCounter-Reset": "7"}),
        _respuesta(200, PARTIDOS),
    )
    assert cliente.obtener_partidos()["matches"]
    assert esperas == [7]
    assert sesion.get.call_count == 2


def test_429_persistente_lanza_rate_limit_error():
    cliente, sesion, esperas = _cliente(*[_respuesta(429) for _ in range(3)], max_reintentos=2)
    with pytest.raises(RateLimitError) as error:
        cliente.obtener_partidos()
    assert sesion.get.call_count == 3
    assert len(esperas) == 2
    assert error.value.espera_segundos > 0


@pytest.mark.parametrize("status", [401, 403])
def test_credencial_invalida_no_reintenta(status):
    cliente, sesion, esperas = _cliente(_respuesta(status), _respuesta(200, PARTIDOS))
    with pytest.raises(CredencialInvalidaError):
        cliente.obtener_partidos()
    assert sesion.get.call_count == 1
    assert esperas == []


def test_sin_key_falla_antes_de_llamar_a_la_api():
    with pytest.raises(CredencialInvalidaError, match="FOOTBALL_DATA_API_KEY"):
        FootballDataClient("")


def test_error_del_servidor_se_propaga():
    cliente, _, _ = _cliente(_respuesta(500))
    with pytest.raises(requests.HTTPError):
        cliente.obtener_partidos()


def test_respuesta_sin_matches_es_un_error():
    cliente, _, _ = _cliente(_respuesta(200, {"errorCode": 0}))
    with pytest.raises(ValueError, match="matches"):
        cliente.obtener_partidos()


def test_segundos_de_espera_acotados():
    assert segundos_de_espera({"Retry-After": "5"}) == 5
    assert segundos_de_espera({"Retry-After": "9999"}) == ESPERA_MAXIMA
    assert segundos_de_espera({}) > 0


def test_resumir_partidos_por_estado():
    assert resumir_partidos(PARTIDOS) == {"FINISHED": 2, "SCHEDULED": 1}


@pytest.mark.parametrize(
    ("fecha", "temporada"),
    [(date(2025, 8, 15), 2025), (date(2026, 5, 24), 2025), (date(2026, 7, 1), 2026)],
)
def test_temporada_de(fecha, temporada):
    assert temporada_de(fecha) == temporada
