"""Tools do agente geradas a partir do OpenAPI da própria API.

Fonte única de verdade: a descrição que o agente lê é a mesma do /docs do FastAPI.
Mudou um endpoint? A tool muda junto, sem duplicar contrato.
"""
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

LIMITE_RESULTADO = 8000  # caracteres devolvidos ao LLM por chamada (protege o contexto)


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    caminho: str
    schema: dict  # formato "function" do tool calling (compatível com OpenAI/Ollama/Groq)


def _nome(caminho: str) -> str:
    return caminho.strip("/").replace("/", "_").replace("-", "_")


def gerar_ferramentas(openapi: dict) -> list[Ferramenta]:
    ferramentas = []
    for caminho, ops in openapi["paths"].items():
        op = ops.get("get")
        if op is None:
            continue
        props, obrigatorios = {}, []
        for p in op.get("parameters", []):
            if p.get("in") != "query":
                continue
            esquema = _resolver(openapi, p["schema"])
            esquema["description"] = p.get("description", "")
            props[p["name"]] = esquema
            if p.get("required"):
                obrigatorios.append(p["name"])
        descricao = f"{op.get('summary', '')}. {op.get('description', '')}".strip()
        ferramentas.append(Ferramenta(
            nome=_nome(caminho),
            caminho=caminho,
            schema={"type": "function", "function": {
                "name": _nome(caminho),
                "description": " ".join(descricao.split()),
                "parameters": {"type": "object", "properties": props, "required": obrigatorios},
            }},
        ))
    return ferramentas


def _resolver(openapi: dict, esquema: dict) -> dict:
    """Simplifica o JSON Schema do FastAPI para o que modelos pequenos entendem bem."""
    if "$ref" in esquema:
        extra = {k: v for k, v in esquema.items() if k != "$ref"}  # ex.: default
        esquema = {**openapi["components"]["schemas"][esquema["$ref"].split("/")[-1]], **extra}
    if "anyOf" in esquema:  # Optional[X] -> X (o "opcional" já está em 'required')
        nao_nulos = [s for s in esquema["anyOf"] if s.get("type") != "null"]
        base = _resolver(openapi, nao_nulos[0]) if nao_nulos else {"type": "string"}
        return {**base, **({"default": esquema["default"]} if "default" in esquema else {})}
    chaves = ("type", "enum", "minimum", "maximum", "default", "minLength")
    return {k: esquema[k] for k in chaves if k in esquema}


class ExecutorHTTP:
    """Executa uma tool chamando a API de verdade."""

    def __init__(self, ferramentas: list[Ferramenta], base_url: str | None = None):
        self._por_nome = {f.nome: f for f in ferramentas}
        self._http = httpx.Client(
            base_url=base_url or os.getenv("API_URL", "http://localhost:8000"), timeout=30
        )

    def __call__(self, nome: str, argumentos: dict[str, Any]) -> tuple[bool, str]:
        ferramenta = self._por_nome.get(nome)
        if ferramenta is None:
            return False, json.dumps({"erro": f"tool '{nome}' não existe"})
        resp = self._http.get(ferramenta.caminho, params=argumentos)
        texto = resp.text[:LIMITE_RESULTADO]
        if resp.status_code != 200:
            return False, json.dumps({"erro": f"HTTP {resp.status_code}", "detalhe": texto})
        return True, texto
