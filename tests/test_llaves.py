"""Tests del generador de llaves de Snowflake."""

import pytest
from cryptography.hazmat.primitives import serialization

from apuestas.llaves import generar_par, llave_publica_en_una_linea


def test_genera_par_valido(tmp_path):
    privada, publica, una_linea = generar_par(tmp_path)
    llave = serialization.load_pem_private_key(privada.read_bytes(), password=None)
    assert llave.key_size == 2048
    assert "BEGIN PUBLIC KEY" in publica.read_text()
    assert "\n" not in una_linea and "-----" not in una_linea


def test_no_pisa_llaves_existentes(tmp_path):
    generar_par(tmp_path)
    with pytest.raises(FileExistsError):
        generar_par(tmp_path)


def test_llave_publica_en_una_linea():
    pem = "-----BEGIN PUBLIC KEY-----\nAAA\nBBB\n-----END PUBLIC KEY-----\n"
    assert llave_publica_en_una_linea(pem) == "AAABBB"
