"""Testes do agente sem LLM real: um cliente falso devolve respostas roteirizadas."""
import json
from decimal import Decimal
from types import SimpleNamespace as NS

from orcamento.agente.agente import FRASE_SEM_DADO, MAX_ITERACOES, Agente
from orcamento.agente.ferramentas import gerar_ferramentas
from orcamento.agente.verificacao import extrair_numeros, numeros_sem_suporte
from orcamento.api.app import app


def _tool_call(id_, nome, args):
    return NS(id=id_, function=NS(name=nome, arguments=json.dumps(args)))


def _msg(content=None, tool_calls=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


class LLMFalso:
    def __init__(self, roteiro):
        self.roteiro, self.recebido = list(roteiro), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.recebido.append(kw)
        return self.roteiro.pop(0)


def test_ferramentas_geradas_do_openapi():
    fs = {f.nome: f for f in gerar_ferramentas(app.openapi())}
    assert set(fs) == {
        "metadados", "orgaos", "despesas_orgaos", "despesas_evolucao_mensal",
        "despesas_credores_ranking", "despesas_funcoes", "receitas_origens", "receitas_itens",
        "receitas_evolucao_mensal", "comparativo_receita_despesa"}
    params = fs["despesas_orgaos"].schema["function"]["parameters"]["properties"]
    assert params["medida"]["enum"] == ["empenhado", "liquidado", "pago"]
    assert params["medida"]["default"] == "liquidado"
    assert "liquidado" in params["medida"]["description"]
    assert fs["receitas_itens"].schema["function"]["parameters"]["required"] == ["busca"]


def test_loop_executa_tool_e_devolve_resultado_ao_llm():
    llm = LLMFalso([
        _msg(tool_calls=[_tool_call("c1", "despesas_orgaos", {"medida": "liquidado"})]),
        _msg(content="A Saúde liquidou R$ 1.668.250.043,27."),
    ])
    executadas = []

    def executar(nome, args):
        executadas.append((nome, args))
        return True, json.dumps({"valor": "1668250043.27"})

    resp = Agente(llm, "falso", [], executar).perguntar("Quanto a saúde gastou?")

    assert executadas == [("despesas_orgaos", {"medida": "liquidado"})]
    assert resp.texto == "A Saúde liquidou R$ 1.668.250.043,27."
    assert resp.iteracoes == 2 and resp.numeros_sem_suporte == []
    ultima = llm.recebido[1]["messages"]
    assert ultima[-1] == {"role": "tool", "tool_call_id": "c1", "content": '{"valor": "1668250043.27"}'}
    assert llm.recebido[0]["temperature"] == 0


def test_numero_inventado_e_detectado():
    llm = LLMFalso([
        _msg(tool_calls=[_tool_call("c1", "receitas_origens", {})]),
        _msg(content="Arrecadou R$ 7.882.016.730,69, cerca de R$ 9,1 bilhões a mais que 2022."),
    ])
    resp = Agente(llm, "falso", [], lambda n, a: (True, '{"total": "7882016730.69"}')).perguntar("x")
    assert resp.numeros_sem_suporte == ["9,1 bilhões"]


def test_argumentos_invalidos_viram_erro_para_o_llm_sem_quebrar():
    chamada = NS(id="c1", function=NS(name="orgaos", arguments="{nao é json"))
    llm = LLMFalso([_msg(tool_calls=[chamada]), _msg(content="ok")])
    resp = Agente(llm, "falso", [], lambda n, a: (True, "{}")).perguntar("x")
    assert resp.chamadas[0].ok is False and "erro" in resp.chamadas[0].resultado


def test_limite_de_iteracoes():
    loop = [_msg(tool_calls=[_tool_call(f"c{i}", "metadados", {})]) for i in range(MAX_ITERACOES)]
    resp = Agente(LLMFalso(loop), "falso", [], lambda n, a: (True, "{}")).perguntar("x")
    assert resp.texto.startswith(FRASE_SEM_DADO) and resp.iteracoes == MAX_ITERACOES


def test_extrair_numeros_formatos_brasileiros():
    nums = {n.texto: n.valor for n in extrair_numeros(
        "R$ 1.668.250.043,27 (21,38%), uns 1,67 bilhão; 660 milhões; api: 7882016730.69")}
    D = Decimal
    assert nums["1.668.250.043,27"] == D("1668250043.27")
    assert nums["21,38"] == D("21.38")
    assert nums["1,67 bilhão"] == D("1670000000")
    assert nums["660 milhões"] == D("660000000")
    assert nums["7882016730.69"] == D("7882016730.69")


def test_arredondamento_coerente_e_aceito_mas_errado_nao():
    tools = ['{"valor": "1668250043.27"}']
    assert numeros_sem_suporte("cerca de R$ 1,67 bilhão", tools) == []
    assert numeros_sem_suporte("cerca de R$ 1,70 bilhão", tools) == ["1,70 bilhão"]
    assert numeros_sem_suporte("em 2023, no mês 12, 3º lugar", tools) == []  # triviais
    assert numeros_sem_suporte("custou R$ 1,00", tools) == ["1,00"]  # dinheiro nunca é trivial
    assert numeros_sem_suporte("custou R$ 7", tools) == ["7"]


def test_versao_de_prompt_e_enviada_ao_llm():
    from orcamento.agente.agente import PROMPTS
    for versao, texto in PROMPTS.items():
        llm = LLMFalso([_msg(content="ok")])
        Agente(llm, "falso", [], lambda n, a: (True, "{}"), prompt_versao=versao).perguntar("x")
        assert llm.recebido[0]["messages"][0] == {"role": "system", "content": texto}
    assert "parâmetro ano" in PROMPTS["v2"] and "parâmetro ano" not in PROMPTS["v1"]


def test_ano_fica_fora_das_tools_do_agente():
    # Decisão guiada por eval: expor 'ano' derrubou o acerto do qwen2.5:7b (ver evals/README.md)
    for f in gerar_ferramentas(app.openapi()):
        assert "ano" not in f.schema["function"]["parameters"]["properties"], f.nome


def test_guardrail_ano_substitui_resposta_do_ano_errado():
    llm = LLMFalso([
        _msg(tool_calls=[_tool_call("c1", "despesas_orgaos", {})]),
        _msg(content="A Saúde gastou R$ 1.668.250.043,27."),
    ])
    tool = json.dumps({"anos_dos_dados": [2023], "total_geral": "1668250043.27"})
    resp = Agente(llm, "falso", [], lambda n, a: (True, tool)).perguntar("Quanto a Saúde gastou em 2022?")
    assert resp.texto.startswith(FRASE_SEM_DADO) and "2023" in resp.texto and "2022" in resp.texto
    assert resp.texto_llm == "A Saúde gastou R$ 1.668.250.043,27."
    assert resp.guardrail == "ano [2022] fora de [2023]"


def test_guardrail_ano_nao_mexe_quando_ano_existe_ou_nao_ha_ano():
    tool = json.dumps({"anos_dos_dados": [2023], "total_geral": "10.00"})
    for pergunta in ["Quanto gastou em 2023?", "Quanto gastou?"]:
        llm = LLMFalso([_msg(tool_calls=[_tool_call("c1", "despesas_orgaos", {})]), _msg(content="R$ 10,00")])
        resp = Agente(llm, "falso", [], lambda n, a: (True, tool)).perguntar(pergunta)
        assert resp.texto == "R$ 10,00" and resp.guardrail is None


def test_assinatura_de_pensamento_volta_intacta_para_o_llm():
    """Gemini 3 exige que tool_calls[].extra_content volte no turno seguinte (senão HTTP 400)."""
    from openai.types.chat import ChatCompletion

    def completion(message):
        return ChatCompletion.model_validate({
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}]})

    chamada = {"id": "c1", "type": "function",
               "function": {"name": "metadados", "arguments": "{}"},
               "extra_content": {"google": {"thought_signature": "SIG123"}}}
    llm = LLMFalso([
        completion({"role": "assistant", "content": None, "tool_calls": [chamada]}),
        completion({"role": "assistant", "content": "ok"}),
    ])
    Agente(llm, "falso", [], lambda n, a: (True, "{}")).perguntar("x")
    assistente = llm.recebido[1]["messages"][2]
    assert assistente["tool_calls"][0]["extra_content"] == {"google": {"thought_signature": "SIG123"}}
    assert assistente["content"] == ""


def test_descricao_do_comparativo_desaconselha_uso_para_totais():
    fs = {f.nome: f for f in gerar_ferramentas(app.openapi())}
    desc = fs["comparativo_receita_despesa"].schema["function"]["description"]
    assert "NÃO use para" in desc and "intraorçamentárias" in desc


def test_executor_in_process_chama_a_mesma_api():
    from fastapi.testclient import TestClient

    from orcamento.agente.ferramentas import ExecutorHTTP

    fs = gerar_ferramentas(app.openapi())
    chamados = []

    class ClienteFalso:  # mesma interface do TestClient/httpx
        def get(self, caminho, params=None):
            chamados.append((caminho, params))
            return NS(status_code=200, text='{"ok": true}')

    ok, texto = ExecutorHTTP(fs, cliente=ClienteFalso())("despesas_orgaos", {"medida": "pago"})
    assert ok and chamados == [("/despesas/orgaos", {"medida": "pago"})]
    assert isinstance(TestClient(app), object)  # TestClient é aceito como cliente
