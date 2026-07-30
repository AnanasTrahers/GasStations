# airflow_home — Airflow runtime home

## Purpose

Airflow `$AIRFLOW_HOME`. Holds runtime config and the `sys.path` bootstrap that lets DAG subprocesses import `src.*`.

## Ownership

- `config/airflow_local_settings.py` — prepends the project root to `sys.path` and loads `.env` via `dotenv`. Airflow auto-imports this file from `$AIRFLOW_HOME/config/` (it appends that dir to `sys.path` then `import airflow_local_settings`).
- `airflow.cfg` — intentionally minimal/empty; config is env-var driven (`AIRFLOW__*` keys in `.env`).
- `simple_auth_manager_passwords.json.generated` — generated auth-manager password store.

## Local Contracts

- `airflow_local_settings.py` is **required** for DAGs to import `src.*`. Placing it directly in `$AIRFLOW_HOME` is silently never loaded — it must live in `config/`.
- `.env` is only read by `src/config.py`'s pydantic Settings (and now by `airflow_local_settings.py` via `dotenv`); Airflow itself honors real env vars / `airflow.cfg`. Always invoke Airflow CLIs as `uv run --env-file .env airflow ...`.
- `AIRFLOW_HOME` and `AIRFLOW__CORE__DAGS_FOLDER` must be absolute paths matching the current checkout.

## Work Guidance

- Do not move `airflow_local_settings.py` out of `config/`.
- Keep `airflow.cfg` empty; drive config through env vars.

## Verification

- `uv run --env-file .env airflow dags list` succeeds and lists both DAGs (proves `src.*` imports resolve).

## Child DOX Index

None.
