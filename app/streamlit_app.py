"""Orçamento Público do Recife: painel + agente de IA.

O app é só mais um CLIENTE da API: o painel e o agente chamam a mesma FastAPI
(dentro do processo, via TestClient), então os números da tela são os mesmos
que os evals avaliam.
"""
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

st.set_page_config(
    page_title="Orçamento Público do Recife",
    page_icon="🏛️",
    layout="wide",
    menu_items={"About": "Dados abertos da Prefeitura do Recife (2023) · projeto de portfólio"},
)


def _carregar_segredos() -> None:
    """Streamlit Cloud: st.secrets -> variáveis de ambiente (o código lê só env).

    load_if_toml_exists() checa em silêncio: sem secrets.toml (ex.: docker compose, onde a
    config vem do ambiente), acessar st.secrets direto exibiria um erro na página.
    """
    try:
        if not st.secrets.load_if_toml_exists():
            return
        for chave, valor in st.secrets.items():
            if isinstance(valor, (str, int, float)):
                os.environ.setdefault(chave, str(valor))
    except Exception:  # noqa: BLE001
        return


_carregar_segredos()
os.environ.setdefault("LLM_MAX_RETRIES", "2")   # no app, melhor falhar rápido que travar
os.environ.setdefault("LLM_TIMEOUT_S", "45")

import openai  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from orcamento.api.app import app as api  # noqa: E402

