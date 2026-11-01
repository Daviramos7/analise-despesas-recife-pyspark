"""Ponto de entrada: python -m despesas.pipeline (despesas + receitas)."""
from despesas.carga import carregar
from despesas.ingestao import DATASETS, criar_spark, executar

if __name__ == "__main__":
    spark = criar_spark()
    try:
        for nome in DATASETS:
            executar(nome, spark)
    finally:
        spark.stop()
    for nome, ds in DATASETS.items():
        carregar(ds.destino, f"raw.{nome}")
