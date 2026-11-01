"""SQL das análises. Toda coluna dinâmica vem de whitelist (sem SQL injection)."""
from psycopg import sql

from despesas.api.modelos import Medida

COLUNA_MEDIDA = {
    Medida.empenhado: "valor_empenhado",
    Medida.liquidado: "valor_liquidado",
    Medida.pago: "valor_pago",
}


def _col(medida: Medida) -> sql.Identifier:
    return sql.Identifier(COLUNA_MEDIDA[medida])


def totais_por_orgao(medida: Medida) -> sql.Composed:
    return sql.SQL("""
        with por_orgao as (
            select u.orgao_codigo, u.orgao_nome, sum(f.{col}) as valor
            from marts.fato_despesa_movimento f
            join marts.dim_unidade u using (sk_unidade)
            join marts.dim_mes m using (sk_mes)
            where m.mes between %(mes_inicio)s and %(mes_fim)s and (%(ano)s::int is null or m.ano = %(ano)s)
            group by 1, 2
        )
        select
            rank() over (order by valor desc)                       as posicao,
            orgao_codigo, orgao_nome, valor,
            round(100 * valor / nullif(sum(valor) over (), 0), 2)   as participacao_pct,
            sum(valor) over ()                                      as total_geral
        from por_orgao
        order by valor desc
    """).format(col=_col(medida))


def evolucao_mensal(medida: Medida) -> sql.Composed:
    return sql.SQL("""
        with por_mes as (
            select m.sk_mes, m.ano_mes, sum(f.{col}) as valor
            from marts.fato_despesa_movimento f
            join marts.dim_mes m using (sk_mes)
            join marts.dim_unidade u using (sk_unidade)
            where (%(orgao_codigo)s::text is null or u.orgao_codigo = %(orgao_codigo)s)
              and (%(ano)s::int is null or m.ano = %(ano)s)
            group by 1, 2
        )
        select
            ano_mes,
            valor,
            valor - lag(valor) over (order by sk_mes)                         as variacao_abs,
            round(100 * (valor - lag(valor) over (order by sk_mes))
                  / nullif(lag(valor) over (order by sk_mes), 0), 2)          as variacao_pct,
            sum(valor) over (order by sk_mes)                                 as acumulado_ano
        from por_mes
        order by sk_mes
    """).format(col=_col(medida))


def ranking_credores(medida: Medida) -> sql.Composed:
    return sql.SQL("""
        -- Consolida por NOME: a fonte tem 572 nomes com mais de um código de credor
        -- (ex.: CAIXA ECONOMICA FEDERAL com 5 códigos).
        with por_credor as (
            select c.credor_nome,
                   array_agg(distinct c.credor_codigo order by c.credor_codigo) as credor_codigos,
                   sum(f.{col}) as valor
            from marts.fato_despesa_movimento f
            join marts.dim_credor c using (sk_credor)
            join marts.dim_unidade u using (sk_unidade)
            join marts.dim_mes m using (sk_mes)
            where (%(orgao_codigo)s::text is null or u.orgao_codigo = %(orgao_codigo)s)
              and (c.credor_informado or %(incluir_nao_informado)s)
              and (%(ano)s::int is null or m.ano = %(ano)s)
            group by 1
        )
        , ranqueado as (
            select rank() over (order by valor desc) as posicao, credor_nome, credor_codigos, valor
            from por_credor
        )
        select * from ranqueado
        where %(busca)s::text is null
           or translate(lower(credor_nome), 'áàâãéêíóôõúç', 'aaaaeeiooouc') like '%%' || %(busca)s || '%%'
        order by valor desc
        limit %(limite)s
    """).format(col=_col(medida))


def totais_por_funcao(medida: Medida) -> sql.Composed:
    return sql.SQL("""
        with por_funcao as (
            select fc.funcao_codigo, fc.funcao_nome, sum(f.{col}) as valor
            from marts.fato_despesa_movimento f
            join marts.dim_classif_funcional fc using (sk_classif_funcional)
            join marts.dim_mes m using (sk_mes)
            where m.mes between %(mes_inicio)s and %(mes_fim)s and (%(ano)s::int is null or m.ano = %(ano)s)
            group by 1, 2
        )
        select
            rank() over (order by valor desc)                       as posicao,
            funcao_codigo, funcao_nome, valor,
            round(100 * valor / nullif(sum(valor) over (), 0), 2)   as participacao_pct,
            sum(valor) over ()                                      as total_geral
        from por_funcao
        order by valor desc
    """).format(col=_col(medida))


