"""Carga do Parquet limpo no Postgres (schema raw), via COPY.

Idempotente: TRUNCATE + COPY numa única transação.
- Não usa DROP: as views do dbt (staging) dependem desta tabela.
- Se algo falhar no meio, o rollback mantém os dados anteriores intactos.
- Se o schema do Parquet mudar, a carga falha de forma explícita (ver _validar_colunas).
"""
import os

import psycopg
import pyarrow.dataset as ds

PARQUET_PADRAO = "data/clean/despesas"
TABELA = "raw.despesas"

TIPOS_PG = {
    "int32": "integer",
    "int64": "bigint",
    "string": "text",
    "large_string": "text",
}


def _tipo_pg(tipo_arrow) -> str:
    nome = str(tipo_arrow)
    if nome.startswith("decimal"):
        return "numeric(18,2)"
    return TIPOS_PG.get(nome, "text")


def dsn() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'despesas')} user={os.getenv('PGUSER', 'despesas')} "
        f"password={os.getenv('PGPASSWORD', 'despesas')}"
    )


def _validar_colunas(cur, esperadas: list[str]) -> None:
    schema, tabela = TABELA.split(".")
    cur.execute(
        "select column_name from information_schema.columns "
        "where table_schema = %s and table_name = %s",
        (schema, tabela),
    )
    existentes = {r[0] for r in cur.fetchall()}
    if existentes != set(esperadas):
        raise RuntimeError(
            f"schema de {TABELA} divergente do Parquet. "
            f"faltando={sorted(set(esperadas) - existentes)} "
            f"sobrando={sorted(existentes - set(esperadas))}. "
            "Recrie o volume do Postgres: docker compose down -v"
        )


def carregar(origem: str = PARQUET_PADRAO) -> int:
    tabela = ds.dataset(origem, format="parquet", partitioning="hive").to_table()
    colunas = ", ".join(f'"{c.name}" {_tipo_pg(c.type)}' for c in tabela.schema)

    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("create schema if not exists raw")
        cur.execute(f"create table if not exists {TABELA} ({colunas})")
        _validar_colunas(cur, tabela.column_names)
        cur.execute(f"truncate table {TABELA}")
        nomes = ", ".join(f'"{c}"' for c in tabela.column_names)
        with cur.copy(f"copy {TABELA} ({nomes}) from stdin") as copy:
            for lote in tabela.to_batches(max_chunksize=10_000):
                for linha in zip(*(col.to_pylist() for col in lote.columns)):
                    copy.write_row(linha)
        cur.execute(f"select count(*) from {TABELA}")
        total = cur.fetchone()[0]
        # erro aqui dentro => o "with psycopg.connect" faz rollback (dados antigos ficam)
        if total != tabela.num_rows:
            raise RuntimeError(
                f"carga inconsistente: parquet={tabela.num_rows} postgres={total}"
            )

    print(f"[carga] {total} linhas em {TABELA}")
    return total


if __name__ == "__main__":
    carregar()
