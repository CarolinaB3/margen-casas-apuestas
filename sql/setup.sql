-- =============================================================================
-- Setup de Snowflake para el pipeline (correr UNA vez en Snowsight).
--
-- Antes de correrlo:
--   1. Generar el par de llaves del usuario de servicio (ver README, "Snowflake").
--   2. Reemplazar TODAS las apariciones de <PEGAR_LLAVE_PUBLICA> por el contenido de secrets/snowflake_rsa_key.pub
--      SIN las líneas BEGIN/END y sin saltos de línea.
--   3. Correr todo con un rol administrador (ACCOUNTADMIN en la cuenta trial).
--
-- Es idempotente: se puede volver a correr sin romper nada.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Objetos (los crea SYSADMIN)
-- ---------------------------------------------------------------------------
USE ROLE SYSADMIN;

-- XSMALL + AUTO_SUSPEND=60: se apaga al minuto sin uso para no gastar créditos.
CREATE WAREHOUSE IF NOT EXISTS APUESTAS_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS APUESTAS;
CREATE SCHEMA IF NOT EXISTS APUESTAS.RAW;        -- datos tal como llegan
CREATE SCHEMA IF NOT EXISTS APUESTAS.ANALYTICS;  -- modelos de dbt

-- Cada fila del CSV y cada partido de la API se guardan como VARIANT (JSON):
-- si la fuente agrega o quita columnas, la carga no se rompe; dbt elige qué leer.
CREATE TABLE IF NOT EXISTS APUESTAS.RAW.CUOTAS (
  datos       VARIANT,
  archivo     STRING,
  fecha_carga DATE,
  cargado_en  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS APUESTAS.RAW.PARTIDOS (
  datos       VARIANT,
  archivo     STRING,
  fecha_carga DATE,
  cargado_en  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Stage interno: Snowflake no ve el MinIO local, Airflow sube los archivos acá con PUT.
CREATE STAGE IF NOT EXISTS APUESTAS.RAW.STAGE_CARGA
  FILE_FORMAT = (TYPE = JSON);

-- ---------------------------------------------------------------------------
-- 2. Rol y usuario del pipeline con permisos mínimos (los crea SECURITYADMIN)
-- ---------------------------------------------------------------------------
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS PIPELINE_ROL;
GRANT ROLE PIPELINE_ROL TO ROLE SYSADMIN;

GRANT USAGE ON WAREHOUSE APUESTAS_WH TO ROLE PIPELINE_ROL;
GRANT USAGE ON DATABASE APUESTAS TO ROLE PIPELINE_ROL;

-- RAW: puede cargar y releer, pero no crear ni borrar tablas.
GRANT USAGE ON SCHEMA APUESTAS.RAW TO ROLE PIPELINE_ROL;
GRANT SELECT, INSERT, DELETE ON TABLE APUESTAS.RAW.CUOTAS TO ROLE PIPELINE_ROL;
GRANT SELECT, INSERT, DELETE ON TABLE APUESTAS.RAW.PARTIDOS TO ROLE PIPELINE_ROL;
GRANT READ, WRITE ON STAGE APUESTAS.RAW.STAGE_CARGA TO ROLE PIPELINE_ROL;

-- ANALYTICS: dbt crea y reemplaza sus tablas y vistas.
GRANT USAGE, CREATE TABLE, CREATE VIEW ON SCHEMA APUESTAS.ANALYTICS TO ROLE PIPELINE_ROL;

-- Usuario de servicio: autenticación por llave RSA, sin contraseña.
CREATE USER IF NOT EXISTS PIPELINE_USUARIO
  TYPE = SERVICE
  DEFAULT_ROLE = PIPELINE_ROL
  DEFAULT_WAREHOUSE = APUESTAS_WH
  RSA_PUBLIC_KEY = '<PEGAR_LLAVE_PUBLICA>'
  COMMENT = 'Usuario del pipeline de Airflow + dbt';

-- Si el usuario ya existía (por ejemplo, creado desde otra máquina), CREATE USER IF NOT
-- EXISTS no cambia su llave: el ALTER deja registrada siempre la llave de este setup.
ALTER USER PIPELINE_USUARIO SET RSA_PUBLIC_KEY = '<PEGAR_LLAVE_PUBLICA>';

GRANT ROLE PIPELINE_ROL TO USER PIPELINE_USUARIO;

-- Para verificar: DESC USER PIPELINE_USUARIO;  (RSA_PUBLIC_KEY_FP no debe estar vacío)
