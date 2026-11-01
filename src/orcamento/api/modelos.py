"""Contratos da API (Pydantic). As descrições aqui são lidas pelo agente de IA."""
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Medida(str, Enum):
    empenhado = "empenhado"
    liquidado = "liquidado"
    pago = "pago"


DESCRICAO_MEDIDA = (
    "Estágio da despesa: 'empenhado' (valor reservado no orçamento), "
    "'liquidado' (serviço/bem entregue e reconhecido) ou 'pago' (dinheiro saiu). "
    "Na dúvida, use 'liquidado', que é o padrão para 'quanto foi gasto'."
)


class RespostaComAno(BaseModel):
    anos_dos_dados: list[int] = Field(
        description="Ano(s) a que TODOS os valores desta resposta se referem. "
                    "Não existem dados de outros anos.")


class Metadados(BaseModel):
    fonte: str
    anos_disponiveis: list[int]
    meses_disponiveis: list[int]
    granularidade_tempo: str
    medidas_despesa: list[str]
    tem_receitas: bool
    nao_disponivel: list[str] = Field(description="O que NÃO existe nos dados")
    observacoes: list[str]


class Orgao(BaseModel):
    orgao_codigo: str
    orgao_nome: str


class TotalOrgao(BaseModel):
    posicao: int = Field(description="Posição no ranking (1 = maior valor)")
    orgao_codigo: str
    orgao_nome: str
    valor: Decimal = Field(description="Total em R$ no período")
    participacao_pct: Decimal = Field(description="% do total da prefeitura no período")


class TotaisPorOrgao(RespostaComAno):
    medida: Medida
    mes_inicio: int
    mes_fim: int
    total_geral: Decimal = Field(description="Soma de TODOS os órgãos no período, em R$")
    orgaos: list[TotalOrgao]


class PontoMensal(BaseModel):
    ano_mes: str
    valor: Decimal = Field(description="Valor do mês em R$")
    variacao_abs: Decimal | None = Field(description="Diferença em R$ para o mês anterior")
    variacao_pct: Decimal | None = Field(description="Variação % em relação ao mês anterior")
    acumulado_ano: Decimal = Field(description="Soma de janeiro até este mês, em R$")


class EvolucaoMensal(RespostaComAno):
    medida: Medida
    orgao_codigo: str | None
    orgao_nome: str | None
    meses: list[PontoMensal]


class CredorRanking(BaseModel):
    posicao: int
    credor_nome: str
    credor_codigos: list[str] = Field(
        description="Códigos de credor consolidados sob este nome (a fonte cadastra filiais/"
                    "cadastros da mesma empresa com códigos diferentes)")
    valor: Decimal


class RankingCredores(RespostaComAno):
    medida: Medida
    orgao_codigo: str | None
    orgao_nome: str | None
    credores: list[CredorRanking]


class TotalFuncao(BaseModel):
    posicao: int
    funcao_codigo: str
    funcao_nome: str
    valor: Decimal
    participacao_pct: Decimal


class TotaisPorFuncao(RespostaComAno):
    medida: Medida
    mes_inicio: int
    mes_fim: int
    total_geral: Decimal
    funcoes: list[TotalFuncao]


# ------------------------------------------------------------------ receitas
class TotalOrigemReceita(BaseModel):
    posicao: int
    categoria_receita_nome: str
    origem_nome: str = Field(description="Origem da receita (ex. Impostos, Transferências)")
    arrecadado: Decimal = Field(description="Arrecadado no período, em R$")
    previsto_atualizado: Decimal = Field(description="Previsão atualizada no período, em R$")
    execucao_pct: Decimal | None = Field(description="arrecadado / previsto_atualizado, em %")


class ReceitasPorOrigem(RespostaComAno):
    mes_inicio: int
    mes_fim: int
    total_arrecadado: Decimal = Field(description="Total arrecadado pela prefeitura no período, em R$")
    total_previsto_atualizado: Decimal
    total_execucao_pct: Decimal | None = Field(
        description="total_arrecadado / total_previsto_atualizado, em %")
    origens: list[TotalOrigemReceita]


class ItemReceita(BaseModel):
    alinea_codigo: str
    alinea_nome: str = Field(description="Receita específica (ex. IPTU, ISS, FPM)")
    origem_nome: str
    arrecadado: Decimal
    previsto_atualizado: Decimal


class BuscaItensReceita(RespostaComAno):
    busca: str
    mes_inicio: int
    mes_fim: int
    itens: list[ItemReceita]


class PontoMensalReceita(BaseModel):
    ano_mes: str
    arrecadado: Decimal
    variacao_abs: Decimal | None
    variacao_pct: Decimal | None
    acumulado_ano: Decimal


class EvolucaoMensalReceita(RespostaComAno):
    meses: list[PontoMensalReceita]


class ComparativoMes(BaseModel):
    ano_mes: str
    receita_arrecadada: Decimal
    despesa: Decimal
    saldo: Decimal = Field(description="receita_arrecadada - despesa, em R$")


class ComparativoReceitaDespesa(RespostaComAno):
    medida_despesa: Medida
    mes_inicio: int
    mes_fim: int
    excluir_intraorcamentarias: bool
    receita_arrecadada: Decimal
    despesa: Decimal
    saldo: Decimal = Field(description="Positivo = arrecadou mais do que gastou")
    meses: list[ComparativoMes]
