# 🏛️ Receitas e Despesas Públicas do Recife: dados prontos para agentes de IA

[![ci](https://github.com/Daviramos7/orcamento-publico-recife/actions/workflows/ci.yml/badge.svg)](https://github.com/Daviramos7/orcamento-publico-recife/actions/workflows/ci.yml)

**🌐 App online: [orcamento-recife.streamlit.app](https://orcamento-recife.streamlit.app)**: pergunte ao agente ou explore o painel.

Pipeline de dados (PySpark + dbt + PostgreSQL), uma **API FastAPI** desenhada para ser lida por
um LLM e um **agente com tool calling** que responde perguntas em português sobre o orçamento do
Recife em 2023. O agente cita só números que vieram da API, e isso é **medido por evals**.

> **Status:** funcionando de ponta a ponta. Em 30 casos de avaliação: **Gemini Flash-Lite (nuvem,
> grátis) 100%** e **qwen2.5:7b (local) 96,7%**, sem nenhum número inventado.
> [Detalhes e limites](#-resultados-dos-evals).

---

## 🎯 O problema

Os dados de orçamento do Recife são públicos, mas responder "quanto a prefeitura arrecadou de IPTU"
ou "a despesa superou a receita em algum mês?" exige baixar CSVs de 80 MB, entender a
classificação orçamentária e somar do jeito certo (empenhado, liquidado ou pago? com ou sem
operações intraorçamentárias?).

Um LLM sozinho **inventa** esses números. Este projeto dá a ele uma API confiável e mede quanto
ele acerta e quanto ele alucina.

## 🏗️ Arquitetura

```text
Portal de Dados Abertos (CSV despesas + receitas 2023)
        │
        ▼
 PySpark ── limpeza testada (valores BR, trim, tipos) ──► Parquet particionado por mês
        │
        ▼  COPY idempotente (TRUNCATE + COPY numa transação)
 PostgreSQL  raw.despesas · raw.receitas
        │
        ▼  dbt: staging → star schema + 86 testes de dados
 marts: fato_despesa_movimento · fato_receita_movimento
        dim_unidade · dim_mes · dim_fonte_recurso   (conformadas)
        dim_credor · dim_classif_economica · dim_classif_funcional · dim_classif_receita
        │
        ▼
 FastAPI  10 endpoints tipados (Pydantic), com descrições escritas para o LLM
        │  OpenAPI
        ▼
 Agente  tools geradas do OpenAPI · loop de tool calling no SDK openai · temperatura 0
        │        ├─► Ollama (local) ou Gemini / Groq / OpenAI (por variável de ambiente)
        │        └─► checagem de grounding: todo número citado precisa estar na saída de uma tool
        ▼
 Evals (30 casos, gabarito via SQL direto no raw)   ·   Feedback 👍/👎 → app.interacoes
```

## 🚀 Como rodar

### 1. Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/), instalado e **aberto**.
- Para o agente, uma das opções:
  - **[Ollama](https://ollama.com/download)** (grátis, local; GPU recomendada): `ollama pull qwen2.5:7b`
  - **Google Gemini** (grátis, na nuvem, sem GPU, sem cartão): chave em [aistudio.google.com](https://aistudio.google.com)
  - **Groq** (grátis, na nuvem): chave em [console.groq.com](https://console.groq.com)

### 2. Código e dados

```bash
git clone https://github.com/Daviramos7/orcamento-publico-recife.git
cd orcamento-publico-recife
```

Os CSVs **não** ficam no repositório. Baixe no
[Portal de Dados Abertos do Recife](https://dados.recife.pe.gov.br) (busque "despesas
orçamentárias" e "receitas orçamentárias", ano **2023**) e salve assim:

```text
data/raw/despesas-orcamentarias-2023.csv
data/raw/receitas-orcamentarias-2023.csv
```

### 3. Subir pipeline + API (um comando)

```bash
docker compose up --build api
```

Isso roda PySpark → Postgres → dbt (com os testes de dados) e sobe a API. Na primeira vez leva
uns 2 a 3 minutos. Está pronto quando aparecer `Uvicorn running on http://0.0.0.0:8000`.

**Teste no navegador:** <http://localhost:8000/docs>. Clique num endpoint, depois em "Try it out" e "Execute".

### 4. Usar (num segundo terminal, com a API no ar)

| Quero… | Comando |
|---|---|
| Conversar com o agente (e dar 👍/👎) | `docker compose run --rm --build agente` |
| Rodar os 30 casos de eval | `docker compose run --rm --build --no-deps evals` |
| Medir variância (3 rodadas) | `docker compose run --rm --build --no-deps evals python evals/rodar.py --repeticoes 3` |
| Rodar os testes | `docker compose run --rm --build tests` |
| Exportar os 👎 para candidatos de eval | `docker compose run --rm --no-deps agente python -m orcamento.feedback` |

### 5. Trocar de LLM (opcional)

```bash
cp .env.example .env     # no Windows: copy .env.example .env
```

Edite o `.env` e deixe **só uma** opção descomentada: 1 = Ollama (padrão), 2 = Gemini, 3 = Groq.
**O `.env` está no `.gitignore`, então a chave nunca vai pro repositório.**

### Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| Testes rodam menos casos do que o esperado | o `run` reaproveitou uma imagem antiga | use `--build` nos comandos `run` |
| Agente/evals: erro de conexão com o LLM | Ollama fechado ou escutando só em localhost | abra o Ollama; no Windows: `setx OLLAMA_HOST 0.0.0.0` e reinicie o Ollama |
| `pipeline` falha logo no início | CSVs ausentes ou com nome diferente | confira os nomes em `data/raw/` |
| Mudou código da API e nada mudou | o container da API é antigo | `docker compose up -d --build --no-deps api` |
| Quer começar do zero | volume do Postgres com dados antigos | `docker compose down -v` |

## 🌐 App online (Streamlit)

**Acesse: <https://orcamento-recife.streamlit.app>**

Painel com os números do orçamento e um chat com o agente, que mostra **quais consultas à API
fez** e se **todos os números foram conferidos**. Tudo em planos gratuitos:

```text
Visitante ─► Streamlit Community Cloud ── app + API FastAPI + agente (no mesmo processo)
                 ├─► Supabase (Postgres): marts + feedback 👍/👎   [usuário app_web: só leitura + feedback]
                 └─► Google Gemini (gemini-3.5-flash-lite, plano gratuito)
```

- **O app é só mais um cliente da API.** O painel e o agente chamam os mesmos endpoints
  (via `TestClient`, sem servidor separado), então os números da tela são os que os evals avaliam.
- **Segurança:** o app usa o usuário `app_web`, que só lê os marts e só grava feedback.
  Ver [`deploy/supabase_setup.sql`](deploy/supabase_setup.sql).
- **Proteção da cota do LLM:** limite **global** de 200 perguntas por dia (soma todos os
  visitantes e sobrevive a recarregar a página; contado em `app.interacoes`, e se o banco não
  responder o chat bloqueia em vez de gastar cota às cegas), 15 por sessão, 5 s entre perguntas,
  300 caracteres por pergunta e teto de 1024 tokens por resposta (`LLM_MAX_TOKENS`). Ajustável
  por `LIMITE_DIARIO_PERGUNTAS`.
- **Limites do plano gratuito:** o Streamlit dorme após 12 h sem
  visita (acorda num clique, ~30 s); o Supabase pausaria após 7 dias, e o workflow
  [`keepalive.yml`](.github/workflows/keepalive.yml) evita isso. Se o Gemini estiver
  sobrecarregado (HTTP 503), o app avisa em vez de travar.
- **Rodar o app local:** `docker compose up --build app` → <http://localhost:8501>

## 🔌 API

| Endpoint | Responde |
|---|---|
| `GET /metadados` | o que existe **e o que não existe** nos dados (anos, granularidade, limitações) |
| `GET /orgaos?busca=` | código do órgão a partir do nome (sem precisar de acento) |
| `GET /despesas/orgaos` | total por órgão no período, ranking (`rank()`), % do total |
| `GET /despesas/evolucao-mensal` | mês a mês com variação (`lag()`) e acumulado (`sum() over`) |
| `GET /despesas/credores/ranking` | maiores credores, consolidados por nome |
| `GET /despesas/funcoes` | gasto por área (Saúde, Educação, Urbanismo…) |
| `GET /receitas/origens` | arrecadado × previsto por origem e % de execução |
| `GET /receitas/itens?busca=IPTU` | receita específica, com siglas (IPTU, ISS, FPM, FUNDEB…) |
| `GET /receitas/evolucao-mensal` | arrecadação mês a mês com variação e acumulado |
| `GET /comparativo/receita-despesa` | receita × despesa e saldo, sem intraorçamentárias por padrão |

Medidas de despesa são whitelisted (`empenhado | liquidado | pago`) e injetadas com
`psycopg.sql.Identifier`, então não tem SQL injection por parâmetro.

## 🤖 Agente

- **Sem framework.** O loop inteiro está em [`src/orcamento/agente/agente.py`](src/orcamento/agente/agente.py)
  e usa o SDK `openai` apontando pra qualquer endpoint compatível (Ollama, Gemini, Groq, OpenAI).
- **Tools geradas do OpenAPI** da própria API. A descrição que o LLM lê é a mesma do `/docs`,
  então existe uma fonte de contrato só.
- **Regras no prompt (versionado: `PROMPT_VERSAO`):** só citar números das tools, nunca calcular
  por conta própria e dizer "Não tenho esse dado" quando não houver dado. Limite de 6
  iterações. Temperatura 0.
- **Guardrail de ano, em código:** se a pergunta cita um ano que não aparece no
  `anos_dos_dados` devolvido pelas tools, a resposta é substituída por "Não tenho esse dado".
- **Checagem de grounding fora do LLM** ([`verificacao.py`](src/orcamento/agente/verificacao.py)):
  extrai todo número da resposta (formato BR, "1,67 bilhão"…) e confere se ele aparece em alguma
  saída de tool, aceitando só o arredondamento coerente com o que foi escrito.

## 📏 Evals

[`evals/casos.yaml`](evals/casos.yaml) tem **30 casos**: 17 de despesa, 9 de receita/comparativo
e **4 que o agente deve recusar** (outro ano, bairro, salário individual, valor por dia).

- **O gabarito é SQL direto em `raw.*`**, sem passar pela API nem pelo dbt. Se a API tiver bug,
  o gabarito não herda o bug. Foi assim que um eval encontrou o problema dos credores com vários
  códigos (ver [`docs/qualidade.md`](docs/qualidade.md)).
- **Teste de cobertura sem LLM:** pra cada caso respondível, uma chamada de referência prova que
  a resposta está na saída da API (25/25). Então, se um eval falha, o problema é do agente.
- **Métricas por caso:** acerto, tool correta, **números citados sem suporte** (detector de
  alucinação) e iterações.

## 📊 Resultados dos evals

Mesmos 30 casos, temperatura 0, mesma API (versão atual):

| Modelo | Onde roda | Rep. | Acerto | LLM sem guardrail | Tool correta | Nº sem suporte |
|---|---|---:|---:|---:|---:|---:|
| `gemini-3.5-flash-lite` | nuvem, plano gratuito | 1 | **100%** | **100%** | 100% | 0 |
| `qwen2.5:7b` | local (Ollama, RTX 3060) | 1 | **96,7%** | 93,3% | 96,7% | 0 |

Em nenhuma rodada o agente citou número que não veio da API.

O caminho até aqui inclui uma **regressão para 76,7%** (causada por expor o parâmetro `ano` nas
tools), um A/B de prompt, um guardrail determinístico e um **trade-off aceito**: a correção que
levou o Gemini a 100% custou 1 caso no qwen. Está tudo em [`evals/README.md`](evals/README.md),
com o JSON de cada rodada em `evals/resultados/`.

> Esses números valem para **estes 30 casos**, escritos pelo autor, e várias correções foram
> feitas depois de ver o erro. Não é uma medida de confiabilidade geral. As rodadas finais têm
> uma repetição só.

## 🔁 Feedback

O CLI do agente pede 👍/👎 e grava em `app.interacoes`: pergunta, tools e argumentos, resposta,
números sem suporte e voto. `python -m orcamento.feedback` exporta os 👎 como **rascunho** em
`evals/candidatos.yaml`. Eles **não** viram caso de eval automaticamente: alguém escreve o
`gabarito_sql` e confere, porque gabarito gerado pelo sistema avaliado não prova nada.

## 🧪 Testes

| Camada | O quê | Onde |
|---|---|---|
| Limpeza | valores BR, trim, tipos, receitas | `tests/test_limpeza.py` (PySpark) |
| Dados | not_null, unique, chaves compostas, relacionamentos, reconciliação fato × staging, regras de negócio | `dbt/` (86 testes) |
| API | valores calculados à mão num mini star schema, 404 de ano, busca | `tests/test_api.py` |
| Agente | loop com LLM falso, tools do OpenAPI, detecção de número inventado, guardrail | `tests/test_agente.py` |
| Evals | integridade dos casos, pontuação, cobertura da API no dado real | `tests/test_avaliacao.py`, `tests/test_cobertura_evals.py` |
| Feedback | gravação e exportação de 👎 | `tests/test_feedback.py` |

O CI (GitHub Actions) roda o pytest com Postgres a cada push. Os testes que dependem dos CSVs
reais são pulados lá, porque os dados não vão pro repositório.

## ⚠️ Limitações conhecidas

- **Só 2023.** O agente deve recusar outros anos, e isso é testado nos evals.
- **Granularidade mensal.** Não existe valor por dia.
- **Dado oficial com inconsistências** em 6 empenhos, monitoradas como WARN
  ([`docs/qualidade.md`](docs/qualidade.md)).
- **Credores consolidados por nome:** duas empresas diferentes com razão social idêntica seriam
  somadas. Não foi encontrado caso assim, mas também não existe CNPJ no dado pra provar.
- **O modelo de 7B ignora metadados do contexto.** Ele respondeu com valor de 2023 uma pergunta
  sobre 2022, mesmo com `anos_dos_dados: [2023]` na resposta. Por isso o guardrail é em código.
  Outras alucinações de contexto, como confundir medidas, não têm guardrail.
- **Em `PROMPT_VERSAO=v2`,** a regra sobre o parâmetro `ano` ficou obsoleta, porque o parâmetro saiu
  das tools. O v2 é mantido só como registro do experimento. O padrão é o v1.
- **O download dos CSVs é manual**, porque o portal bloqueia acesso automatizado.

## 📚 Documentação

- [`docs/schema.md`](docs/schema.md): camadas, grão, medidas e dimensões conformadas
- [`docs/qualidade.md`](docs/qualidade.md): achados de qualidade e decisões
- [`docs/v1-notebook.md`](docs/v1-notebook.md): README original da v1

## 🗂️ v1: notebook no Colab (métricas originais, preservadas)

A primeira versão era um notebook PySpark no Colab ([`analise.ipynb`](analise.ipynb)). Métricas
reportadas **por aquela versão**, mantidas como estavam:

| Métrica | Resultado (v1) |
| --- | ---: |
| Registros processados | **127.119** |
| Valor liquidado | **R$ 7.803.361.234,91** |
| Percentual pago sobre o liquidado | **94,05%** |

O ranking de órgãos da v1 agrupava por nome. A v2 agrupa por código de órgão, por isso os valores
podem diferir levemente. Os números da v2 vêm da API e dos evals, e não substituem os da tabela
acima.

---

Desenvolvido por [Davi Ramos Ferreira](https://github.com/Daviramos7)
