import os

import pytest
from pyspark.sql import SparkSession

os.environ.setdefault("SPARK_LOCAL_HOSTNAME", "localhost")


@pytest.fixture(scope="session")
def spark():
    sessao = (
        SparkSession.builder.master("local[1]")
        .appName("testes-despesas")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield sessao
    sessao.stop()
