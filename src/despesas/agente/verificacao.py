"""Checagem de "grounding": todo número citado na resposta precisa ter vindo de uma tool.

Não confia no LLM: extrai os números do texto final e compara com os números presentes
nos JSONs retornados pela API. É a base do detector de alucinação dos evals.
"""
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# "1.668.250.043,27" | "21,38" | "7882016730.69" | "1,67 bilhão" | "660 milhões"
_NUM = re.compile(
    r"(R\$\s*)?(?<![\w.,])(-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:[.,]\d+)?)"
    r"(\s*(?:bilh(?:ão|ões|ao|oes)|milh(?:ão|ões|ao|oes)|mil\b|bi\b|mi\b))?",
    re.IGNORECASE,
)
_ESCALAS = [("bilh", 10**9), ("bi", 10**9), ("milh", 10**6), ("mil", 10**3), ("mi", 10**6)]


@dataclass(frozen=True)
class NumeroCitado:
    texto: str
    valor: Decimal
    tolerancia: Decimal  # meia unidade da última casa escrita: "1,67 bilhão" -> ±5 milhões
    monetario: bool = False  # veio com "R$" na frente
    tem_decimais: bool = False

    def casa_com(self, alvo: Decimal) -> bool:
        return abs(self.valor - alvo) <= self.tolerancia


def _para_decimal(bruto: str) -> tuple[Decimal, int]:
    """Converte número escrito em pt-BR (ou com ponto decimal) e devolve (valor, casas)."""
    if "," in bruto:
        inteiro, frac = bruto.replace(".", "").split(",")
        return Decimal(f"{inteiro}.{frac}"), len(frac)
    if bruto.count(".") == 1 and len(bruto.split(".")[1]) != 3:
        return Decimal(bruto), len(bruto.split(".")[1])  # "7882016730.69" (formato da API)
    return Decimal(bruto.replace(".", "")), 0  # "1.234.567" = separador de milhar


def extrair_numeros(texto: str) -> list[NumeroCitado]:
    numeros = []
    for m in _NUM.finditer(texto):
        try:
            valor, casas = _para_decimal(m.group(2))
        except (InvalidOperation, ValueError):
            continue
        escala = 1
        sufixo = (m.group(3) or "").strip().lower()
        for prefixo, fator in _ESCALAS:
            if sufixo.startswith(prefixo):
                escala = fator
                break
        meia_unidade = Decimal(5) / Decimal(10) ** (casas + 1)
        texto_num = (m.group(2) + (m.group(3) or "")).strip()
        numeros.append(NumeroCitado(texto_num, valor * escala, meia_unidade * escala,
                                    monetario=bool(m.group(1)), tem_decimais=casas > 0))
    return numeros


def numeros_das_tools(resultados: list[str]) -> set[Decimal]:
    """Coleta todo valor numérico (número ou string numérica) dos JSONs das tools."""
    achados: set[Decimal] = set()

    def visitar(x):
        if isinstance(x, dict):
            for v in x.values():
                visitar(v)
        elif isinstance(x, list):
            for v in x:
                visitar(v)
        elif isinstance(x, bool):
            return
        elif isinstance(x, (int, float)):
            achados.add(Decimal(str(x)))
        elif isinstance(x, str):
            try:
                achados.add(Decimal(x))
            except InvalidOperation:
                for n in re.findall(r"\d+", x):  # ex.: "2023-05" -> 2023 e 5
                    achados.add(Decimal(n))

    for r in resultados:
        try:
            visitar(json.loads(r))
        except json.JSONDecodeError:
            continue
    return achados


def eh_trivial(n: NumeroCitado) -> bool:
    """Números que não são 'dado' (mês, posição de ranking, ano de referência).

    Só inteiros pequenos ou anos, escritos sem centavos, sem escala e sem "R$".
    """
    if n.monetario or n.tem_decimais or n.tolerancia >= 1:
        return False
    return 0 <= n.valor <= 100 or 1990 <= n.valor <= 2100


def numeros_sem_suporte(resposta: str, resultados_tools: list[str], pergunta: str = "") -> list[str]:
    """Números citados na resposta que não aparecem em nenhuma saída de tool (nem na pergunta)."""
    base = numeros_das_tools(resultados_tools) | {n.valor for n in extrair_numeros(pergunta)}
    return [
        n.texto for n in extrair_numeros(resposta)
        if not eh_trivial(n) and not any(n.casa_com(alvo) for alvo in base)
    ]
