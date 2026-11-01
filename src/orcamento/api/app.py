"""API de despesas públicas do Recife, desenhada para ser consumida por um agente de IA.

Regra de ouro: as descrições de endpoint e parâmetro são o "manual" do agente.
Elas dizem o que cada rota responde, em que unidade e o que ela NÃO responde.
"""
import unicodedata
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query
from psycopg.rows import dict_row

from orcamento.api import consultas
from orcamento.api.modelos import (
    DESCRICAO_MEDIDA,
    BuscaItensReceita,
    ComparativoReceitaDespesa,
    EvolucaoMensalReceita,
    ItemReceita,
    ReceitasPorOrigem,
    EvolucaoMensal,
    Medida,
    Metadados,
    Orgao,
    RankingCredores,
    TotaisPorFuncao,
    TotaisPorOrgao,
)
from orcamento.config import dsn

app = FastAPI(
    title="Receitas e Despesas Públicas do Recife",
    version="0.3.0",
    description=(
        "Receitas e despesas orçamentárias da Prefeitura do Recife (Portal de Dados Abertos). "
        "Valores em reais (R$), agregados por mês. Consulte /metadados para saber "
        "o que existe e o que NÃO existe nos dados."
    ),
)


def conexao() -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(conexao)]
MedidaQ = Annotated[Medida, Query(description=DESCRICAO_MEDIDA)]
MesInicio = Annotated[int, Query(ge=1, le=12, description="Mês inicial (1-12), inclusivo")]
MesFim = Annotated[int, Query(ge=1, le=12, description="Mês final (1-12), inclusivo")]
OrgaoQ = Annotated[
    str | None,
    Query(description="Código do órgão (ex. '48'). Descubra o código em /orgaos. "
                      "Omita para a prefeitura inteira."),
]


