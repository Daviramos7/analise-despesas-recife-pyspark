"""Configuração por variável de ambiente (nada de segredo no código)."""
import os


def dsn() -> str:
    return (
        f"host={os.getenv('PGHOST', 'localhost')} port={os.getenv('PGPORT', '5432')} "
        f"dbname={os.getenv('PGDATABASE', 'despesas')} user={os.getenv('PGUSER', 'despesas')} "
        f"password={os.getenv('PGPASSWORD', 'despesas')}"
    )
