"""Genera el par de llaves RSA del usuario de servicio de Snowflake.

Uso (desde la raíz del repo, una sola vez):

    py -3.12 -m pip install cryptography
    py -3.12 include/apuestas/llaves.py secrets

Crea:
- secrets/snowflake_rsa_key.p8   -> llave privada (la usan Airflow y dbt; NUNCA a git)
- secrets/snowflake_rsa_key.pub  -> llave pública (se pega en sql/setup.sql)
e imprime la llave pública en una sola línea, lista para pegar.
"""

from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

NOMBRE = "snowflake_rsa_key"


def generar_par(carpeta: str | Path) -> tuple[Path, Path, str]:
    """Escribe la llave privada (PKCS8, sin cifrar) y la pública; no pisa archivos."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    privada, publica = carpeta / f"{NOMBRE}.p8", carpeta / f"{NOMBRE}.pub"
    if privada.exists() or publica.exists():
        raise FileExistsError(
            f"Ya existen llaves en {carpeta}: borralas a mano si querés regenerar"
        )

    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    privada.write_bytes(
        llave.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pem_publica = llave.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    publica.write_bytes(pem_publica)
    return privada, publica, llave_publica_en_una_linea(pem_publica.decode())


def llave_publica_en_una_linea(pem: str) -> str:
    """El formato que pide Snowflake en RSA_PUBLIC_KEY: sin BEGIN/END ni saltos."""
    return "".join(linea for linea in pem.splitlines() if linea and "-----" not in linea)


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else "secrets"
    _, _, una_linea = generar_par(destino)
    print("Llaves creadas en", destino)
    print("\nPegá esto en sql/setup.sql en lugar de <PEGAR_LLAVE_PUBLICA>:\n")
    print(una_linea)
