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
    topo = next(m.value for m in at.markdown if 'class="topo"' in m.value)
    assert "R$ 7,88 bi" in topo and "R$ 7,80 bi" in topo          # frase do topo
    assert "R$ 7.882.016.730,69" in topo and "R$ 7.803.361.234,91" in topo  # balança, exato
    assert "89,95%" in topo
    assert len(at.tabs) == 3
    assert any("não está configurado" in i.value for i in at.info)  # sem LLM: aviso, sem quebrar


def test_chat_bloqueia_quando_cota_diaria_global_acaba(monkeypatch):
    """Limite global: mesmo numa sessão nova (página recarregada), o LLM não é chamado."""
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")  # se fosse chamado, daria erro
    monkeypatch.setenv("LIMITE_DIARIO_PERGUNTAS", "0")
    at = st_testing.AppTest.from_file(APP, default_timeout=90).run()
    at.chat_input[0].set_value("Quanto foi o IPTU?").run()
    assert not at.exception, at.exception
    assert any("limite de perguntas de hoje" in w.value for w in at.warning)
    assert not at.session_state["historico"]  # nada foi perguntado ao modelo
