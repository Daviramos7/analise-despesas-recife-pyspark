"""Carga do Parquet limpo no Postgres (schema raw), via COPY.

Idempotente: recria a tabela a cada execução.
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


def carregar(origem: str = PARQUET_PADRAO) -> int:
    tabela = ds.dataset(origem, format="parquet", partitioning="hive").to_table()
    colunas = ", ".join(f'"{c.name}" {_tipo_pg(c.type)}' for c in tabela.schema)

    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("create schema if not exists raw")
        cur.execute(f"drop table if exists {TABELA}")
        cur.execute(f"create table {TABELA} ({colunas})")
        nomes = ", ".join(f'"{c}"' for c in tabela.column_names)
        with cur.copy(f"copy {TABELA} ({nomes}) from stdin") as copy:
            for lote in tabela.to_batches(max_chunksize=10_000):
                for linha in zip(*(col.to_pylist() for col in lote.columns)):
                    copy.write_row(linha)
        cur.execute(f"select count(*) from {TABELA}")
        total = cur.fetchone()[0]

    if total != tabela.num_rows:
        raise RuntimeError(f"carga inconsistente: parquet={tabela.num_rows} postgres={total}")
    print(f"[carga] {total} linhas em {TABELA}")
    return total


if __name__ == "__main__":
    carregar()
