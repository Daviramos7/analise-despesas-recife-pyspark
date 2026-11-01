from decimal import Decimal

import pytest
from pyspark.sql import Row
from pyspark.sql.types import DecimalType, IntegerType

from despesas.limpeza import (
    aparar_textos,
    canonizar_nome,
    limpar,
    valor_br_para_decimal,
)


# ---------- valor_br_para_decimal ----------

@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("16229,00", Decimal("16229.00")),
        ("1.234,56", Decimal("1234.56")),
        ("1.000.000,01", Decimal("1000000.01")),
        ("-12,30", Decimal("-12.30")),  # anulação: negativo é válido
        ("0,00", Decimal("0.00")),
        ("", None),
        ("   ", None),
    ],
)
def test_valor_br_para_decimal(spark, entrada, esperado):
    df = spark.createDataFrame([Row(v=entrada)])
    linha = df.select(valor_br_para_decimal(df.v).alias("v")).first()
    assert linha.v == esperado


def test_valor_br_para_decimal_tipo(spark):
    df = spark.createDataFrame([Row(v="1,00")])
    saida = df.select(valor_br_para_decimal(df.v).alias("v"))
    assert saida.schema["v"].dataType == DecimalType(18, 2)


# ---------- aparar_textos ----------

def test_aparar_textos_remove_espacos_e_vazio_vira_null(spark):
    df = spark.createDataFrame([Row(a=" 2023", b="  ", c="ok ")])
    linha = aparar_textos(df).first()
    assert (linha.a, linha.b, linha.c) == ("2023", None, "ok")


# ---------- canonizar_nome ----------

def test_canonizar_nome_usa_o_mais_frequente(spark):
    df = spark.createDataFrame(
        [
            Row(cod="37", nome="LOCAÇÃO DE MÃO DE OBRA"),
            Row(cod="37", nome="LOCAÇÃO DE MÃO DE OBRA"),
            Row(cod="37", nome="LOCAÇÃO DE MÃO-DE-OBRA"),
            Row(cod="99", nome="OUTRO"),
        ]
    )
    saida = canonizar_nome(df, "cod", "nome")
    assert saida.count() == 4
    assert saida.columns == ["cod", "nome"]
    nomes = {(r.cod, r.nome) for r in saida.collect()}
    assert nomes == {("37", "LOCAÇÃO DE MÃO DE OBRA"), ("99", "OUTRO")}


def test_canonizar_nome_empate_pega_menor_alfabetico(spark):
    df = spark.createDataFrame(
        [Row(cod="41", nome="CONTRIBUIÇÕES"), Row(cod="41", nome="CONTRIBUIÇOES")]
    )
    nomes = {r.nome for r in canonizar_nome(df, "cod", "nome").collect()}
    assert nomes == {min("CONTRIBUIÇÕES", "CONTRIBUIÇOES")}


# ---------- limpar (integração) ----------

def _linha_bruta(**sobrescrever):
    base = dict(
        ano_movimentacao="2023",
        mes_movimentacao="5",
        empenho_ano=" 2023",
        empenho_numero=" 12",
        subempenho=" 0",
        elemento_codigo="35",
        elemento_nome="SERVIÇOS DE CONSULTORIA",
        credor_codigo="04301727",
        valor_empenhado="16229,00",
        valor_liquidado="0,00",
        valor_pago="-1,50",
    )
    base.update(sobrescrever)
    return Row(**base)


def test_limpar_tipos_e_valores(spark):
    df = spark.createDataFrame([_linha_bruta()])
    saida = limpar(df)
    tipos = {c.name: c.dataType for c in saida.schema}

    for col in ["ano_movimentacao", "mes_movimentacao", "empenho_ano",
                "empenho_numero", "subempenho"]:
        assert tipos[col] == IntegerType(), col
    for col in ["valor_empenhado", "valor_liquidado", "valor_pago"]:
        assert tipos[col] == DecimalType(18, 2), col

    linha = saida.first()
    assert linha.empenho_numero == 12
    assert linha.valor_empenhado == Decimal("16229.00")
    assert linha.valor_pago == Decimal("-1.50")
    assert linha.credor_codigo == "04301727"  # código é texto: zero à esquerda fica


def test_limpar_preserva_linhas_e_credor_nao_informado(spark):
    df = spark.createDataFrame(
        [_linha_bruta(), _linha_bruta(mes_movimentacao="6", credor_codigo="0")]
    )
    saida = limpar(df)
    assert saida.count() == 2
    assert {r.credor_codigo for r in saida.collect()} == {"04301727", "0"}


# ---------- limpar_receitas ----------

def test_limpar_receitas_tipos_valores_e_remove_mes_nome(spark):
    from despesas.limpeza import limpar_receitas

    df = spark.createDataFrame([Row(
        ano="2023", mes=" 7", mes_nome="Julho", unidade_codigo="15.01",
        receita_prevista="553.000.000,00", receita_prevista_acrescimo="0,00",
        receita_prevista_atualizada="553.000.000,00", receita_arrecadada="-10,50",
    )])
    saida = limpar_receitas(df)
    linha = saida.first()

    assert "mes_nome" not in saida.columns
    assert saida.schema["mes"].dataType == IntegerType()
    assert linha.mes == 7
    assert linha.receita_prevista == Decimal("553000000.00")
    assert linha.receita_arrecadada == Decimal("-10.50")  # dedução: negativo é válido
