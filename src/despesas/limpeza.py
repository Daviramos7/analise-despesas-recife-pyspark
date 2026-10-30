"""Camada bruto -> limpo.

Regras levantadas no profiling do CSV de 2023 (127.119 linhas):
- separador ';', UTF-8, tudo vem como texto entre aspas;
- alguns campos numéricos chegam com espaço à esquerda (" 2023", " 12");
- valores no formato brasileiro ("1.234,56"), podendo ser NEGATIVOS
  (anulação/estorno: é dado legítimo, NÃO filtrar);
- o mesmo código pode aparecer com nomes diferentes
  (ex.: elemento 37 = "LOCAÇÃO DE MÃO-DE-OBRA" e "LOCAÇÃO DE MÃO DE OBRA").
"""
from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, IntegerType, StringType

COLUNAS_INTEIRAS = [
    "ano_movimentacao",
    "mes_movimentacao",
    "empenho_ano",
    "empenho_numero",
    "subempenho",
]
COLUNAS_VALOR = ["valor_empenhado", "valor_liquidado", "valor_pago"]

# (coluna de código, coluna de nome) que precisam de nome canônico
PARES_CODIGO_NOME = [
    ("elemento_codigo", "elemento_nome"),
]


def valor_br_para_decimal(coluna: Column) -> Column:
    """'1.234,56' -> Decimal('1234.56'); '-12,30' -> Decimal('-12.30').

    String vazia ou só espaços vira null. Tipo de saída: DecimalType(18, 2).
    """
    valor = F.trim(coluna)
    valor = F.regexp_replace(valor, r"\.", "")   # separador de milhar
    valor = F.regexp_replace(valor, ",", ".")     # vírgula decimal
    return F.when(valor == "", F.lit(None)).otherwise(valor).cast(DecimalType(18, 2))


def aparar_textos(df: DataFrame) -> DataFrame:
    """Aplica trim em TODAS as colunas do tipo string e transforma '' em null."""
    for campo in df.schema.fields:
        if isinstance(campo.dataType, StringType):
            coluna = F.trim(F.col(campo.name))
            df = df.withColumn(
                campo.name,
                F.when(coluna == "", F.lit(None)).otherwise(coluna),
            )
    return df


def canonizar_nome(df: DataFrame, col_codigo: str, col_nome: str) -> DataFrame:
    """Garante 1 nome por código: usa o nome MAIS FREQUENTE daquele código.

    Empate na frequência -> escolhe o menor em ordem alfabética.
    Não pode mudar o número de linhas nem a ordem das colunas.
    """
    frequencias = (
        df
        .filter(F.col(col_codigo).isNotNull() & F.col(col_nome).isNotNull())
        .groupBy(col_codigo, col_nome)
        .agg(F.count("*").alias("frequencia"))
    )

    janela = (
        Window
        .partitionBy(col_codigo)
        .orderBy(F.desc("frequencia"), F.asc(col_nome))
    )

    nomes_canonicos = (
        frequencias
        .withColumn("posicao", F.row_number().over(janela))
        .filter(F.col("posicao") == 1)
        .select(col_codigo, F.col(col_nome).alias("nome_canonico"))
    )

    return (
        df
        .join(nomes_canonicos, on=col_codigo, how="left")
        .withColumn(col_nome, F.coalesce(F.col("nome_canonico"), F.col(col_nome)))
        .select(*df.columns)  # join joga a chave pra frente; restaura a ordem
    )


def limpar(df_bruto: DataFrame) -> DataFrame:
    """Pipeline completo da camada limpa.

    1. aparar_textos
    2. COLUNAS_INTEIRAS -> int
    3. COLUNAS_VALOR -> valor_br_para_decimal
    4. canonizar_nome para cada par de PARES_CODIGO_NOME
    """
    df = aparar_textos(df_bruto)

    for coluna in COLUNAS_INTEIRAS:
        df = df.withColumn(coluna, F.col(coluna).cast(IntegerType()))

    for coluna in COLUNAS_VALOR:
        df = df.withColumn(coluna, valor_br_para_decimal(F.col(coluna)))

    for col_codigo, col_nome in PARES_CODIGO_NOME:
        df = canonizar_nome(df, col_codigo, col_nome)

    return df
