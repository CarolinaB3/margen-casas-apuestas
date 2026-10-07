FROM apache/airflow:2.10.5-python3.12

# Providers y Cosmos instalados contra las constraints oficiales de Airflow 2.10.5:
# así pip no sube una dependencia que rompa Airflow.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir \
    "apache-airflow==2.10.5" \
    -r /requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.12.txt"

# Dbt va en un virtualenv aparte: sus dependencias chocan con las de Airflow.
# Cosmos lo invoca por ruta (ExecutionConfig.dbt_executable_path).
RUN python -m venv /home/airflow/dbt_venv \
    && /home/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-core==1.12.5" "dbt-snowflake==1.12.1"
