"""Loop de feedback: guarda cada interação e exporta as ruins como candidatas a eval."""
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import yaml

from orcamento.agente.agente import RespostaAgente
from orcamento.config import dsn

DDL = """
create schema if not exists app;
create table if not exists app.interacoes (
    id           bigserial primary key,
    criado_em    timestamptz not null default now(),
    modelo       text not null,
    pergunta     text not null,
    resposta     text not null,
    chamadas     jsonb not null,          -- [{ferramenta, argumentos, ok}]
    numeros_sem_suporte jsonb not null,   -- detector de alucinação
    avaliacao    smallint check (avaliacao in (-1, 1)),  -- 👎 = -1, 👍 = 1, null = sem voto
    comentario   text
);
"""


def garantir_tabela(conn: psycopg.Connection) -> None:
    """Cria a tabela só se ela não existir.

    No app online o usuário do banco é restrito (sem CREATE), então nem tentamos DDL quando
    a tabela já está lá: o Postgres checa permissão antes de avaliar o IF NOT EXISTS.
    """
    existe = conn.execute("select to_regclass('app.interacoes') is not null").fetchone()[0]
    if not existe:
        conn.execute(DDL)


def registrar(resp: RespostaAgente, avaliacao: int | None = None,
              comentario: str | None = None, conn: psycopg.Connection | None = None) -> int:
    proprio = conn is None
    conn = conn or psycopg.connect(dsn())
    try:
        garantir_tabela(conn)
        chamadas = [{"ferramenta": c.ferramenta, "argumentos": c.argumentos, "ok": c.ok}
                    for c in resp.chamadas]
        linha = conn.execute(
            """insert into app.interacoes
               (modelo, pergunta, resposta, chamadas, numeros_sem_suporte, avaliacao, comentario)
               values (%s, %s, %s, %s, %s, %s, %s) returning id""",
            (resp.modelo, resp.pergunta, resp.texto, json.dumps(chamadas, ensure_ascii=False),
             json.dumps(resp.numeros_sem_suporte, ensure_ascii=False), avaliacao, comentario),
        ).fetchone()
        conn.commit()
        return linha[0]
    finally:
        if proprio:
            conn.close()


def votar(id_interacao: int, avaliacao: int, comentario: str | None = None,
          conn: psycopg.Connection | None = None) -> None:
    """Registra 👍 (1) / 👎 (-1) numa interação já gravada (o voto vem depois da resposta)."""
    if avaliacao not in (-1, 1):
        raise ValueError("avaliacao deve ser -1 ou 1")
    proprio = conn is None
    conn = conn or psycopg.connect(dsn())
    try:
        conn.execute("update app.interacoes set avaliacao = %s, comentario = %s where id = %s",
                     (avaliacao, comentario, id_interacao))
        conn.commit()
    finally:
        if proprio:
            conn.close()


def perguntas_hoje(conn: psycopg.Connection | None = None) -> int:
    """Quantas perguntas o agente respondeu HOJE (fuso do Recife), somando todos os visitantes.

    É a base do limite diário global do app: o limite por sessão some quando a página é
    recarregada, este não. Conta só o que foi gravado (respostas que de fato gastaram cota do
    LLM). Requer SELECT em (criado_em) para o usuário do app; ver deploy/supabase_setup.sql.
    """
    proprio = conn is None
    conn = conn or psycopg.connect(dsn())
    try:
        if not conn.execute("select to_regclass('app.interacoes') is not null").fetchone()[0]:
            return 0
        return conn.execute(
            """select count(*) from app.interacoes
               where criado_em >= date_trunc('day', now() at time zone 'America/Recife')
                                  at time zone 'America/Recife'"""
        ).fetchone()[0]
    finally:
        if proprio:
            conn.close()


def exportar_negativos(destino: str = "evals/candidatos.yaml",
                       conn: psycopg.Connection | None = None) -> int:
    """Interações com 👎 viram RASCUNHO de caso de eval.

    Não entram direto em casos.yaml: alguém precisa escrever o gabarito_sql e conferir o
    resultado. Gabarito gerado pelo próprio sistema avaliado não prova nada.
    """
    proprio = conn is None
    conn = conn or psycopg.connect(dsn())
    try:
        garantir_tabela(conn)
        linhas = conn.execute(
            """select id, pergunta, resposta, chamadas, comentario from app.interacoes
               where avaliacao = -1 order by id"""
        ).fetchall()
    finally:
        if proprio:
            conn.close()
    rascunhos = [{
        "id": f"feedback_{i}",
        "pergunta": pergunta,
        "tipo": "PREENCHER (numero | texto | recusa)",
        "ferramentas_aceitas": sorted({c["ferramenta"] for c in chamadas}) or ["PREENCHER"],
        "gabarito_sql": "PREENCHER: SQL direto em raw.despesas / raw.receitas",
        "contexto": {"resposta_ruim": resposta, "comentario": comentario},
    } for i, pergunta, resposta, chamadas, comentario in linhas]
    cabecalho = (f"# Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC a partir de 👎.\n"
                 "# Revise, escreva o gabarito_sql e mova para evals/casos.yaml.\n")
    Path(destino).write_text(
        cabecalho + yaml.safe_dump(rascunhos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return len(rascunhos)


if __name__ == "__main__":
    print(f"{exportar_negativos()} candidatos exportados para evals/candidatos.yaml")
