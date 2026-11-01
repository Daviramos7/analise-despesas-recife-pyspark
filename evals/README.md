# Evals do agente

- `casos.yaml`: 30 casos (23 numéricos, 3 de texto, 4 recusas). O gabarito é SQL direto em `raw.*`.
- `rodar.py`: roda o agente, pontua e salva em `resultados/` (inclusive as rodadas que pioraram).
- Métricas: acerto, acerto do LLM sem guardrail, tool correta, respostas com número sem suporte
  nas tools (alucinação numérica) e guardrail acionado.

## Histórico (modelo `qwen2.5:7b` via Ollama, temperatura 0, RTX 3060)

O conjunto de casos é **o mesmo** em todas as rodadas, com uma exceção registrada: em
`desp_educacao_dezembro`, `despesas_orgaos` foi aceito como tool válida depois da rodada 1.

| # | Mudança | Prompt | Rep. | Acerto | Sem suporte | Arquivo |
|---|---|---|---:|---:|---:|---|
| 1 | baseline | v1 | 1 | 90,0% | 0 | `20261101-1336_*` |
| 2 | `ano` exposto nas tools + busca de credor + prompt maior | v2¹ | 1 | 76,7% | 1 | `20261101-1341_*` |
| 3a | A/B só do prompt, com a API da rodada 2 | v1 | 3 | 78,9% (76,7–80,0) | 1 | `20261101-1348_*` |
| 3b | idem | v2 | 3 | 76,7% (76,7–76,7) | 1 | `20261101-1350_*` |
| 4 | `ano` **fora** das tools + `anos_dos_dados` em toda resposta | v1 | 3 | 96,7% (96,7–96,7) | 0 | `20261101-1424_*` |
| 5 | + guardrail determinístico de ano | v1 | 3 | **100% (LLM sozinho: 96,7%)** | 0 | `20261101-1429_*` |

### Modelo na nuvem (Gemini) e ajuste do comparativo

| # | Modelo | Mudança | Rep. | Acerto | Sem guardrail | Sem suporte | Arquivo |
|---|---|---|---:|---:|---:|---:|---|
| 6 | gemini-3.5-flash-lite | 1ª rodada no Gemini (+ repasse da assinatura de raciocínio) | 1 | 93,3% | 93,3% | 0 | `20261101-1520_*` |
| 7 | gemini-3.5-flash-lite | descrição do `comparativo` avisa que os totais excluem intraorçamentárias | 1 | **100%** | **100%** | 0 | `20261101-1527_*` |
| 8 | qwen2.5:7b | mesma API da rodada 7 (checagem de regressão) | 1 | 96,7% | 93,3% | 0 | `20261101-1528_*` |

¹ Antes do versionamento de prompt, o JSON não registra a versão. O texto usado é o que hoje é o `v2`.

### O que cada rodada ensinou

- **1 → 2:** a busca por nome de credor e as descrições "órgão × credor" resolveram a Caixa, e
  o 404 para outro ano resolveu a recusa de 2022. Mas expor `ano` como parâmetro fez o modelo
  **chamar ano=2022 sozinho** depois de já ter o dado certo, e recusar 4 perguntas de receita.
  Também passou a recusar perguntas de 2023 **sem chamar nenhuma tool**.
- **3a × 3b:** o prompt não era a causa (v1 ≈ v2). Com temperatura 0, as rodadas são praticamente
  idênticas: o erro é sistemático, não é ruído.
- **4:** tirar `ano` das tools (a API continua aceitando o parâmetro, só fora do OpenAPI)
  recuperou tudo e manteve os ganhos. Sobrou um erro: pra "quanto a Saúde gastou **em 2022**", o
  modelo responde o valor de 2023, ignorando `anos_dos_dados`. O detector de números **não** pega
  esse caso, porque o valor existe.
- **5:** guardrail em código (`aplicar_guardrail_ano`). Se a pergunta cita um ano ausente dos
  `anos_dos_dados` devolvidos pelas tools, a resposta vira "Não tenho esse dado". O relatório
  separa o acerto com e sem guardrail.

- **6:** o Gemini errou 2 totais por usar `comparativo_receita_despesa`, que por padrão exclui
  operações intraorçamentárias e devolve valores menores. O número existia na API (0 sem
  suporte), mas o significado era outro, e a descrição da tool não avisava disso. Não foi
  alucinação: foi ambiguidade da API.
- **7:** a descrição passou a dizer "NÃO use para totais", e a resposta ganhou o campo
  `observacao`. O Gemini foi a 100% sem precisar do guardrail, e recusou 2022 sozinho.
- **8:** a mesma mudança custou 1 caso no qwen. Ele voltou a pedir "qual órgão?" em vez de
  consultar o total de março, e o erro acontece no primeiro turno, antes de qualquer tool. A
  decisão foi **aceitar o trade-off**: o Gemini é o modelo do app online, e seguir ajustando
  descrições contra os mesmos 30 casos seria otimizar para a prova.
- Em `20261101-1512_*` houve um HTTP 503 de sobrecarga do `gemini-3.8-flash`. O arquivo foi
  descartado por ser falha do provedor, não avaliação. Por isso o modelo usado é o Flash-Lite.

### Limites destes números

- As rodadas 6 a 8 têm **uma repetição só**. O Gemini na nuvem pode variar mais que o modelo
  local, e as 3 repetições ficaram pendentes por causa da cota diária gratuita.
- 30 casos escritos pelo próprio autor. O guardrail foi criado **depois** de ver o caso de 2022
  falhar, então esse caso não mede generalização. Casos novos devem vir do loop de feedback
  (`python -m orcamento.feedback`).
- Um modelo e uma máquina. Comparar com outro modelo, como o Groq `llama-3.3-70b-versatile`,
  exige só trocar o `.env`.
