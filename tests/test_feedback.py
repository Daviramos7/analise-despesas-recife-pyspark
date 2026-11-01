"""Registro de interações e exportação de 👎 para candidatos de eval."""
import psycopg
import pytest
import yaml

from orcamento.agente.agente import Chamada, RespostaAgente
from orcamento.config import dsn
from orcamento.feedback import exportar_negativos, registrar


def test_registra_e_exporta_so_negativos(tmp_path):
    try:
        psycopg.connect(dsn(), connect_timeout=3).close()
    except psycopg.OperationalError as e:
        pytest.skip(f"Postgres indisponível: {e}")
    boa = RespostaAgente("Quanto foi o IPTU?", "R$ 660.545.540,80",
                         [Chamada("receitas_itens", {"busca": "IPTU"}, True, '{"a":"660545540.80"}')], modelo="t")
    ruim = RespostaAgente("Quanto foi o ISS?", "R$ 1,00",
                          [Chamada("receitas_itens", {"busca": "ISS"}, True, "{}")], modelo="t")
    with psycopg.connect(dsn()) as c:
        antes = c.execute("select coalesce(max(id),0) from app.interacoes").fetchone()[0] \
            if c.execute("select to_regclass('app.interacoes')").fetchone()[0] else 0
    id_boa = registrar(boa, 1)
    id_ruim = registrar(ruim, -1, "valor errado")
    assert id_ruim > id_boa > antes

    with psycopg.connect(dsn()) as c:
        linha = c.execute("select avaliacao, numeros_sem_suporte, chamadas from app.interacoes where id=%s",
                          (id_ruim,)).fetchone()
    assert linha[0] == -1 and linha[1] == ["1,00"] and linha[2][0]["ferramenta"] == "receitas_itens"

    destino = tmp_path / "candidatos.yaml"
    exportar_negativos(str(destino))
    candidatos = yaml.safe_load(destino.read_text("utf-8"))
    perguntas = [c["pergunta"] for c in candidatos]
    assert "Quanto foi o ISS?" in perguntas and "Quanto foi o IPTU?" not in perguntas
    ultimo = [c for c in candidatos if c["id"] == f"feedback_{id_ruim}"][0]
    assert ultimo["contexto"]["comentario"] == "valor errado"
    assert "PREENCHER" in ultimo["gabarito_sql"]  # gabarito nunca é gerado automaticamente

    with psycopg.connect(dsn()) as c:
        c.execute("delete from app.interacoes where id in (%s, %s)", (id_boa, id_ruim))


def test_voto_posterior_atualiza_interacao():
    try:
        psycopg.connect(dsn(), connect_timeout=3).close()
    except psycopg.OperationalError as e:
        pytest.skip(f"Postgres indisponível: {e}")
    from orcamento.feedback import votar
    resp = RespostaAgente("p?", "r", [], modelo="t")
    id_ = registrar(resp)  # sem voto ainda (como no app: resposta aparece antes do voto)
    votar(id_, -1, "errado")
    with psycopg.connect(dsn()) as c:
        assert c.execute("select avaliacao, comentario from app.interacoes where id=%s",
                         (id_,)).fetchone() == (-1, "errado")
        c.execute("delete from app.interacoes where id=%s", (id_,))
    with pytest.raises(ValueError):
        votar(id_, 0)