# ------------------------------------------------------------------ constantes
COR_DESPESA = "#2a78d6"   # slot 1 da paleta validada (azul): despesa em TODOS os gráficos
COR_RECEITA = "#eb6834"   # slot 2 (laranja): receita em TODOS os gráficos
TINTA_2 = "#52514e"
GRADE = "#e7e6e1"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MAX_PERGUNTAS = 15
INTERVALO_S = 5
SUGESTOES = [
    "Quanto a prefeitura arrecadou em 2023?",
    "Quanto foi arrecadado de IPTU?",
    "Quais órgãos mais gastaram?",
    "Quanto foi gasto com saúde?",
    "A prefeitura arrecadou mais do que gastou?",
    "Quem mais recebeu pagamentos da prefeitura?",
]

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1200px;}
      .hero h1 {font-size: 2.1rem; margin-bottom: .2rem;}
      .hero p {color: #52514e; font-size: 1.02rem; margin-top: 0;}
      div[data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #e7e6e1; border-radius: 12px;
        padding: 14px 16px;
      }
      div[data-testid="stMetricLabel"] p {color: #52514e; font-size: .9rem;}
      .selo {font-size: .85rem; color: #52514e;}
      .rodape {color: #8a8984; font-size: .82rem; margin-top: 2.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ dados (via API)
@st.cache_resource
def cliente_api() -> TestClient:
    return TestClient(api)


@st.cache_data(ttl=3600, show_spinner=False)
def consultar(caminho: str, **params) -> dict:
    resp = cliente_api().get(caminho, params=params)
    resp.raise_for_status()
    return resp.json()


def D(valor) -> float:
    return float(Decimal(str(valor)))


def brl(valor, compacto: bool = True) -> str:
    v = D(valor)
    if compacto and abs(v) >= 1e9:
        txt, suf = f"{v / 1e9:,.2f}", " bi"
    elif compacto and abs(v) >= 1e6:
        txt, suf = f"{v / 1e6:,.1f}", " mi"
    else:
        txt, suf = f"{v:,.2f}", ""
    return "R$ " + txt.replace(",", "X").replace(".", ",").replace("X", ".") + suf


def pct(valor) -> str:
    return f"{D(valor):.2f}%".replace(".", ",")


def nome_curto(nome: str, limite: int = 34) -> str:
    for sufixo in (" - ADMINISTRAÇÃO SUPERVISIONADA", " - ADMINISTRAÇÃO DIRETA"):
        nome = nome.replace(sufixo, "")
    nome = nome.title()
    for palavra in (" De ", " Da ", " Do ", " Das ", " Dos ", " E ", " Ao ", " A ", " Em "):
        nome = nome.replace(palavra, palavra.lower())
    return nome if len(nome) <= limite else nome[: limite - 1] + "…"


def rotulos_unicos(nomes: list[str], diferenciais: list[str]) -> list[str]:
    """Nomes repetidos (ex.: mesmo órgão em adm. direta e supervisionada) ganham diferencial."""
    contagem = {n: nomes.count(n) for n in nomes}
    return [f"{n} ({d})" if contagem[n] > 1 else n for n, d in zip(nomes, diferenciais)]


def layout_base(fig: go.Figure, altura: int = 360) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#0b0b0b", size=13), separators=",.",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRADE, font_color="#0b0b0b"),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRADE, zeroline=False, linecolor=GRADE, tickfont_color=TINTA_2)
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, linecolor=GRADE, tickfont_color=TINTA_2)
    return fig


def barras_horizontais(rotulos, valores, cor, titulo_hover, nomes_completos=None) -> go.Figure:
    """Barras horizontais. Cada barra tem posição própria (y numérico + ticktext), então dois
    rótulos iguais nunca se fundem numa barra só."""
    valores_mi = [D(v) / 1e6 for v in valores]
    posicoes = list(range(len(rotulos)))
    nomes_completos = nomes_completos or rotulos
    fig = go.Figure(go.Bar(
        x=valores_mi, y=posicoes, orientation="h",
        marker=dict(color=cor, cornerradius=4),
        text=[brl(v) for v in valores], textposition="outside", cliponaxis=False,
        textfont=dict(color=TINTA_2, size=12),
        hovertemplate="<b>%{customdata[0]}</b><br>" + titulo_hover +
                      ": %{customdata[1]}<extra></extra>",
        customdata=[[n, brl(v, compacto=False)] for n, v in zip(nomes_completos, valores)],
    ))
    layout_base(fig, altura=max(260, 34 * len(rotulos) + 40))
    fig.update_layout(bargap=0.35, margin=dict(l=8, r=8, t=8, b=8))
    fig.update_yaxes(tickvals=posicoes, ticktext=rotulos, autorange="reversed",
                     gridcolor="rgba(0,0,0,0)", automargin=True)
    fig.update_xaxes(title=None, ticksuffix=" mi", tickformat=",.0f", nticks=4,
                     range=[0, max(valores_mi) * 1.4])
    return fig


# ------------------------------------------------------------------ agente
def llm_configurado() -> bool:
    return bool(os.getenv("LLM_BASE_URL"))


@st.cache_resource
def agente():
    from orcamento.agente.agente import criar_agente_padrao
    return criar_agente_padrao(cliente_api=cliente_api())


def sem_latex(texto: str) -> str:
    # "R$ 1,00 ... R$ 2,00" viraria fórmula LaTeX no Markdown do Streamlit
    return texto.replace("$", "\\$")


def registrar_interacao(resp) -> int | None:
    try:
        from orcamento.feedback import registrar
        return registrar(resp)
    except Exception:  # noqa: BLE001 - feedback nunca derruba o app
        return None


def votar(id_interacao: int | None, polegar: int) -> None:
    if id_interacao is None:
        return
    try:
        from orcamento.feedback import votar as votar_bd
        votar_bd(id_interacao, 1 if polegar == 1 else -1)
    except Exception:  # noqa: BLE001
        pass


def perguntar(pergunta: str) -> dict:
    try:
        resp = agente().perguntar(pergunta)
    except openai.RateLimitError:
        return {"pergunta": pergunta, "erro": "O limite gratuito do modelo foi atingido. "
                                               "Tente de novo em cerca de 1 minuto."}
    except (openai.InternalServerError, openai.APIConnectionError, openai.APITimeoutError):
        return {"pergunta": pergunta, "erro": "O modelo de IA está sobrecarregado ou "
                                               "indisponível agora. Tente em alguns minutos."}
    except openai.AuthenticationError:
        return {"pergunta": pergunta, "erro": "Chave do modelo de IA inválida (configuração)."}
    return {
        "pergunta": pergunta,
        "texto": resp.texto,
        "chamadas": [{"ferramenta": c.ferramenta, "argumentos": c.argumentos, "ok": c.ok}
                     for c in resp.chamadas],
        "sem_suporte": resp.numeros_sem_suporte,
        "guardrail": resp.guardrail,
        "id": registrar_interacao(resp),
    }


def mostrar_resposta(i: int, item: dict) -> None:
    with st.chat_message("assistant", avatar="🏛️"):
        if item.get("erro"):
            st.warning(item["erro"], icon="⏳")
            return
        st.markdown(sem_latex(item["texto"]))
        if item["sem_suporte"]:
            st.markdown(f'<span class="selo">⚠️ Números sem suporte na API: '
                        f'{", ".join(item["sem_suporte"])}</span>', unsafe_allow_html=True)
        elif item["chamadas"]:
            st.markdown('<span class="selo">✅ Todos os números conferidos com a API</span>',
                        unsafe_allow_html=True)
        if item["guardrail"]:
            st.markdown('<span class="selo">🛡️ Resposta ajustada pelo guardrail de ano</span>',
                        unsafe_allow_html=True)
        if item["chamadas"]:
            n = len(item["chamadas"])
            with st.expander(f"🔎 Como cheguei nessa resposta ({n} consulta{'s' if n > 1 else ''} à API)"):
                for c in item["chamadas"]:
                    st.markdown(f"**`{c['ferramenta']}`** {'✅' if c['ok'] else '❌'}")
                    st.code(json.dumps(c["argumentos"], ensure_ascii=False), language="json")
        voto = st.feedback("thumbs", key=f"voto_{i}")
        votados = st.session_state.setdefault("votados", set())
        if voto is not None and i not in votados:
            votar(item.get("id"), voto)
            votados.add(i)
            st.toast("Valeu pelo feedback! 🙌")


# ------------------------------------------------------------------ cabeçalho + KPIs
st.markdown(
    """
    <div class="hero">
      <h1>🏛️ Orçamento Público do Recife</h1>
      <p>Receitas e despesas da Prefeitura do Recife em 2023, com um agente de IA que
      responde em português <b>citando só números que vieram da API</b>.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    receitas = consultar("/receitas/origens")
    despesas = consultar("/despesas/orgaos", limite=10)
    comparativo = consultar("/comparativo/receita-despesa")
except Exception as e:  # noqa: BLE001
    st.error("Não consegui acessar o banco de dados agora. Tente de novo em instantes.")
    st.caption(f"Detalhe técnico: {type(e).__name__}")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Receita arrecadada", brl(receitas["total_arrecadado"]),
          help=f"{brl(receitas['total_arrecadado'], False)} · inclui intraorçamentárias")
k2.metric("Despesa liquidada", brl(despesas["total_geral"]),
          help=f"{brl(despesas['total_geral'], False)} · inclui intraorçamentárias")
k3.metric("Saldo (receita − despesa)", brl(comparativo["saldo"]),
          help="Sem operações intraorçamentárias (transferências entre órgãos da própria "
               f"prefeitura). Valor exato: {brl(comparativo['saldo'], False)}")
k4.metric("Receita prevista realizada", pct(receitas["total_execucao_pct"]),
          help=f"Arrecadado ÷ previsto atualizado ({brl(receitas['total_previsto_atualizado'], False)})")

st.write("")
aba_chat, aba_painel, aba_sobre = st.tabs(["💬 Pergunte ao agente", "📊 Painel", "🧪 Como funciona"])

# ------------------------------------------------------------------ aba: chat
with aba_chat:
    if not llm_configurado():
        st.info("O agente de IA não está configurado neste ambiente (falta `LLM_BASE_URL`). "
                "O painel continua funcionando.", icon="🔌")
    else:
        st.caption("🔒 Não digite dados pessoais: as perguntas são enviadas a um modelo de IA "
                   f"externo. Limite de {MAX_PERGUNTAS} perguntas por sessão (plano gratuito).")
        historico = st.session_state.setdefault("historico", [])

        if not historico:
            st.markdown("**Experimente:**")
            colunas = st.columns(3)
            for j, sugestao in enumerate(SUGESTOES):
                if colunas[j % 3].button(sugestao, key=f"sug_{j}", use_container_width=True):
                    st.session_state["pendente"] = sugestao
                    st.rerun()

        for i, item in enumerate(historico):
            with st.chat_message("user", avatar="🙋"):
                st.markdown(sem_latex(item["pergunta"]))
            mostrar_resposta(i, item)

        digitada = st.chat_input("Pergunte sobre receitas e despesas do Recife em 2023…",
                                 max_chars=300)
        pergunta = digitada or st.session_state.pop("pendente", None)
        if pergunta:
            agora = time.time()
            ultima = st.session_state.get("ultima_pergunta_em", 0)
            if len(historico) >= MAX_PERGUNTAS:
                st.warning("Limite de perguntas desta sessão atingido. Recarregue a página "
                           "mais tarde. 🙂", icon="🚦")
            elif agora - ultima < INTERVALO_S:
                st.warning(f"Calma! Espere {INTERVALO_S} segundos entre perguntas.", icon="🚦")
            else:
                st.session_state["ultima_pergunta_em"] = agora
                with st.spinner(f"Consultando a API sobre: “{pergunta}”…"):
                    item = perguntar(pergunta)
                historico.append(item)
                st.rerun()  # redesenha: conversa acima da caixa de texto, sem as sugestões

# ------------------------------------------------------------------ aba: painel
with aba_painel:
    st.subheader("Receita × despesa, mês a mês")
    st.caption("Receita arrecadada e despesa liquidada, sem operações intraorçamentárias. "
               "Valores em milhões de reais.")
    meses = comparativo["meses"]
    x = [MESES[int(m["ano_mes"][-2:]) - 1] for m in meses]
    fig = go.Figure()
    for nome, campo, cor in (("Receita", "receita_arrecadada", COR_RECEITA),
                             ("Despesa", "despesa", COR_DESPESA)):
        y = [D(m[campo]) / 1e6 for m in meses]
        fig.add_trace(go.Scatter(
            x=x, y=y, name=nome, mode="lines+markers",
            line=dict(color=cor, width=2), marker=dict(size=8, color=cor,
                                                       line=dict(color="#fcfcfb", width=2)),
            customdata=[brl(m[campo], False) for m in meses],
            hovertemplate=f"<b>{nome}</b> · %{{x}}<br>%{{customdata}}<extra></extra>",
        ))
        fig.add_annotation(x=x[-1], y=y[-1], text=f"<b>{nome}</b>", showarrow=False,
                           xanchor="left", xshift=10, font=dict(color=TINTA_2, size=12))
    layout_base(fig, altura=380)
    fig.update_layout(showlegend=True, hovermode="x unified",
                      legend=dict(orientation="h", y=1.08, x=0, font=dict(color=TINTA_2)),
                      margin=dict(r=70))
    fig.update_yaxes(ticksuffix=" mi", rangemode="tozero", tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Órgãos que mais gastaram")
        st.caption("Despesa liquidada em 2023 · top 10")
        org = despesas["orgaos"]
        nomes_org = rotulos_unicos(
            [nome_curto(o["orgao_nome"], 28) for o in org],
            ["supervisionada" if "SUPERVISIONADA" in o["orgao_nome"] else f"cód. {o['orgao_codigo']}"
             for o in org])
        st.plotly_chart(
            barras_horizontais(nomes_org, [o["valor"] for o in org], COR_DESPESA, "Liquidado",
                               nomes_completos=[o["orgao_nome"].title() for o in org]),
            use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.subheader("De onde veio o dinheiro")
        st.caption("Receita arrecadada em 2023, por origem")
        ori = [o for o in receitas["origens"] if D(o["arrecadado"]) > 0][:8]
        nomes_ori = rotulos_unicos(
            [nome_curto(o["origem_nome"], 28) for o in ori],
            ["intra" if "INTRA" in o["categoria_receita_nome"] else
             ("capital" if "CAPITAL" in o["categoria_receita_nome"] else "corrente") for o in ori])
        st.plotly_chart(
            barras_horizontais(nomes_ori, [o["arrecadado"] for o in ori], COR_RECEITA, "Arrecadado",
                               nomes_completos=[f"{o['origem_nome'].title()} · "
                                                f"{o['categoria_receita_nome'].title()}" for o in ori]),
            use_container_width=True, config={"displayModeBar": False})

    st.subheader("Quem mais recebeu da prefeitura")
    st.caption("Valor pago em 2023 por credor (empresas, bancos e fundos), consolidado por nome. "
               "Exclui a folha registrada como “credor não informado”.")
    cred = consultar("/despesas/credores/ranking", limite=10)["credores"]
    st.plotly_chart(
        barras_horizontais([nome_curto(c["credor_nome"], 30) for c in cred],
                           [c["valor"] for c in cred], COR_DESPESA, "Pago",
                           nomes_completos=[c["credor_nome"].title() for c in cred]),
        use_container_width=True, config={"displayModeBar": False})

    with st.expander("📋 Ver os números em tabela"):
        st.dataframe(
            [{"Mês": m["ano_mes"], "Receita (R$)": D(m["receita_arrecadada"]),
              "Despesa (R$)": D(m["despesa"]), "Saldo (R$)": D(m["saldo"])} for m in meses],
            use_container_width=True, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.2f")
                           for c in ("Receita (R$)", "Despesa (R$)", "Saldo (R$)")},
        )

# ------------------------------------------------------------------ aba: como funciona
with aba_sobre:
    st.subheader("Como funciona")
    st.markdown(
        """
1. **Dados:** CSVs oficiais do Portal de Dados Abertos do Recife → **PySpark** (limpeza testada)
   → **PostgreSQL** → **dbt** (modelo dimensional + 86 testes de qualidade de dados).
2. **API:** **FastAPI** com 10 endpoints tipados. As descrições foram escritas para serem lidas
   por um LLM, e este painel usa a mesma API.
3. **Agente:** cada endpoint vira uma *tool* (geradas do OpenAPI). O loop de *tool calling* é
   escrito direto no SDK, sem framework. Um verificador **fora do LLM** confere se todo número
   da resposta veio da API, e um guardrail recusa perguntas sobre anos que não existem.
4. **Evals:** 30 perguntas com gabarito calculado por **SQL direto nos dados brutos**, sem
   passar pela API. Os resultados ficam versionados.
        """
    )
    pasta = RAIZ / "evals" / "resultados"
    linhas = []
    for arq in sorted(pasta.glob("*.json")):
        try:
            dado = json.loads(arq.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ag = dado.get("agregado") or dado.get("resumo", {})
        acerto = ag.get("acerto_pct")
        sem_g = ag.get("acerto_llm_sem_guardrail_pct")
        linhas.append({
            "Rodada": arq.name[:13],
            "Modelo": ag.get("modelo", "qwen2.5:7b"),
            "Acerto (%)": acerto["media"] if isinstance(acerto, dict) else acerto,
            "LLM sem guardrail (%)": (sem_g["media"] if isinstance(sem_g, dict) else sem_g),
            "Repetições": ag.get("repeticoes", 1),
        })
    if linhas:
        st.markdown("**Histórico dos evals** (inclui as rodadas que pioraram):")
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    st.caption("Números válidos para estes 30 casos, escritos pelo autor. Não são uma medida de "
               "confiabilidade geral.")

st.markdown(
    '<div class="rodape">Dados: Portal de Dados Abertos da Prefeitura do Recife (2023) · '
    'Código: <a href="https://github.com/Daviramos7/orcamento-publico-recife">GitHub</a> · '
    'Projeto de portfólio de Davi Ramos Ferreira</div>',
    unsafe_allow_html=True,
)
