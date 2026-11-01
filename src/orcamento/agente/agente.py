"""Agente com tool calling direto no SDK (sem framework).

O loop inteiro é este arquivo:
  1. manda pergunta + lista de tools pro LLM;
  2. se o LLM pedir tool, executa (HTTP na API) e devolve o resultado como mensagem 'tool';
  3. repete até o LLM responder em texto ou estourar MAX_ITERACOES.
Funciona com qualquer endpoint compatível com a API de chat da OpenAI:
Ollama (local, grátis), Groq (nuvem, plano gratuito) ou OpenAI.
"""
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from orcamento.agente.verificacao import numeros_sem_suporte

MAX_ITERACOES = 6
FRASE_SEM_DADO = "Não tenho esse dado"

_PROMPT_V1 = f"""Você é um assistente que responde perguntas sobre receitas e despesas \
públicas da Prefeitura do Recife, em português do Brasil.

REGRAS OBRIGATÓRIAS:
1. Só use números que vieram das ferramentas. NUNCA invente, estime ou calcule valores por \
conta própria (nem somas, nem diferenças): se precisar de um total, use o campo que a \
ferramenta já entrega.
2. Cite os valores exatamente como vieram, em reais, no formato brasileiro com centavos. \
Exemplo: 7882016730.69 vira "R$ 7.882.016.730,69". Percentuais: "21,38%".
3. Se nenhuma ferramenta tiver o dado (outro ano, nível de detalhe inexistente, assunto fora \
do escopo), responda começando com "{FRASE_SEM_DADO}" e explique em uma frase o que falta. \
Na dúvida sobre o que existe, chame metadados.
4. Para filtrar por órgão, descubra o código com a ferramenta orgaos antes.
5. "Quanto o órgão X gastou" = despesas_orgaos. "Quanto foi gasto COM saúde/educação" (a área) \
= despesas_funcoes. Para despesa, use a medida 'liquidado' quando a pergunta não especificar.
6. Responda de forma curta e direta, dizendo a medida usada (empenhado/liquidado/pago/arrecadado)."""

# v2 (2026-11-01): + regra de ano e distinção órgão x credor. Ver evals/README.md.
_PROMPT_V2 = f"""Você é um assistente que responde perguntas sobre receitas e despesas \
públicas da Prefeitura do Recife, em português do Brasil.

REGRAS OBRIGATÓRIAS:
1. Só use números que vieram das ferramentas. NUNCA invente, estime ou calcule valores por \
conta própria (nem somas, nem diferenças): se precisar de um total, use o campo que a \
ferramenta já entrega.
2. Cite os valores exatamente como vieram, em reais, no formato brasileiro com centavos. \
Exemplo: 7882016730.69 vira "R$ 7.882.016.730,69". Percentuais: "21,38%".
3. Se nenhuma ferramenta tiver o dado (outro ano, nível de detalhe inexistente, assunto fora \
do escopo), responda começando com "{FRASE_SEM_DADO}" e explique em uma frase o que falta. \
Na dúvida sobre o que existe, chame metadados.
4. Quando a pergunta citar um ano, passe SEMPRE o parâmetro ano. Se a ferramenta responder \
erro de ano indisponível, responda com "{FRASE_SEM_DADO}" e NÃO use dados de outro ano.
5. Órgão = secretaria/entidade da prefeitura (descubra o código com a ferramenta orgaos). \
Credor = empresa, banco, fundo ou pessoa que recebeu dinheiro (use despesas_credores_ranking \
com busca).
6. "Quanto o órgão X gastou" = despesas_orgaos. "Quanto foi gasto COM saúde/educação" (a área) \
= despesas_funcoes. Para despesa, use a medida 'liquidado' quando a pergunta não especificar.
7. Responda de forma curta e direta, dizendo a medida usada (empenhado/liquidado/pago/arrecadado)."""

PROMPTS = {"v1": _PROMPT_V1, "v2": _PROMPT_V2}
PROMPT_PADRAO = "v1"


@dataclass
class Chamada:
    ferramenta: str
    argumentos: dict[str, Any]
    ok: bool
    resultado: str


@dataclass
class RespostaAgente:
    pergunta: str
    texto: str
    chamadas: list[Chamada] = field(default_factory=list)
    iteracoes: int = 0
    modelo: str = ""
    guardrail: str | None = None       # motivo, quando o código sobrescreveu a resposta do LLM
    texto_llm: str | None = None       # resposta original do LLM antes do guardrail

    @property
    def numeros_sem_suporte(self) -> list[str]:
        return numeros_sem_suporte(self.texto, [c.resultado for c in self.chamadas], self.pergunta)


Executor = Callable[[str, dict[str, Any]], tuple[bool, str]]


def _mensagem_assistente(msg, chamadas) -> dict[str, Any]:
    """Devolve ao LLM a mensagem dele EXATAMENTE como veio, com campos desconhecidos inclusos.

    Modelos com raciocínio (ex.: Gemini 3) anexam uma assinatura do pensamento às tool calls
    (no modo compatível com OpenAI, em tool_calls[].extra_content). Se ela não volta no turno
    seguinte, a API responde 400. Reconstruir a mensagem campo a campo perdia essa assinatura.
    """
    if hasattr(msg, "model_dump"):
        dados = msg.model_dump(exclude_none=True)
        dados["content"] = dados.get("content") or ""
        return dados
    return {  # fallback para objetos simples (testes)
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in chamadas
        ],
    }


