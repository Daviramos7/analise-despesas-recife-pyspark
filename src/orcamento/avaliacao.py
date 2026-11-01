"""Pontuação dos evals (pura, sem LLM nem banco: testável isoladamente)."""
import unicodedata
from dataclasses import asdict, dataclass
from decimal import Decimal

from orcamento.agente.agente import FRASE_SEM_DADO, RespostaAgente
from orcamento.agente.verificacao import extrair_numeros

TIPOS = {"numero", "texto", "recusa"}


def normalizar(txt: str) -> str:
    nfkd = unicodedata.normalize("NFKD", txt.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@dataclass
class ResultadoCaso:
    id: str
    tipo: str
    pergunta: str
    esperado: str | None
    resposta: str
    ferramentas_chamadas: list[str]
    ferramenta_ok: bool
    acerto: bool
    numeros_sem_suporte: list[str]
    iteracoes: int
    chamadas: list[dict] | None = None   # ferramenta, argumentos, ok, início do resultado
    guardrail: str | None = None         # o código sobrescreveu a resposta do LLM?
    acerto_llm: bool | None = None       # acerto da resposta ORIGINAL do LLM (sem guardrail)
    erro: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def _acertou(tipo: str, texto: str, esperado, sem_suporte: list[str]) -> bool:
    if tipo == "numero":
        alvo = Decimal(str(esperado))
        return any(n.casa_com(alvo) for n in extrair_numeros(texto))
    if tipo == "texto":
        return normalizar(str(esperado)) in normalizar(texto)
    if tipo == "recusa":
        return normalizar(FRASE_SEM_DADO) in normalizar(texto) and not sem_suporte
    raise ValueError(f"tipo desconhecido: {tipo}")


def avaliar(caso: dict, resp: RespostaAgente, esperado) -> ResultadoCaso:
    tipo = caso["tipo"]
    chamadas = [c.ferramenta for c in resp.chamadas]
    sem_suporte = resp.numeros_sem_suporte

    acerto = _acertou(tipo, resp.texto, esperado, sem_suporte)
    if resp.guardrail:
        from orcamento.agente.verificacao import numeros_sem_suporte
        texto_llm = resp.texto_llm or ""
        acerto_llm = _acertou(tipo, texto_llm, esperado, numeros_sem_suporte(
            texto_llm, [c.resultado for c in resp.chamadas], resp.pergunta))
    else:
        acerto_llm = acerto

    aceitas = set(caso.get("ferramentas_aceitas", []))
    if tipo == "recusa":  # recusar sem chamar nada também é correto
        ferramenta_ok = not chamadas or bool(aceitas & set(chamadas))
    else:
        ferramenta_ok = bool(aceitas & set(chamadas))

    return ResultadoCaso(
        id=caso["id"], tipo=tipo, pergunta=caso["pergunta"],
        esperado=None if esperado is None else str(esperado),
        resposta=resp.texto, ferramentas_chamadas=chamadas, ferramenta_ok=ferramenta_ok,
        acerto=acerto, numeros_sem_suporte=sem_suporte, iteracoes=resp.iteracoes,
        chamadas=[{"ferramenta": c.ferramenta, "argumentos": c.argumentos, "ok": c.ok,
                   "resultado_inicio": c.resultado[:300]} for c in resp.chamadas],
        guardrail=resp.guardrail, acerto_llm=acerto_llm,
    )


def resumir(resultados: list[ResultadoCaso]) -> dict:
    n = len(resultados)
    if n == 0:
        return {"casos": 0}
    pct = lambda k: round(100 * k / n, 1)  # noqa: E731
    por_tipo = {}
    for t in sorted({r.tipo for r in resultados}):
        sub = [r for r in resultados if r.tipo == t]
        por_tipo[t] = f"{sum(r.acerto for r in sub)}/{len(sub)}"
    return {
        "casos": n,
        "acerto_pct": pct(sum(r.acerto for r in resultados)),
        "acerto_llm_sem_guardrail_pct": pct(sum(bool(r.acerto_llm) for r in resultados)),
        "guardrail_acionado": sum(r.guardrail is not None for r in resultados),
        "ferramenta_correta_pct": pct(sum(r.ferramenta_ok for r in resultados)),
        "respostas_com_numero_sem_suporte": sum(bool(r.numeros_sem_suporte) for r in resultados),
        "erros_execucao": sum(r.erro is not None for r in resultados),
        "acerto_por_tipo": por_tipo,
    }


def agregar(rodadas: list[dict]) -> dict:
    """Média/mín/máx de várias repetições (LLM local não é 100% determinístico)."""
    if not rodadas:
        return {}
    chaves = ["acerto_pct", "acerto_llm_sem_guardrail_pct", "ferramenta_correta_pct",
              "respostas_com_numero_sem_suporte", "guardrail_acionado"]
    return {k: {"media": round(sum(r[k] for r in rodadas) / len(rodadas), 1),
                "min": min(r[k] for r in rodadas), "max": max(r[k] for r in rodadas)}
            for k in chaves if all(k in r for r in rodadas)} | {"repeticoes": len(rodadas)}
