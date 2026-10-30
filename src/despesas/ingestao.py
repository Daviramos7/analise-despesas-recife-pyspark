"""Job bruto (CSV) -> limpo (Parquet particionado por mês)."""
import argparse
import os

from pyspark.sql import DataFrame, SparkSession

from despesas.limpeza import limpar

CSV_PADRAO = "data/raw/despesas-orcamentarias-2023.csv"
PARQUET_PADRAO = "data/clean/despesas"


def criar_spark(app: str = "despesas-recife") -> SparkSession:
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


def executar(caminho_csv: str = CSV_PADRAO, destino: str = PARQUET_PADRAO) -> int:
    spark = criar_spark()
    try:
        limpo = limpar(ler_bruto(spark, caminho_csv))
        (
            limpo.write.mode("overwrite")
            .partitionBy("mes_movimentacao")
            .parquet(destino)
        )
        total = spark.read.parquet(destino).count()
        print(f"[ingestao] {total} linhas gravadas em {destino}")
        return total
    finally:
        spark.stop()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=CSV_PADRAO)
    p.add_argument("--destino", default=PARQUET_PADRAO)
    a = p.parse_args()
    executar(a.csv, a.destino)
