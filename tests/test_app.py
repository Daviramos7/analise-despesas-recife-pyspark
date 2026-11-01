"""Smoke test do app Streamlit: renderiza a página contra o banco real, sem LLM."""
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

from tests.test_cobertura_evals import _banco_real_disponivel  # noqa: E402

APP = str(Path(__file__).parents[1] / "app" / "streamlit_app.py")

pytestmark = pytest.mark.skipif(not _banco_real_disponivel(), reason="banco com dados reais indisponível")


def test_app_renderiza_kpis_abas_e_graficos(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    at = st_testing.AppTest.from_file(APP, default_timeout=90).run()
    assert not at.exception, at.exception
    assert [m.label for m in at.metric] == [
        "Receita arrecadada", "Despesa liquidada", "Saldo (receita − despesa)",
        "Receita prevista realizada"]
    assert at.metric[0].value == "R$ 7,88 bi"
    assert at.metric[1].value == "R$ 7,80 bi"
    assert len(at.tabs) == 3
    assert any("não está configurado" in i.value for i in at.info)  # sem LLM: aviso, sem quebrar