def _sem_acento(txt: str) -> str:
    nfkd = unicodedata.normalize("NFKD", txt.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _nome_orgao(conn: psycopg.Connection, codigo: str | None) -> str | None:
    if codigo is None:
        return None
    linha = conn.execute(
        "select orgao_nome from marts.dim_unidade where orgao_codigo = %s limit 1", (codigo,)
    ).fetchone()
    if linha is None:
        raise HTTPException(404, f"Órgão '{codigo}' não existe. Use /orgaos para buscar o código.")
    return linha["orgao_nome"]


# Sigla -> trechos (sem acento) que aparecem nos nomes oficiais das alíneas de receita.
SIGLAS_RECEITA: dict[str, tuple[str, ...]] = {
    "IPTU": ("propriedade predial e territorial urbana",),
    "ISS": ("impostos sobre servicos",),
    "ISSQN": ("impostos sobre servicos",),
    "ITBI": ("transmissao",),
    "IRRF": ("imposto sobre a renda",),
    "FPM": ("fundo de participacao dos municipios",),
    "ICMS": ("icms",),
    "IPVA": ("ipva",),
    "FUNDEB": ("fundeb", "educacao basica"),
    "SUS": ("sistema unico de saude",),
    "COSIP": ("iluminacao publica",),
}


# 'ano' existe para consumo humano/programático, mas fica FORA do OpenAPI (e portanto das
# tools do agente). Evals 2026-11-01: expor 'ano' ao qwen2.5:7b derrubou o acerto de 90% para
# ~78% (o modelo passou a chamar ano=2022 sozinho e a recusar perguntas de 2023).
AnoQ = Annotated[int | None, Query(ge=1900, le=2100, include_in_schema=False)]


def _anos(conn: psycopg.Connection) -> list[int]:
    return [r["ano"] for r in conn.execute("select distinct ano from marts.dim_mes order by 1").fetchall()]


def _validar_ano(conn: psycopg.Connection, ano: int | None) -> None:
    if ano is not None and ano not in (anos := _anos(conn)):
        raise HTTPException(404, f"Não há dados para o ano {ano}. Anos disponíveis: {anos}.")


def _validar_periodo(mes_inicio: int, mes_fim: int) -> None:
    if mes_inicio > mes_fim:
        raise HTTPException(422, "mes_inicio não pode ser maior que mes_fim")


@app.get("/metadados", response_model=Metadados, summary="O que existe (e o que não existe) nos dados")
def metadados(conn: Conn) -> Metadados:
    """Chame PRIMEIRO quando a pergunta envolver ano, período, receita ou um nível de
    detalhe que talvez não exista. Diz quais anos/meses estão disponíveis e o que falta."""
    meses = conn.execute(consultas.META_MESES).fetchall()
    tem_receitas = conn.execute(
        "select to_regclass('marts.fato_receita_movimento') is not null as ok"
    ).fetchone()["ok"]
    return Metadados(
        fonte="Portal de Dados Abertos do Recife — despesas e receitas orçamentárias",
        anos_disponiveis=sorted({m["ano"] for m in meses}),
        meses_disponiveis=[m["mes"] for m in meses],
        granularidade_tempo="mensal (não há data por dia)",
        medidas_despesa=[m.value for m in Medida],
        tem_receitas=tem_receitas,
        nao_disponivel=[
            "anos diferentes dos listados em anos_disponiveis",
            "valores por dia ou por semana",
            "localização geográfica (bairro, RPA)",
            "dados individuais de servidores (salário por pessoa)",
            "CPF/CNPJ de credores",
        ],
        observacoes=[
            "Valores negativos num mês são anulações/estornos e entram nas somas.",
            "Credor 'CREDOR NÃO INFORMADO' corresponde majoritariamente a folha de pessoal.",
        ],
    )


@app.get("/orgaos", response_model=list[Orgao], summary="Lista/busca órgãos da prefeitura")
def orgaos(
    conn: Conn,
    busca: Annotated[str | None, Query(
        description="Trecho do nome, sem precisar de acento (ex. 'saude', 'educacao')")] = None,
) -> list[Orgao]:
    """Use para descobrir o orgao_codigo a partir do nome antes de filtrar outras rotas."""
    linhas = [Orgao(**r) for r in conn.execute(consultas.ORGAOS).fetchall()]
    if busca:
        alvo = _sem_acento(busca)
        linhas = [o for o in linhas if alvo in _sem_acento(o.orgao_nome)]
    return linhas


@app.get("/despesas/orgaos", response_model=TotaisPorOrgao,
         summary="Total de despesa por órgão num período, com ranking e % do total")
def despesas_por_orgao(
    conn: Conn,
    medida: MedidaQ = Medida.liquidado,
    mes_inicio: MesInicio = 1,
    mes_fim: MesFim = 12,
    limite: Annotated[int, Query(ge=1, le=100, description="Quantos órgãos retornar")] = 10,
    ano: AnoQ = None,
) -> TotaisPorOrgao:
    """Responde: 'quanto o órgão X gastou', 'quais órgãos mais gastaram', 'qual a fatia do
    órgão X no total', 'quanto a prefeitura gastou no total' (campo total_geral).
    Órgãos são secretarias e entidades da PREFEITURA; para empresas/fornecedores use
    despesas_credores_ranking."""
    _validar_ano(conn, ano)
    _validar_periodo(mes_inicio, mes_fim)
    linhas = conn.execute(
        consultas.totais_por_orgao(medida), {"mes_inicio": mes_inicio, "mes_fim": mes_fim, "ano": ano}
    ).fetchall()
    total = linhas[0]["total_geral"] if linhas else 0
    return TotaisPorOrgao(anos_dos_dados=[ano] if ano else _anos(conn), medida=medida, mes_inicio=mes_inicio, mes_fim=mes_fim,
                          total_geral=total, orgaos=linhas[:limite])


@app.get("/despesas/evolucao-mensal", response_model=EvolucaoMensal,
         summary="Despesa mês a mês, com variação e acumulado no ano")
def despesas_evolucao_mensal(
    conn: Conn,
    medida: MedidaQ = Medida.liquidado,
    orgao_codigo: OrgaoQ = None,
    ano: AnoQ = None,
) -> EvolucaoMensal:
    """Responde: 'quanto foi gasto em <mês>', 'variação de um mês para o outro',
    'qual mês teve o maior gasto', 'acumulado até <mês>'. Prefeitura inteira ou um órgão."""
    _validar_ano(conn, ano)
    nome = _nome_orgao(conn, orgao_codigo)
    linhas = conn.execute(
        consultas.evolucao_mensal(medida), {"orgao_codigo": orgao_codigo, "ano": ano}
    ).fetchall()
    return EvolucaoMensal(anos_dos_dados=[ano] if ano else _anos(conn), medida=medida, orgao_codigo=orgao_codigo, orgao_nome=nome, meses=linhas)


@app.get("/despesas/credores/ranking", response_model=RankingCredores,
         summary="Maiores credores/fornecedores por valor")
def despesas_ranking_credores(
    conn: Conn,
    medida: MedidaQ = Medida.pago,
    orgao_codigo: OrgaoQ = None,
    limite: Annotated[int, Query(ge=1, le=50, description="Tamanho do ranking")] = 10,
    incluir_nao_informado: Annotated[bool, Query(
        description="Incluir 'CREDOR NÃO INFORMADO' (folha de pessoal). Padrão: não")] = False,
    busca: Annotated[str | None, Query(
        description="Trecho do nome do credor, sem precisar de acento (ex. 'caixa economica'). "
                    "Use para perguntas sobre uma empresa/pessoa específica.")] = None,
    ano: AnoQ = None,
) -> RankingCredores:
    """Credores são EMPRESAS, bancos, fundos ou pessoas que RECEBERAM dinheiro da prefeitura.
    Responde: 'quem mais recebeu', 'maiores fornecedores do órgão X', 'quanto a empresa X
    recebeu' (use busca). Valores consolidados por nome do credor. Padrão: medida 'pago'."""
    _validar_ano(conn, ano)
    nome = _nome_orgao(conn, orgao_codigo)
    linhas = conn.execute(consultas.ranking_credores(medida), {
        "orgao_codigo": orgao_codigo, "limite": limite,
        "incluir_nao_informado": incluir_nao_informado,
        "busca": _sem_acento(busca) if busca else None, "ano": ano,
    }).fetchall()
    return RankingCredores(anos_dos_dados=[ano] if ano else _anos(conn), medida=medida, orgao_codigo=orgao_codigo, orgao_nome=nome, credores=linhas)


@app.get("/despesas/funcoes", response_model=TotaisPorFuncao,
         summary="Despesa por área de governo (função: Saúde, Educação, Urbanismo...)")
def despesas_por_funcao(
    conn: Conn,
    medida: MedidaQ = Medida.liquidado,
    mes_inicio: MesInicio = 1,
    mes_fim: MesFim = 12,
    ano: AnoQ = None,
) -> TotaisPorFuncao:
    """Responde 'quanto foi gasto COM saúde/educação' (a área), que é diferente de
    'quanto a SECRETARIA de Saúde gastou' (o órgão, use /despesas/orgaos)."""
    _validar_ano(conn, ano)
    _validar_periodo(mes_inicio, mes_fim)
    linhas = conn.execute(
        consultas.totais_por_funcao(medida), {"mes_inicio": mes_inicio, "mes_fim": mes_fim, "ano": ano}
    ).fetchall()
    total = linhas[0]["total_geral"] if linhas else 0
    return TotaisPorFuncao(anos_dos_dados=[ano] if ano else _anos(conn), medida=medida, mes_inicio=mes_inicio, mes_fim=mes_fim,
                           total_geral=total, funcoes=linhas)


# --------------------------------------------------------------------- receitas
def _exige_receitas(conn: psycopg.Connection) -> None:
    ok = conn.execute(
        "select to_regclass('marts.fato_receita_movimento') is not null as ok"
    ).fetchone()["ok"]
    if not ok:
        raise HTTPException(404, "Dados de receita não estão carregados.")


@app.get("/receitas/origens", response_model=ReceitasPorOrigem,
         summary="Receita arrecadada e prevista por origem (Impostos, Transferências...)")
def receitas_por_origem(conn: Conn, mes_inicio: MesInicio = 1, mes_fim: MesFim = 12,
                        ano: AnoQ = None) -> ReceitasPorOrigem:
    """Responde: 'quanto a prefeitura arrecadou' (total_arrecadado), 'quanto veio de impostos /
    transferências', '% da receita prevista que foi arrecadada' (total_execucao_pct no total,
    execucao_pct por origem)."""
    _exige_receitas(conn)
    _validar_ano(conn, ano)
    _validar_periodo(mes_inicio, mes_fim)
    linhas = conn.execute(consultas.RECEITAS_POR_ORIGEM,
                          {"mes_inicio": mes_inicio, "mes_fim": mes_fim, "ano": ano}).fetchall()
    arrecadado = linhas[0]["total_arrecadado"] if linhas else 0
    previsto = linhas[0]["total_previsto_atualizado"] if linhas else 0
    return ReceitasPorOrigem(
        anos_dos_dados=[ano] if ano else _anos(conn), mes_inicio=mes_inicio, mes_fim=mes_fim,
        total_arrecadado=arrecadado, total_previsto_atualizado=previsto,
        total_execucao_pct=round(100 * arrecadado / previsto, 2) if previsto else None,
        origens=linhas,
    )


@app.get("/receitas/itens", response_model=BuscaItensReceita,
         summary="Busca uma receita específica pelo nome (IPTU, ISS, FPM, ICMS...)")
def receitas_itens(
    conn: Conn,
    busca: Annotated[str, Query(min_length=2, description=(
        "Trecho do nome da receita, sem precisar de acento. Siglas comuns são expandidas: "
        "IPTU, ISS, ITBI, IRRF, FPM, ICMS, IPVA, FUNDEB, SUS, COSIP."))],
    mes_inicio: MesInicio = 1,
    mes_fim: MesFim = 12,
    ano: AnoQ = None,
) -> BuscaItensReceita:
    """Responde 'quanto foi arrecadado de IPTU/ISS/...'. Retorna lista vazia se nada casar."""
    _exige_receitas(conn)
    _validar_ano(conn, ano)
    _validar_periodo(mes_inicio, mes_fim)
    termos = SIGLAS_RECEITA.get(busca.strip().upper(), (_sem_acento(busca),))
    linhas = conn.execute(consultas.RECEITAS_POR_ALINEA,
                          {"mes_inicio": mes_inicio, "mes_fim": mes_fim, "ano": ano}).fetchall()
    itens = [ItemReceita(**r) for r in linhas
             if any(t in _sem_acento(r["alinea_nome"]) for t in termos)]
    return BuscaItensReceita(anos_dos_dados=[ano] if ano else _anos(conn), busca=busca, mes_inicio=mes_inicio, mes_fim=mes_fim, itens=itens)


@app.get("/receitas/evolucao-mensal", response_model=EvolucaoMensalReceita,
         summary="Receita arrecadada mês a mês, com variação e acumulado no ano")
def receitas_evolucao_mensal(conn: Conn, ano: AnoQ = None) -> EvolucaoMensalReceita:
    """Responde: 'quanto foi arrecadado em <mês>', 'mês de maior arrecadação', 'acumulado até <mês>'."""
    _exige_receitas(conn)
    _validar_ano(conn, ano)
    return EvolucaoMensalReceita(
        anos_dos_dados=[ano] if ano else _anos(conn), meses=conn.execute(consultas.RECEITAS_EVOLUCAO, {"ano": ano}).fetchall())


@app.get("/comparativo/receita-despesa", response_model=ComparativoReceitaDespesa,
         summary="Receita arrecadada x despesa no período, com saldo mês a mês")
def comparativo_receita_despesa(
    conn: Conn,
    medida_despesa: MedidaQ = Medida.liquidado,
    mes_inicio: MesInicio = 1,
    mes_fim: MesFim = 12,
    excluir_intraorcamentarias: Annotated[bool, Query(description=(
        "Excluir operações entre órgãos da própria prefeitura (contadas como receita num órgão "
        "e despesa no outro). Padrão: true, para não contar o mesmo valor duas vezes."))] = True,
    ano: AnoQ = None,
) -> ComparativoReceitaDespesa:
    """Responde: 'a prefeitura arrecadou mais do que gastou?', 'qual foi o saldo', 'em que
    meses a despesa superou a receita'."""
    _exige_receitas(conn)
    _validar_ano(conn, ano)
    _validar_periodo(mes_inicio, mes_fim)
    meses = conn.execute(consultas.comparativo(medida_despesa), {
        "mes_inicio": mes_inicio, "mes_fim": mes_fim, "excluir": excluir_intraorcamentarias,
        "ano": ano,
    }).fetchall()
    receita = sum((m["receita_arrecadada"] for m in meses), start=0)
    despesa = sum((m["despesa"] for m in meses), start=0)
    return ComparativoReceitaDespesa(
        anos_dos_dados=[ano] if ano else _anos(conn), medida_despesa=medida_despesa, mes_inicio=mes_inicio, mes_fim=mes_fim,
        excluir_intraorcamentarias=excluir_intraorcamentarias,
        receita_arrecadada=receita, despesa=despesa, saldo=receita - despesa, meses=meses,
    )