class Agente:
    def __init__(self, cliente, modelo: str, ferramentas_schema: list[dict], executar: Executor,
                 prompt_versao: str = PROMPT_PADRAO, max_tokens: int | None = None):
        self.cliente = cliente          # objeto com .chat.completions.create (SDK openai)
        self.modelo = modelo
        self.prompt_versao = prompt_versao
        self.prompt = PROMPTS[prompt_versao]
        self.ferramentas_schema = ferramentas_schema
        self.executar = executar
        self.max_tokens = max_tokens    # teto de tokens por resposta do LLM (custo/cota)

    def perguntar(self, pergunta: str) -> RespostaAgente:
        mensagens: list[dict[str, Any]] = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": pergunta},
        ]
        resposta = RespostaAgente(pergunta=pergunta, texto="", modelo=self.modelo)

        for i in range(1, MAX_ITERACOES + 1):
            resposta.iteracoes = i
            extras = {"max_tokens": self.max_tokens} if self.max_tokens else {}
            completion = self.cliente.chat.completions.create(
                model=self.modelo,
                messages=mensagens,
                tools=self.ferramentas_schema,
                temperature=0,  # reprodutibilidade dos evals
                **extras,
            )
            msg = completion.choices[0].message
            chamadas = msg.tool_calls or []

            if not chamadas:
                resposta.texto = (msg.content or "").strip()
                return aplicar_guardrail_ano(resposta)

            mensagens.append(_mensagem_assistente(msg, chamadas))
            for c in chamadas:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    ok, resultado, args = False, json.dumps({"erro": "argumentos não são JSON"}), {}
                else:
                    ok, resultado = self.executar(c.function.name, args)
                resposta.chamadas.append(Chamada(c.function.name, args, ok, resultado))
                mensagens.append({"role": "tool", "tool_call_id": c.id, "content": resultado})

        resposta.texto = f"{FRASE_SEM_DADO}: não consegui concluir a consulta em {MAX_ITERACOES} passos."
        return resposta


def _anos_nos_resultados(resultados: list[str]) -> set[int]:
    anos: set[int] = set()
    for r in resultados:
        try:
            dado = json.loads(r)
        except json.JSONDecodeError:
            continue
        if isinstance(dado, dict) and isinstance(dado.get("anos_dos_dados"), list):
            anos.update(int(a) for a in dado["anos_dos_dados"])
    return anos


def aplicar_guardrail_ano(resp: RespostaAgente) -> RespostaAgente:
    """Guardrail determinístico (fora do LLM) contra 'resposta certa do ano errado'.

    Se a pergunta cita um ano que não está em nenhum 'anos_dos_dados' devolvido pelas tools,
    a resposta é substituída. Motivação (evals 2026-11-01): o qwen2.5:7b respondia a pergunta
    sobre 2022 com o valor de 2023, ignorando anos_dos_dados; o detector de números não pega
    isso porque o valor existe.
    """
    anos_pergunta = {int(a) for a in re.findall(r"\b(19[9]\d|20\d\d)\b", resp.pergunta)}
    anos_dados = _anos_nos_resultados([c.resultado for c in resp.chamadas if c.ok])
    if not anos_pergunta or not anos_dados:
        return resp
    faltando = sorted(anos_pergunta - anos_dados)
    if faltando and normalizar_frase(FRASE_SEM_DADO) not in normalizar_frase(resp.texto):
        resp.texto_llm = resp.texto
        resp.guardrail = f"ano {faltando} fora de {sorted(anos_dados)}"
        resp.texto = (f"{FRASE_SEM_DADO}: os dados disponíveis são de "
                      f"{', '.join(map(str, sorted(anos_dados)))}, não de {', '.join(map(str, faltando))}.")
    return resp


def normalizar_frase(txt: str) -> str:
    return " ".join(txt.lower().split())


def criar_agente_padrao(cliente_api=None) -> Agente:
    """Agente configurado por variável de ambiente. Nenhuma chave no código.

    cliente_api: opcional; ex. TestClient(app) para chamar a API no mesmo processo.
    """
    from openai import OpenAI

    from orcamento.agente.ferramentas import ExecutorHTTP, gerar_ferramentas
    from orcamento.api.app import app

    ferramentas = gerar_ferramentas(app.openapi())
    cliente = OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("LLM_API_KEY", "ollama"),  # Ollama ignora; Groq/OpenAI exigem
        # Planos gratuitos (ex.: Groq 8k tokens/min) devolvem 429. O SDK reespera respeitando o
        # header retry-after; com várias tentativas a rodada fica lenta, mas não quebra.
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "8")),
        timeout=float(os.getenv("LLM_TIMEOUT_S", "120")),
    )
    return Agente(
        cliente=cliente,
        modelo=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        ferramentas_schema=[f.schema for f in ferramentas],
        executar=ExecutorHTTP(ferramentas, cliente=cliente_api),
        prompt_versao=os.getenv("PROMPT_VERSAO", PROMPT_PADRAO),
        # Respostas do agente são curtas; o teto só corta abuso ("escreva um TCC...").
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")) or None,
    )