ORGAOS = """
    select distinct orgao_codigo, orgao_nome from marts.dim_unidade order by orgao_codigo
"""
META_MESES = "select distinct ano, mes from marts.dim_mes order by ano, mes"


# ------------------------------------------------------------------ receitas
RECEITAS_POR_ORIGEM = """
    with por_origem as (
        select n.categoria_receita_nome, n.origem_nome,
               sum(f.valor_arrecadado) as arrecadado,
               sum(f.valor_previsto_atualizado) as previsto_atualizado
        from marts.fato_receita_movimento f
        join marts.dim_classif_receita n using (sk_classif_receita)
        join marts.dim_mes m using (sk_mes)
        where m.mes between %(mes_inicio)s and %(mes_fim)s and (%(ano)s::int is null or m.ano = %(ano)s)
        group by 1, 2
    )
    select
        rank() over (order by arrecadado desc)                       as posicao,
        categoria_receita_nome, origem_nome, arrecadado, previsto_atualizado,
        round(100 * arrecadado / nullif(previsto_atualizado, 0), 2)  as execucao_pct,
        sum(arrecadado) over ()                                      as total_arrecadado,
        sum(previsto_atualizado) over ()                             as total_previsto_atualizado
    from por_origem
    order by arrecadado desc
"""

RECEITAS_POR_ALINEA = """
    select n.alinea_codigo, n.alinea_nome, n.origem_nome,
           sum(f.valor_arrecadado) as arrecadado,
           sum(f.valor_previsto_atualizado) as previsto_atualizado
    from marts.fato_receita_movimento f
    join marts.dim_classif_receita n using (sk_classif_receita)
    join marts.dim_mes m using (sk_mes)
    where m.mes between %(mes_inicio)s and %(mes_fim)s and (%(ano)s::int is null or m.ano = %(ano)s)
    group by 1, 2, 3
    order by arrecadado desc
"""

RECEITAS_EVOLUCAO = """
    with por_mes as (
        select m.sk_mes, m.ano_mes, sum(f.valor_arrecadado) as arrecadado
        from marts.fato_receita_movimento f
        join marts.dim_mes m using (sk_mes)
        where (%(ano)s::int is null or m.ano = %(ano)s)
        group by 1, 2
    )
    select ano_mes, arrecadado,
           arrecadado - lag(arrecadado) over (order by sk_mes)                    as variacao_abs,
           round(100 * (arrecadado - lag(arrecadado) over (order by sk_mes))
                 / nullif(lag(arrecadado) over (order by sk_mes), 0), 2)          as variacao_pct,
           sum(arrecadado) over (order by sk_mes)                                 as acumulado_ano
    from por_mes
    order by sk_mes
"""


def comparativo(medida: Medida) -> sql.Composed:
    # Intraorçamentárias = transferências entre órgãos da própria prefeitura. Aparecem como
    # receita (categoria 7) num órgão e despesa (modalidade 91) no outro: excluí-las evita
    # contar o mesmo real duas vezes ao comparar com o "mundo externo".
    return sql.SQL("""
        with r as (
            select f.sk_mes, sum(f.valor_arrecadado) as receita
            from marts.fato_receita_movimento f
            join marts.dim_classif_receita n using (sk_classif_receita)
            where not (%(excluir)s and n.intraorcamentaria)
            group by 1
        ),
        d as (
            select f.sk_mes, sum(f.{col}) as despesa
            from marts.fato_despesa_movimento f
            join marts.dim_classif_economica e using (sk_classif_economica)
            where not (%(excluir)s and e.modalidade_aplicacao_codigo = '91')
            group by 1
        )
        select m.ano_mes,
               coalesce(r.receita, 0)                            as receita_arrecadada,
               coalesce(d.despesa, 0)                            as despesa,
               coalesce(r.receita, 0) - coalesce(d.despesa, 0)   as saldo
        from marts.dim_mes m
        left join r using (sk_mes)
        left join d using (sk_mes)
        where m.mes between %(mes_inicio)s and %(mes_fim)s and (%(ano)s::int is null or m.ano = %(ano)s)
        order by m.sk_mes
    """).format(col=_col(medida))
