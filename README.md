# 🏛️ Análise de Despesas Públicas do Recife — PySpark

> Pipeline ETL de Big Data para auditoria do orçamento municipal do Recife (2023), processando 127 mil registros com Apache Spark.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Daviramos7/analise-despesas-recife-pyspark/blob/main/analise.ipynb)

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![PySpark](https://img.shields.io/badge/PySpark-3.x-orange?style=for-the-badge&logo=apachespark&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Concluído-success?style=for-the-badge)

---

## ⚡ Performance

| Métrica | Resultado |
|---|---|
| Volume processado | **127.119 registros** |
| Tempo de execução (Wall Clock) | **10,25 segundos** |
| Tempo de CPU (Cluster) | **9,16 segundos** |
| Shuffle de dados (rede) | **0,00 MB** |
| Status | ✅ Paralelismo eficiente — CPU Time > Wall Clock |

> **0,00 MB de Shuffle** significa que toda a agregação foi resolvida localmente, sem tráfego de dados entre nós — otimização total de memória.

---

## 📈 Resultados da Auditoria (2023)

| # | Órgão | Destaque |
|---|---|---|
| 1 | Fundo Municipal de Saúde | **~R$ 1,66 bilhão** |
| 2 | Secretaria de Educação | ~R$ 1,56 bilhão |
| 3 | Infraestrutura Urbana | — |

**Total auditado: ~R$ 7,8 bilhões**

O orçamento é altamente concentrado nas áreas finalísticas (Saúde + Educação = ~42% do total), consistente com obrigações constitucionais do município.

---

## 🏗️ Arquitetura do Pipeline

```
Portal de Dados Abertos do Recife (HTTP)
              │
              ▼
     requests.get() → despesas_recife_2023.csv
              │
              ▼
     SparkSession local[*] (2g driver memory)
              │
              ▼
  ┌─────────── EXTRACT ───────────┐
  │  spark.read.csv()             │
  │  encoding=UTF-8, sep=";"      │
  │  127.119 registros            │
  └───────────────────────────────┘
              │
              ▼
  ┌─────────── TRANSFORM ─────────┐
  │  regexp_replace() — Regex     │
  │  "1.000,00" → 1000.00         │
  │  cast(DoubleType)             │
  │  df.cache() — otimização      │
  └───────────────────────────────┘
              │
              ▼
  ┌─────────── ANALYTICS ─────────┐
  │  agg(sum) — total liquidado   │
  │  groupBy + orderBy + limit    │
  │  toPandas() — só o Top 10     │
  └───────────────────────────────┘
              │
              ▼
     Matplotlib (barh) + Relatório
     métricas extraídas via Spark UI API
     (localhost:4040/api/v1/applications)
```

---

## 🛠️ Decisões Técnicas

**Tratamento de moeda brasileira com Regex**
O dataset usa formato `1.000,00` que o Spark lê como string. Solução: `regexp_replace` em duas passagens — remove o ponto de milhar, substitui vírgula decimal — antes do cast para `DoubleType`.

**`df.cache()` antes das agregações**
O DataFrame transformado é mantido em memória antes dos cálculos. Isso elimina releitura do CSV para cada operação — resultado direto: 0,00 MB de Shuffle.

**Métricas via Spark UI API**
O pipeline extrai automaticamente CPU Time e Shuffle Bytes da API REST do Spark (`localhost:4040`) para gerar o relatório de performance, sem depender de estimativas manuais.

**`toPandas()` apenas no resultado agregado**
Evita carregar os 127k registros brutos na memória do driver. O Spark faz toda a agregação distribuída e só traz o Top 10 para o Pandas — padrão de engenharia para workloads híbridos.

---

## 🚀 Como Executar

**Recomendado: Google Colab** (Java/Spark já disponíveis)

<<<<<<< HEAD
1. Clique no badge **Open in Colab** acima
2. Execute todas as células: `Runtime > Run all`

**Local:**
```bash
git clone https://github.com/Daviramos7/analise-despesas-recife-pyspark
cd analise-despesas-recife-pyspark

pip install pyspark pandas matplotlib requests

jupyter notebook analise.ipynb
```
=======
1.  Clone este repositório ou baixe o arquivo `.ipynb`.
2.  Abra o [Google Colab](https://colab.research.google.com/).
3.  Faça o upload do arquivo `analise.ipynb`.
4.  Execute todas as células (Runtime > Run all).
>>>>>>> 9213c5a85b10e3dd9f08f3326444a7cc58e47f74

---

## 📄 Licença

Copyright © 2026 por Davi Ramos Ferreira. Todos os Direitos Reservados.

---

**Desenvolvido com 💙 por [Davi Ramos Ferreira](https://github.com/Daviramos7)**
