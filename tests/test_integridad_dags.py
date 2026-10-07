"""Integridad de los DAGs: importan sin errores y cumplen las reglas del proyecto.

No prueban la lógica de negocio (eso va en los tests de include/apuestas), sino que
ningún PR rompa la carga de DAGs ni se salte las reglas del enunciado.
"""

from pathlib import Path

import pytest
from airflow.models import DagBag

CARPETA_DAGS = Path(__file__).resolve().parent.parent / "dags"


@pytest.fixture(scope="session")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(CARPETA_DAGS), include_examples=False)


def test_dags_importan_sin_errores(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}, f"DAGs con errores de importación: {dagbag.import_errors}"


def test_dags_tienen_owner(dagbag: DagBag) -> None:
    for dag_id, dag in dagbag.dags.items():
        assert dag.owner and dag.owner != "airflow", f"{dag_id} no tiene owner propio"


def test_dags_no_hacen_catchup(dagbag: DagBag) -> None:
    for dag_id, dag in dagbag.dags.items():
        assert dag.catchup is False, f"{dag_id} tiene catchup activado"


def test_dags_tienen_documentacion(dagbag: DagBag) -> None:
    for dag_id, dag in dagbag.dags.items():
        assert dag.doc_md, f"{dag_id} no tiene doc_md"
