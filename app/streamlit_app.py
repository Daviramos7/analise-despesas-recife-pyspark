"""Orçamento Público do Recife: painel + agente de IA.

O app é só mais um CLIENTE da API: o painel e o agente chamam a mesma FastAPI
(dentro do processo, via TestClient), então os números da tela são os mesmos
que os evals avaliam.
"""
import html
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

# ------------------------------------------------------------------ tokens de design
# Cores de DADO (paleta validada para daltonismo): despesa e receita em TODOS os gráficos.
COR_DESPESA = "#2a78d6"
COR_RECEITA = "#eb6834"
# Cores de INTERFACE: o rio (Capibaribe) e o papel. Nunca usadas como série de dado.
RIO = "#0e3b4f"
TINTA = "#13222e"
TINTA_2 = "#4a5a63"
TINTA_3 = "#7a8a92"
LINHA = "#dde3e1"
FONTE = "Public Sans, system-ui, sans-serif"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MAX_PERGUNTAS = 15                                                    # por sessão
LIMITE_DIARIO = int(os.getenv("LIMITE_DIARIO_PERGUNTAS", "200"))      # todos os visitantes
INTERVALO_S = 5
SUGESTOES = [
    "Quanto a prefeitura arrecadou em 2023?",
    "Quanto foi arrecadado de IPTU?",
    "Quais órgãos mais gastaram?",
    "Quanto foi gasto com saúde?",
    "A prefeitura arrecadou mais do que gastou?",
    "Quem mais recebeu pagamentos da prefeitura?",
]
REPO = "https://github.com/Daviramos7/orcamento-publico-recife"

