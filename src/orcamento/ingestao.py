"""Job bruto (CSV) -> limpo (Parquet particionado por mês), para cada dataset."""
import argparse
import os
from collections.abc import Callable
from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession

from orcamento.limpeza import limpar, limpar_receitas


@dataclass(frozen=True)
class Dataset:
    csv: str
    destino: str
    limpeza: Callable[[DataFrame], DataFrame]
    coluna_mes: str


DATASETS = {
    "despesas": Dataset(
        "data/raw/despesas-orcamentarias-2023.csv", "data/clean/despesas", limpar, "mes_movimentacao"
    ),
    "receitas": Dataset(
        "data/raw/receitas-orcamentarias-2023.csv", "data/clean/receitas", limpar_receitas, "mes"
    ),
}


def criar_spark(app: str = "orcamento-publico-recife") -> SparkSession:
    os.environ.setdefault("SPARK_LOCAL_HOSTNAME", "localhost")
    return (
        SparkSession.builder.master("local[*]")
        .appName(app)
        .config("spark.sql.session.timeZone", "America/Recife")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )


def ler_bruto(spark: SparkSession, caminho: str) -> DataFrame:
    # tudo como string: tipagem é responsabilidade da camada limpa
    return spark.read.csv(
        caminho, sep=";", header=True, encoding="UTF-8", quote='"', inferSchema=False
    )


def executar(nome: str = "despesas", spark: SparkSession | None = None) -> int:
    ds = DATASETS[nome]
    proprio = spark is None
    spark = spark or criar_spark()
    try:
        limpo = ds.limpeza(ler_bruto(spark, ds.csv))
        limpo.write.mode("overwrite").partitionBy(ds.coluna_mes).parquet(ds.destino)
        total = spark.read.parquet(ds.destino).count()
        print(f"[ingestao] {nome}: {total} linhas gravadas em {ds.destino}")
        return total
    finally:
        if proprio:
            spark.stop()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("dataset", choices=sorted(DATASETS), nargs="?", default="despesas")
    executar(p.parse_args().dataset)
