"""Pontuação dos evals e integridade do arquivo de casos."""
from pathlib import Path

import yaml

from despesas.agente.agente import Chamada, RespostaAgente
from despesas.agente.ferramentas import gerar_ferramentas
from despesas.api.app import app
from despesas.avaliacao import TIPOS, avaliar, resumir

CASOS = yaml.safe_load((Path(__file__).parents[1] / "evals" / "casos.yaml").read_text("utf-8"))


def _resp(texto, tools=(), resultados=("{}",)):
    return RespostaAgente("p", texto, [Chamada(t, {}, True, r) for t, r in zip(tools, resultados)])


def test_casos_bem_formados():
    nomes = {f.nome for f in gerar_ferramentas(app.openapi())}
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids)), "ids duplicados"
    assert 20 <= len(CASOS) <= 40
    for c in CASOS:
        assert c["tipo"] in TIPOS, c["id"]
        assert set(c["ferramentas_aceitas"]) <= nomes, c["id"]
        assert bool(c.get("gabarito_sql")) == (c["tipo"] != "recusa"), c["id"]
    assert sum(c["tipo"] == "recusa" for c in CASOS) >= 4


def test_numero_certo_errado_e_arredondado():
    caso = {"id": "x", "pergunta": "p", "tipo": "numero", "ferramentas_aceitas": ["receitas_itens"]}
    tool = ('{"arrecadado": "660545540.80"}',)
    assert avaliar(caso, _resp("R$ 660.545.540,80", ["receitas_itens"], tool), "660545540.80").acerto
    assert avaliar(caso, _resp("cerca de R$ 660,5 milhões", ["receitas_itens"], tool), "660545540.80").acerto
    assert not avaliar(caso, _resp("R$ 600.000.000,00", ["receitas_itens"], tool), "660545540.80").acerto
    r = avaliar(caso, _resp("R$ 660.545.540,80", ["despesas_orgaos"], tool), "660545540.80")
    assert r.acerto and not r.ferramenta_ok


def test_recusa_exige_frase_e_nenhum_numero_inventado():
    caso = {"id": "x", "pergunta": "p", "tipo": "recusa", "ferramentas_aceitas": ["metadados"]}
    assert avaliar(caso, _resp("Não tenho esse dado: só existe 2023."), None).acerto
    assert not avaliar(caso, _resp("Foram R$ 1.234.567,00."), None).acerto
    assert not avaliar(caso, _resp("Não tenho esse dado, mas foi uns R$ 5 milhões."), None).acerto


def test_texto_ignora_acento_e_caixa():
    caso = {"id": "x", "pergunta": "p", "tipo": "texto", "ferramentas_aceitas": ["despesas_orgaos"]}
    assert avaliar(caso, _resp("Foi a Secretaria de Saude", ["despesas_orgaos"]), "SAÚDE").acerto


def test_resumo():
    caso = {"id": "x", "pergunta": "p", "tipo": "texto", "ferramentas_aceitas": ["orgaos"]}
    rs = [avaliar(caso, _resp("abc", ["orgaos"]), "abc"), avaliar(caso, _resp("zzz", []), "abc")]
    s = resumir(rs)
    assert s["acerto_pct"] == 50.0 and s["ferramenta_correta_pct"] == 50.0
    assert s["acerto_por_tipo"] == {"texto": "1/2"}


def test_resultado_guarda_argumentos_das_chamadas_e_agregado():
    from despesas.avaliacao import agregar
    caso = {"id": "x", "pergunta": "p", "tipo": "texto", "ferramentas_aceitas": ["orgaos"]}
    r = avaliar(caso, RespostaAgente("p", "abc", [Chamada("orgaos", {"busca": "saude"}, True, "[]")]), "abc")
    assert r.chamadas == [{"ferramenta": "orgaos", "argumentos": {"busca": "saude"}, "ok": True,
                           "resultado_inicio": "[]"}]
    ag = agregar([{"acerto_pct": 90.0, "ferramenta_correta_pct": 90.0, "respostas_com_numero_sem_suporte": 0},
                  {"acerto_pct": 70.0, "ferramenta_correta_pct": 100.0, "respostas_com_numero_sem_suporte": 2}])
    assert ag["acerto_pct"] == {"media": 80.0, "min": 70.0, "max": 90.0} and ag["repeticoes"] == 2


def test_avaliacao_separa_acerto_com_e_sem_guardrail():
    caso = {"id": "x", "pergunta": "p", "tipo": "recusa", "ferramentas_aceitas": ["despesas_orgaos"]}
    resp = RespostaAgente("p", "Não tenho esse dado: só 2023.", guardrail="ano [2022] fora de [2023]",
                          texto_llm="R$ 1.668.250.043,27")
    r = avaliar(caso, resp, None)
    assert r.acerto is True and r.acerto_llm is False and r.guardrail
    s = resumir([r])
    assert s["acerto_pct"] == 100.0 and s["acerto_llm_sem_guardrail_pct"] == 0.0
    assert s["guardrail_acionado"] == 1