# Azulejo: um ladrilho de 48px desenhado em SVG, repetido no fundo do topo.
_AZULEJO = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='56' "
    "viewBox='0 0 56 56'%3E%3Cg fill='none' stroke='%23ffffff' stroke-width='1.2'%3E"
    "%3Crect x='.6' y='.6' width='54.8' height='54.8'/%3E%3Ccircle cx='28' cy='28' r='8'/%3E"
    "%3Cpath d='M28 4C28 18 18 28 4 28C18 28 28 38 28 52C28 38 38 28 52 28C38 28 28 18 28 4Z'/%3E"
    "%3Ccircle cx='0' cy='0' r='10'/%3E%3Ccircle cx='56' cy='0' r='10'/%3E"
    "%3Ccircle cx='0' cy='56' r='10'/%3E%3Ccircle cx='56' cy='56' r='10'/%3E%3C/g%3E%3C/svg%3E"
)

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');
      :root {{
        --rio: {RIO}; --tinta: {TINTA}; --tinta-2: {TINTA_2}; --tinta-3: {TINTA_3};
        --linha: {LINHA}; --papel: #f4f6f5; --branco: #ffffff;
        --receita: {COR_RECEITA}; --despesa: {COR_DESPESA};
        --display: 'Bricolage Grotesque', 'Public Sans', sans-serif;
      }}
      .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea,
      .stApp button {{ font-family: 'Public Sans', system-ui, sans-serif; }}
      .stApp h1, .stApp h2, .stApp h3 {{ font-family: var(--display); color: var(--tinta);
        letter-spacing: -0.01em; }}
      .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1180px; }}
      header[data-testid="stHeader"] {{ background: transparent; }}

      /* ---------- topo: o rio, o azulejo e a balança ---------- */
      .topo {{ position: relative; overflow: hidden; background: var(--rio); color: #fff;
        border-radius: 20px; padding: 1.6rem 2rem 1.7rem; margin-bottom: 1.4rem; }}
      .topo::after {{ content: ""; position: absolute; inset: 0; background-image: url("{_AZULEJO}");
        opacity: .13; -webkit-mask-image: linear-gradient(100deg, transparent 38%, #000 92%);
        mask-image: linear-gradient(100deg, transparent 38%, #000 92%); pointer-events: none; }}
      .topo > * {{ position: relative; z-index: 1; }}
      .marca {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem;
        font-size: .92rem; color: #cfe0e6; margin-bottom: 1.6rem; flex-wrap: wrap; }}
      .marca b {{ font-family: var(--display); font-weight: 600; color: #fff; font-size: 1.02rem; }}
      .marca a {{ color: #cfe0e6; text-decoration: none; border-bottom: 1px solid #5f8796; }}
      .marca a:hover, .marca a:focus-visible {{ color: #fff; border-color: #fff; }}
      .frase {{ font-family: var(--display); font-weight: 800; color: #fff;
        font-size: clamp(1.75rem, 3.6vw, 2.9rem); line-height: 1.12; letter-spacing: -0.02em;
        max-width: 22ch; margin: 0 0 1.5rem; }}
      .frase .n {{ white-space: nowrap; }}
      .frase .n.rec {{ box-shadow: inset 0 -.18em 0 var(--receita); }}
      .frase .n.desp {{ box-shadow: inset 0 -.18em 0 var(--despesa); }}
      .balanca {{ display: grid; grid-template-columns: max-content 1fr max-content;
        gap: .55rem 1rem; align-items: center; max-width: 760px; }}
      .balanca span {{ font-size: .9rem; color: #cfe0e6; }}
      .balanca .valor {{ color: #fff; font-variant-numeric: tabular-nums; font-weight: 600; }}
      .trilho {{ height: 12px; background: rgba(255,255,255,.08); border-radius: 4px; }}
      .trilho i {{ display: block; height: 100%; border-radius: 0 4px 4px 0; }}
      .trilho i.rec {{ background: var(--receita); }} .trilho i.desp {{ background: var(--despesa); }}
      .fatos {{ display: flex; flex-wrap: wrap; gap: .5rem 2.2rem; margin-top: 1.4rem;
        padding-top: 1.1rem; border-top: 1px solid rgba(255,255,255,.14); font-size: .92rem;
        color: #cfe0e6; }}
      .fatos b {{ color: #fff; font-weight: 600; font-variant-numeric: tabular-nums; }}
      @media (max-width: 640px) {{
        .topo {{ padding: 1.2rem 1.1rem 1.3rem; border-radius: 16px; }}
        .balanca {{ grid-template-columns: max-content 1fr; }}
        .balanca .valor {{ grid-column: 1 / -1; margin-top: -.3rem; }}
      }}

      /* ---------- abas ---------- */
      .stTabs [data-baseweb="tab-list"] {{ gap: .4rem; border-bottom: 1px solid var(--linha); }}
      .stTabs [data-baseweb="tab"] {{ padding: .55rem .9rem; }}
      .stTabs [data-baseweb="tab"] p {{ font-family: var(--display); font-size: 1.02rem;
        font-weight: 600; color: var(--tinta-2); }}
      .stTabs [aria-selected="true"] p {{ color: var(--tinta); }}
      .stTabs [data-baseweb="tab-highlight"] {{ background: var(--rio); height: 3px; }}

      /* ---------- painéis de gráfico ---------- */
      div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]
        > [data-testid="stElementContainer"] .titulo-graf) {{ padding: .9rem 1.1rem .4rem;
        background: var(--branco); border-color: var(--linha); border-radius: 16px; }}
      .titulo-graf h3 {{ font-size: 1.15rem; margin: .1rem 0 .15rem; padding: 0; }}
      .titulo-graf p {{ color: var(--tinta-2); font-size: .9rem; margin: 0 0 .3rem; }}
      .legenda {{ display: flex; gap: 1.2rem; font-size: .88rem; color: var(--tinta-2); }}
      .legenda i {{ display: inline-block; width: 14px; height: 3px; border-radius: 2px;
        vertical-align: middle; margin-right: .4rem; }}

      /* ---------- conversa ---------- */
      .vazio h3 {{ font-size: 1.35rem; margin-bottom: .2rem; }}
      .vazio p {{ color: var(--tinta-2); max-width: 62ch; }}
      div[class*="st-key-sug_"] button {{ background: var(--branco); border: 1px solid var(--linha);
        border-radius: 12px; text-align: left; justify-content: flex-start; padding: .7rem .95rem;
        color: var(--tinta); }}
      @media (min-width: 640px) {{ div[class*="st-key-sug_"] button {{ min-height: 4.1rem; }} }}
      div[class*="st-key-sug_"] button:hover {{ border-color: var(--rio); color: var(--rio); }}
      div[class*="st-key-sug_"] button p {{ font-size: .95rem; }}
      [data-testid="stChatMessage"] {{ background: transparent; padding: .6rem 0; }}
      [data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {{
        border-radius: 10px; }}
      [data-testid="stChatMessageAvatarAssistant"] {{ background: var(--rio); color: #fff; }}
      .selos {{ display: flex; flex-wrap: wrap; gap: .4rem; margin: .1rem 0 .4rem; }}
      .selo {{ display: inline-flex; align-items: center; gap: .35rem; font-size: .8rem;
        padding: .18rem .6rem; border-radius: 999px; border: 1px solid; }}
      .selo.ok {{ color: #1d6b3f; border-color: #b8dcc6; background: #eef7f1; }}
      .selo.alerta {{ color: #8a4b00; border-color: #f0d2a6; background: #fdf5ea; }}
      .selo.info {{ color: var(--rio); border-color: #c4d6dd; background: #eef4f6; }}
      .cota {{ font-size: .86rem; color: var(--tinta-2); margin: .2rem 0 .8rem; }}
      .cota .barra {{ display: inline-block; width: 90px; height: 6px; border-radius: 3px;
        background: var(--linha); vertical-align: middle; margin: 0 .45rem; overflow: hidden; }}
      .cota .barra i {{ display: block; height: 100%; background: var(--rio); }}

      /* ---------- como funciona ---------- */
      .etapas {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: .6rem 0 1.6rem;
        counter-reset: etapa; }}
      .etapa {{ border-top: 3px solid var(--rio); padding-top: .8rem; counter-increment: etapa; }}
      .etapa h4 {{ font-family: var(--display); font-size: 1.05rem; margin: 0 0 .35rem; color: var(--tinta); }}
      .etapa h4::before {{ content: counter(etapa); display: inline-grid; place-items: center;
        width: 1.5rem; height: 1.5rem; margin-right: .5rem; border-radius: 50%; background: var(--rio);
        color: #fff; font-size: .8rem; font-family: 'Public Sans', sans-serif; }}
      .etapa p {{ font-size: .92rem; color: var(--tinta-2); margin: 0; line-height: 1.5; }}
      @media (max-width: 900px) {{ .etapas {{ grid-template-columns: 1fr 1fr; }} }}
      @media (max-width: 560px) {{ .etapas {{ grid-template-columns: 1fr; }} }}

      .rodape {{ color: var(--tinta-3); font-size: .84rem; margin-top: 2.5rem; padding-top: 1rem;
        border-top: 1px solid var(--linha); }}
      .rodape a {{ color: var(--tinta-2); }}
      @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
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
        height=altura, margin=dict(l=4, r=8, t=8, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONTE, color=TINTA, size=13), separators=",.",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=LINHA, font=dict(family=FONTE, color=TINTA)),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=LINHA, zeroline=False, linecolor=LINHA, tickfont_color=TINTA_2)
    fig.update_yaxes(gridcolor=LINHA, zeroline=False, linecolor=LINHA, tickfont_color=TINTA_2)
    return fig


def barras_horizontais(rotulos, valores, cor, titulo_hover, nomes_completos=None) -> go.Figure:
    """Ranking em barras com o nome ACIMA de cada barra (não à esquerda): a barra usa a
    largura toda, então o gráfico funciona igual no celular e no desktop. O valor ao lado da
    barra substitui o eixo x (que some). Cada barra tem posição própria, então dois rótulos
    iguais nunca se fundem numa barra só."""
    valores_mi = [D(v) / 1e6 for v in valores]
    nomes_completos = nomes_completos or rotulos
    fig = go.Figure(go.Bar(
        x=valores_mi, y=list(range(len(rotulos))), orientation="h", width=0.42,
        marker=dict(color=cor, cornerradius=4),
        text=[brl(v) for v in valores], textposition="outside", cliponaxis=False,
        textfont=dict(color=TINTA_2, size=12, family=FONTE),
        hovertemplate="<b>%{customdata[0]}</b><br>" + titulo_hover +
                      ": %{customdata[1]}<extra></extra>",
        customdata=[[n, brl(v, compacto=False)] for n, v in zip(nomes_completos, valores)],
    ))
    for i, rotulo in enumerate(rotulos):
        fig.add_annotation(x=0, y=i - 0.25, text=rotulo, showarrow=False, xanchor="left", align="left", xshift=-2,
                           yanchor="bottom", xref="x", font=dict(color=TINTA, size=12.5))
    layout_base(fig, altura=46 * len(rotulos) + 12)
    fig.update_yaxes(visible=False, autorange="reversed", range=None)
    fig.update_xaxes(visible=False, range=[0, max(valores_mi) * 1.3])
    fig.update_layout(margin=dict(l=2, r=8, t=4, b=2))
    return fig


def titulo_grafico(titulo: str, subtitulo: str, legenda: list[tuple[str, str]] | None = None) -> None:
    itens = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in (legenda or []))
    st.markdown(
        f'<div class="titulo-graf"><h3>{titulo}</h3><p>{subtitulo}</p>'
        + (f'<div class="legenda">{itens}</div>' if itens else "") + "</div>",
        unsafe_allow_html=True)


PLOTLY_CFG = {"displayModeBar": False}


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


def perguntas_hoje() -> int | None:
    """Perguntas respondidas hoje por TODOS os visitantes; None se não deu para contar."""
    try:
        from orcamento.feedback import perguntas_hoje as contar
        return contar()
    except Exception:  # noqa: BLE001
        return None


def cota_diaria_esgotada() -> bool:
    """Limite global, que sobrevive a recarregar a página (o de sessão, não).

    Falha FECHADA: se não der para contar, não gasta cota do LLM às cegas.
    """
    usadas = perguntas_hoje()
    return usadas is None or usadas >= LIMITE_DIARIO


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


AVATAR_AGENTE = ":material/account_balance:"
AVATAR_PESSOA = ":material/person:"


def mostrar_resposta(i: int, item: dict) -> None:
    with st.chat_message("assistant", avatar=AVATAR_AGENTE):
        if item.get("erro"):
            st.warning(item["erro"], icon=":material/hourglass_top:")
            return
        st.markdown(sem_latex(item["texto"]))
        selos = []
        if item["sem_suporte"]:
            selos.append(("alerta", "⚠", "Números sem suporte na API: "
                          + html.escape(", ".join(item["sem_suporte"]))))
        elif item["chamadas"]:
            selos.append(("ok", "✓", "Todos os números conferidos com a API"))
        if item["guardrail"]:
            selos.append(("info", "⛨", "Ajustada pelo guardrail de ano"))
        if selos:
            st.markdown('<div class="selos">' + "".join(
                f'<span class="selo {c}"><span aria-hidden="true">{ic}</span>{t}</span>'
                for c, ic, t in selos) + "</div>", unsafe_allow_html=True)
        if item["chamadas"]:
            n = len(item["chamadas"])
            with st.expander(f"Como cheguei nessa resposta ({n} consulta{'s' if n > 1 else ''} à API)",
                             icon=":material/manage_search:"):
                for c in item["chamadas"]:
                    st.markdown(f"**`{c['ferramenta']}`** {'✅' if c['ok'] else '❌'}")
                    st.code(json.dumps(c["argumentos"], ensure_ascii=False), language="json")
        voto = st.feedback("thumbs", key=f"voto_{i}")
        votados = st.session_state.setdefault("votados", set())
        if voto is not None and i not in votados:
            votar(item.get("id"), voto)
            votados.add(i)
            st.toast("Feedback registrado. Obrigado!", icon=":material/thumb_up:")


# ------------------------------------------------------------------ dados do topo
try:
    receitas = consultar("/receitas/origens")
    despesas = consultar("/despesas/orgaos", limite=10)
    comparativo = consultar("/comparativo/receita-despesa")
except Exception as e:  # noqa: BLE001
    st.error("Não consegui acessar o banco de dados agora. Tente de novo em instantes.")
    st.caption(f"Detalhe técnico: {type(e).__name__}")
    st.stop()

# ------------------------------------------------------------------ topo
arrecadado, liquidado = D(receitas["total_arrecadado"]), D(despesas["total_geral"])
maior = max(arrecadado, liquidado)
st.markdown(
    f"""
    <section class="topo" aria-label="Resumo de 2023">
      <div class="marca">
        <b>Orçamento Público do Recife</b>
        <a href="{REPO}" target="_blank" rel="noopener">Código e documentação no GitHub</a>
      </div>
      <p class="frase">Em 2023, a prefeitura arrecadou
        <span class="n rec" title="{brl(arrecadado, False)}">{brl(arrecadado)}</span>
        e gastou <span class="n desp" title="{brl(liquidado, False)}">{brl(liquidado)}</span>.</p>
      <div class="balanca" role="img"
           aria-label="Receita arrecadada {brl(arrecadado, False)}; despesa liquidada {brl(liquidado, False)}">
        <span>Receita arrecadada</span>
        <div class="trilho"><i class="rec" style="width:{arrecadado / maior * 100:.2f}%"></i></div>
        <span class="valor">{brl(arrecadado, False)}</span>
        <span>Despesa liquidada</span>
        <div class="trilho"><i class="desp" style="width:{liquidado / maior * 100:.2f}%"></i></div>
        <span class="valor">{brl(liquidado, False)}</span>
      </div>
      <div class="fatos">
        <span>Sobra sem transferências internas: <b>{brl(comparativo["saldo"])}</b></span>
        <span>Da receita prevista, entrou <b>{pct(receitas["total_execucao_pct"])}</b></span>
        <span>Fonte: Portal de Dados Abertos do Recife</span>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

aba_chat, aba_painel, aba_sobre = st.tabs(["Perguntar", "Painel", "Como funciona"])

# ------------------------------------------------------------------ aba: chat
with aba_chat:
    if not llm_configurado():
        st.info("O agente de IA não está configurado neste ambiente (falta `LLM_BASE_URL`). "
                "O painel continua funcionando.", icon=":material/power_off:")
    else:
        historico = st.session_state.setdefault("historico", [])

        if not historico:
            st.markdown(
                '<div class="vazio"><h3>Pergunte em português</h3>'
                "<p>O agente consulta a mesma API do painel e só cita números que vieram dela. "
                "Ele cobre receitas e despesas de 2023: órgãos, áreas, credores, impostos e "
                "evolução mês a mês.</p></div>", unsafe_allow_html=True)
            colunas = st.columns(3)
            for j, sugestao in enumerate(SUGESTOES):
                if colunas[j % 3].button(sugestao, key=f"sug_{j}", use_container_width=True):
                    st.session_state["pendente"] = sugestao
                    st.rerun()

        for i, item in enumerate(historico):
            with st.chat_message("user", avatar=AVATAR_PESSOA):
                st.markdown(sem_latex(item["pergunta"]))
            mostrar_resposta(i, item)

        usadas = perguntas_hoje()
        if usadas is not None:
            fracao = min(usadas / LIMITE_DIARIO, 1) if LIMITE_DIARIO else 1
            st.markdown(
                f'<div class="cota">Perguntas hoje, somando todos os visitantes: '
                f'<span class="barra" aria-hidden="true"><i style="width:{fracao * 100:.0f}%"></i></span>'
                f"{usadas} de {LIMITE_DIARIO}. Não digite dados pessoais: as perguntas vão para "
                f"um modelo de IA externo.</div>", unsafe_allow_html=True)

        digitada = st.chat_input("Pergunte sobre o orçamento de 2023…",
                                 max_chars=300)
        pergunta = digitada or st.session_state.pop("pendente", None)
        if pergunta:
            agora = time.time()
            ultima = st.session_state.get("ultima_pergunta_em", 0)
            if cota_diaria_esgotada():
                st.warning("O agente atingiu o limite de perguntas de hoje (plano gratuito). "
                           "Volte amanhã, o painel continua disponível.",
                           icon=":material/do_not_disturb_on:")
            elif len(historico) >= MAX_PERGUNTAS:
                st.warning(f"Você chegou a {MAX_PERGUNTAS} perguntas nesta visita. "
                           "Volte mais tarde para continuar.", icon=":material/do_not_disturb_on:")
            elif agora - ultima < INTERVALO_S:
                st.warning(f"Espere {INTERVALO_S} segundos entre uma pergunta e outra.",
                           icon=":material/timer:")
            else:
                st.session_state["ultima_pergunta_em"] = agora
                with st.spinner("Consultando a API…"):
                    item = perguntar(pergunta)
                historico.append(item)
                st.rerun()  # redesenha: conversa acima da caixa de texto, sem as sugestões

# ------------------------------------------------------------------ aba: painel
with aba_painel:
    meses = comparativo["meses"]
    with st.container(border=True):
        titulo_grafico("Receita e despesa, mês a mês",
                       "Sem transferências internas entre órgãos da prefeitura. Em milhões de reais.",
                       [("Receita arrecadada", COR_RECEITA), ("Despesa liquidada", COR_DESPESA)])
        x = [MESES[int(m["ano_mes"][-2:]) - 1] for m in meses]
        fig = go.Figure()
        for nome, campo, cor in (("Receita", "receita_arrecadada", COR_RECEITA),
                                 ("Despesa", "despesa", COR_DESPESA)):
            y = [D(m[campo]) / 1e6 for m in meses]
            fig.add_trace(go.Scatter(
                x=x, y=y, name=nome, mode="lines+markers",
                line=dict(color=cor, width=2), marker=dict(size=8, color=cor,
                                                           line=dict(color="#ffffff", width=2)),
                customdata=[brl(m[campo], False) for m in meses],
                hovertemplate=f"{nome}: %{{customdata}}<extra></extra>",
            ))
            fig.add_annotation(x=x[-1], y=y[-1], text=nome, showarrow=False,
                               xanchor="left", xshift=10, font=dict(color=TINTA_2, size=12))
        layout_base(fig, altura=360)
        fig.update_layout(hovermode="x unified", margin=dict(r=64))
        fig.update_yaxes(ticksuffix=" mi", rangemode="tozero", tickformat=",.0f", nticks=5)
        fig.update_xaxes(showgrid=False, linecolor=LINHA)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        titulo_grafico("Órgãos que mais gastaram", "Despesa liquidada em 2023, 10 maiores")
        org = despesas["orgaos"]
        nomes_org = rotulos_unicos(
            [nome_curto(o["orgao_nome"], 30) for o in org],
            ["supervisionada" if "SUPERVISIONADA" in o["orgao_nome"] else f"cód. {o['orgao_codigo']}"
             for o in org])
        st.plotly_chart(
            barras_horizontais(nomes_org, [o["valor"] for o in org], COR_DESPESA, "Liquidado",
                               nomes_completos=[o["orgao_nome"].title() for o in org]),
            use_container_width=True, config=PLOTLY_CFG)
    with c2, st.container(border=True):
        titulo_grafico("De onde veio o dinheiro", "Receita arrecadada em 2023, por origem")
        ori = [o for o in receitas["origens"] if D(o["arrecadado"]) > 0][:8]
        nomes_ori = rotulos_unicos(
            [nome_curto(o["origem_nome"], 40) for o in ori],
            ["intra" if "INTRA" in o["categoria_receita_nome"] else
             ("capital" if "CAPITAL" in o["categoria_receita_nome"] else "corrente") for o in ori])
        st.plotly_chart(
            barras_horizontais(nomes_ori, [o["arrecadado"] for o in ori], COR_RECEITA, "Arrecadado",
                               nomes_completos=[f"{o['origem_nome'].title()} · "
                                                f"{o['categoria_receita_nome'].title()}" for o in ori]),
            use_container_width=True, config=PLOTLY_CFG)

    with st.container(border=True):
        titulo_grafico("Quem mais recebeu da prefeitura",
                       "Valor pago em 2023 a empresas, bancos e fundos, somado por nome. "
                       "Não inclui a folha registrada sem credor.")
        cred = consultar("/despesas/credores/ranking", limite=10)["credores"]
        st.plotly_chart(
            barras_horizontais([nome_curto(c["credor_nome"], 40) for c in cred],
                               [c["valor"] for c in cred], COR_DESPESA, "Pago",
                               nomes_completos=[c["credor_nome"].title() for c in cred]),
            use_container_width=True, config=PLOTLY_CFG)

    with st.expander("Ver os números mês a mês em tabela", icon=":material/table:"):
        st.dataframe(
            [{"Mês": m["ano_mes"], "Receita (R$)": D(m["receita_arrecadada"]),
              "Despesa (R$)": D(m["despesa"]), "Saldo (R$)": D(m["saldo"])} for m in meses],
            use_container_width=True, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.2f")
                           for c in ("Receita (R$)", "Despesa (R$)", "Saldo (R$)")},
        )

# ------------------------------------------------------------------ aba: como funciona
with aba_sobre:
    st.markdown(
        """
        <div class="etapas">
          <div class="etapa"><h4>Dados</h4><p>CSVs oficiais da prefeitura limpos em PySpark,
            carregados no PostgreSQL e modelados em estrela com dbt, com 86 testes de qualidade.</p></div>
          <div class="etapa"><h4>API</h4><p>FastAPI com 10 endpoints tipados. As descrições foram
            escritas para um LLM ler, e este painel usa a mesma API.</p></div>
          <div class="etapa"><h4>Agente</h4><p>Cada endpoint vira uma ferramenta. Um verificador
            fora do LLM confere se todo número da resposta veio da API.</p></div>
          <div class="etapa"><h4>Evals</h4><p>30 perguntas com gabarito calculado por SQL direto
            nos dados brutos, sem passar pela API. Os resultados ficam versionados.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
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
            "Rodada": f"{arq.name[6:8]}/{arq.name[4:6]} {arq.name[9:11]}h{arq.name[11:13]}",
            "Modelo": ag.get("modelo", "qwen2.5:7b"),
            "Acerto (%)": acerto["media"] if isinstance(acerto, dict) else acerto,
            # métrica criada depois das primeiras rodadas: nelas, não foi medida
            "LLM sem guardrail (%)": "não medido" if sem_g is None else
                f"{(sem_g['media'] if isinstance(sem_g, dict) else sem_g):.1f}".replace(".", ","),
            "Repetições": ag.get("repeticoes", 1),
        })
    if linhas:
        st.markdown("### Histórico dos evals")
        st.caption("Todas as rodadas, inclusive as que pioraram. Números válidos para estes 30 "
                   "casos, escritos pelo autor; não são uma medida de confiabilidade geral.")
        st.dataframe(linhas, use_container_width=True, hide_index=True,
                     column_config={"Acerto (%)": st.column_config.ProgressColumn(
                         min_value=0, max_value=100, format="%.1f")})

st.markdown(
    f'<div class="rodape">Dados do Portal de Dados Abertos da Prefeitura do Recife (2023). '
    f'Projeto de portfólio de Davi Ramos Ferreira. <a href="{REPO}">Código no GitHub</a>.</div>',
    unsafe_allow_html=True,
)
