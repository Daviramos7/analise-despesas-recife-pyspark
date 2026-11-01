"""Cobertura: cada caso respondível do eval é respondível pela API (sem LLM).

Roda contra o banco REAL (dados completos). Pulado se o banco/dados não estiverem
disponíveis (ex.: CI só com fixture). Execute com: docker compose run --rm tests
"""
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient

from orcamento.agente.ferramentas import gerar_ferramentas
from orcamento.agente.verificacao import numeros_das_tools
from orcamento.avaliacao import normalizar
from orcamento.config import dsn

CASOS = yaml.safe_load((Path(__file__).parents[1] / "evals" / "casos.yaml").read_text("utf-8"))


def _banco_real_disponivel() -> bool:
    try:
        with psycopg.connect(dsn(), connect_timeout=3) as c:
            return c.execute("select count(*) > 100000 from marts.fato_despesa_movimento").fetchone()[0]
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _banco_real_disponivel(), reason="banco com dados reais indisponível")


@pytest.fixture(scope="module")
def api():
    from orcamento.api.app import app
    caminhos = {f.nome: f.caminho for f in gerar_ferramentas(app.openapi())}
    cliente = TestClient(app)
    return lambda nome, args: cliente.get(caminhos[nome], params=args)


@pytest.mark.parametrize("caso", [c for c in CASOS if c.get("referencia")], ids=lambda c: c["id"])
def test_resposta_esperada_esta_na_saida_da_api(api, caso):
    with psycopg.connect(dsn()) as conn:
        esperado = conn.execute(caso["gabarito_sql"]).fetchone()[0]
    resp = api(caso["referencia"]["ferramenta"], caso["referencia"]["argumentos"])
    assert resp.status_code == 200, resp.text
    assert caso["referencia"]["ferramenta"] in caso["ferramentas_aceitas"]
    if caso["tipo"] == "numero":
        assert Decimal(str(esperado)) in numeros_das_tools([resp.text]), (esperado, resp.text[:500])
    else:
        assert normalizar(str(esperado)) in normalizar(resp.text)
