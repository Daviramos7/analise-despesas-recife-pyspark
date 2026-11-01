"""Roda os evals: gabarito via SQL direto no banco x resposta do agente.

    python evals/rodar.py                 # todos os casos
    python evals/rodar.py --so rec_iptu   # um caso
    python evals/rodar.py --gabarito      # só calcula e mostra os gabaritos (sem LLM)
    python evals/rodar.py --repeticoes 3  # mede variância
    PROMPT_VERSAO=v2 python evals/rodar.py
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import yaml

from orcamento.agente.agente import RespostaAgente, criar_agente_padrao
from orcamento.avaliacao import ResultadoCaso, agregar, avaliar, resumir
from orcamento.config import dsn

AQUI = Path(__file__).parent


def carregar_casos() -> list[dict]:
    return yaml.safe_load((AQUI / "casos.yaml").read_text(encoding="utf-8"))


def calcular_gabaritos(casos: list[dict]) -> dict[str, object]:
    with psycopg.connect(dsn()) as conn:
        return {c["id"]: (conn.execute(c["gabarito_sql"]).fetchone()[0]
                          if c.get("gabarito_sql") else None) for c in casos}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", nargs="*", help="ids de casos a rodar")
    ap.add_argument("--gabarito", action="store_true", help="só mostra os gabaritos")
    ap.add_argument("--repeticoes", type=int, default=1, help="rodadas completas (variância)")
    ap.add_argument("--pausa", type=float, default=0.0,
                    help="segundos entre perguntas (útil em plano gratuito com limite por minuto)")
    args = ap.parse_args()

    casos = [c for c in carregar_casos() if not args.so or c["id"] in args.so]
    gabaritos = calcular_gabaritos(casos)
    if args.gabarito:
        for c in casos:
            print(f"{c['id']:32} {gabaritos[c['id']]}")
        return 0

    agente = criar_agente_padrao()
    rodadas, todas = [], []
    for rep in range(1, args.repeticoes + 1):
        print(f"\n=== rodada {rep}/{args.repeticoes} · modelo={agente.modelo} · prompt={agente.prompt_versao}")
        resultados: list[ResultadoCaso] = []
        inicio = time.time()
        for c in casos:
            try:
                resp = agente.perguntar(c["pergunta"])
                r = avaliar(c, resp, gabaritos[c["id"]])
            except Exception as e:  # noqa: BLE001 - erro de execução também é resultado
                r = avaliar(c, RespostaAgente(c["pergunta"], ""), gabaritos[c["id"]])
                r.erro = f"{type(e).__name__}: {e}"
            resultados.append(r)
            if args.pausa:
                time.sleep(args.pausa)
            marca = "✅" if r.acerto else "❌"
            alerta = f"  ⚠️ sem suporte: {r.numeros_sem_suporte}" if r.numeros_sem_suporte else ""
            print(f"{marca} {r.id:30} tools={r.ferramentas_chamadas}{alerta}", flush=True)
            if r.erro:
                print(f"   erro: {r.erro}")
        resumo = resumir(resultados) | {"duracao_s": round(time.time() - inicio, 1)}
        rodadas.append(resumo)
        todas.append({"rodada": rep, "resumo": resumo, "casos": [r.dict() for r in resultados]})
        print(json.dumps(resumo, ensure_ascii=False))

    meta = {
        "modelo": agente.modelo,
        "prompt_versao": agente.prompt_versao,
        "llm_base_url": os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        "pausa_s": args.pausa,
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "casos": len(casos),
    }
    agregado = meta | agregar(rodadas)
    print("\n" + json.dumps(agregado, ensure_ascii=False, indent=2))

    saida = AQUI / "resultados"
    saida.mkdir(exist_ok=True)
    modelo = agente.modelo.replace(":", "-").replace("/", "-")
    nome = f"{datetime.now(timezone.utc):%Y%m%d-%H%M}_{modelo}_prompt-{agente.prompt_versao}_x{args.repeticoes}.json"
    (saida / nome).write_text(json.dumps({"agregado": agregado, "rodadas": todas},
                                         ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nresultado salvo em evals/resultados/{nome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
