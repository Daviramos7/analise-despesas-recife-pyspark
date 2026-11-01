"""Conversa com o agente no terminal e coleta 👍/👎.

    python -m despesas.agente.cli
"""
from despesas.agente.agente import criar_agente_padrao
from despesas.feedback import registrar


def main() -> None:
    agente = criar_agente_padrao()
    print(f"Agente de receitas e despesas do Recife (modelo: {agente.modelo}). Enter vazio sai.\n")
    while True:
        pergunta = input("Você: ").strip()
        if not pergunta:
            break
        resp = agente.perguntar(pergunta)
        print(f"\nAgente: {resp.texto}")
        print(f"  tools: {[c.ferramenta for c in resp.chamadas] or 'nenhuma'}")
        if resp.numeros_sem_suporte:
            print(f"  ⚠️  números sem suporte nas tools: {resp.numeros_sem_suporte}")
        voto = input("Resposta boa? [s/n/Enter=pular]: ").strip().lower()
        avaliacao = {"s": 1, "n": -1}.get(voto)
        comentario = input("O que estava errado? ").strip() or None if avaliacao == -1 else None
        registrar(resp, avaliacao, comentario)
        print()


if __name__ == "__main__":
    main()
