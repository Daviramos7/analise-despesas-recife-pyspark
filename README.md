# 🏛️ Análise de Despesas Públicas do Recife — PySpark

> Pipeline ETL com Apache Spark para ingestão, tratamento e análise de despesas orçamentárias do Município do Recife em 2023.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Daviramos7/analise-despesas-recife-pyspark/blob/main/analise.ipynb)

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge\&logo=python\&logoColor=white)
![PySpark](https://img.shields.io/badge/PySpark-3.x-orange?style=for-the-badge\&logo=apachespark\&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge\&logo=pandas\&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-11557C?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Concluído-success?style=for-the-badge)

---

## 📌 Sobre o projeto

Este projeto implementa um pipeline de dados para analisar as despesas orçamentárias do Recife em 2023.

O fluxo utiliza PySpark para processar o conjunto completo de dados e transfere para o Pandas apenas os resultados já agregados que serão utilizados na visualização.

O pipeline executa automaticamente:

* download e validação do dataset;
* detecção de respostas HTML inválidas;
* detecção automática do separador do CSV;
* normalização dos nomes das colunas;
* limpeza de valores monetários brasileiros;
* processamento e agregações com PySpark;
* validações de qualidade dos dados;
* ranking dos órgãos por valor liquidado;
* geração de visualização em formato 16:9;
* exportação dos resultados em CSV, JSON, PNG e ZIP.

---

## 📊 Resultados da análise

Na execução com o dataset de 2023, foram encontrados:

| Métrica                           |               Resultado |
| --------------------------------- | ----------------------: |
| Registros processados             |             **127.119** |
| Valor liquidado                   | **R$ 7.803.361.234,91** |
| Percentual pago sobre o liquidado |              **94,05%** |

### Maiores órgãos por valor liquidado

Entre os maiores valores identificados estão:

|  # | Órgão                        |   Valor aproximado |
| -: | ---------------------------- | -----------------: |
|  1 | Secretaria de Saúde          | **R$ 1,67 bilhão** |
|  2 | Secretaria de Educação       | **R$ 1,56 bilhão** |
|  3 | Secretaria de Infraestrutura | **R$ 1,27 bilhão** |
|  4 | Encargos Gerais do Município | **R$ 810 milhões** |

Os valores são calculados diretamente a partir do dataset processado pelo pipeline.

---

## ⚡ Métricas de execução

A aplicação apresenta ao final de cada execução:

* quantidade de registros processados;
* tempo real de processamento no Spark;
* tamanho do arquivo de entrada;
* quantidade de partições do DataFrame;
* quantidade de órgãos ausentes;
* quantidade de valores monetários inválidos;
* versão do Apache Spark utilizada.

> O tempo de execução pode variar de acordo com a máquina, disponibilidade do Google Colab, conexão com a internet e versão do Spark. Por isso, o projeto não utiliza um tempo fixo como resultado oficial.

---

## 🏗️ Arquitetura do pipeline

```text
Portal de Dados Abertos do Recife
                 │
                 ▼
     Download com requests e retry
                 │
                 ├── Validação HTTP
                 ├── Detecção de HTML
                 ├── Validação do CSV
                 └── Upload manual no Colab como fallback
                 │
                 ▼
          Apache Spark
                 │
       ┌─────────┴─────────┐
       │      EXTRACT      │
       │                   │
       │ spark.read.csv()  │
       │ separador         │
       │ detectado         │
       │ automaticamente   │
       └─────────┬─────────┘
                 │
                 ▼
       ┌───────────────────┐
       │     TRANSFORM     │
       │                   │
       │ normalização das  │
       │ colunas           │
       │                   │
       │ limpeza de moeda  │
       │ brasileira        │
       │                   │
       │ conversão para    │
       │ DoubleType        │
       │                   │
       │ MEMORY_AND_DISK   │
       └─────────┬─────────┘
                 │
                 ▼
       ┌───────────────────┐
       │     ANALYTICS     │
       │                   │
       │ totais financeiros│
       │ validações        │
       │ groupBy + sum     │
       │ ranking Top 10    │
       └─────────┬─────────┘
                 │
                 ▼
       Pandas + Matplotlib
                 │
                 ▼
         CSV · JSON · PNG · ZIP
```

---

## 🛠️ Decisões técnicas

### Validação do download

O portal pode retornar uma página HTML, redirecionamento ou erro temporário no lugar do CSV.

Antes de iniciar o processamento, o pipeline verifica:

* status da resposta HTTP;
* tipo do conteúdo retornado;
* primeiros bytes do arquivo;
* tamanho mínimo;
* estrutura do cabeçalho;
* presença de separadores válidos.

Isso impede que uma página iniciada por `<!DOCTYPE html>` seja interpretada pelo Spark como um arquivo CSV.

### Fallback de upload no Google Colab

Caso o Portal de Dados Abertos recuse a conexão do Colab, o notebook abre automaticamente uma janela para envio manual do CSV.

Depois do upload, o arquivo passa pelas mesmas validações e o pipeline continua normalmente.

### Tratamento da moeda brasileira

Os valores monetários do dataset podem utilizar o padrão brasileiro:

```text
1.234.567,89
```

O pipeline:

1. remove espaços e símbolos monetários;
2. remove os pontos de milhar;
3. substitui a vírgula decimal por ponto;
4. converte o resultado para `DoubleType`.

Exemplo:

```text
1.234.567,89 → 1234567.89
```

### Normalização das colunas

Os nomes das colunas são convertidos para um padrão consistente:

```text
Valor Liquidado → valor_liquidado
Órgão Nome → orgao_nome
```

Também são removidos:

* acentos;
* espaços;
* caracteres especiais;
* duplicações de separadores.

Antes da análise, o código confirma a existência das colunas obrigatórias.

### Persistência com `MEMORY_AND_DISK`

O DataFrame transformado é persistido com:

```python
StorageLevel.MEMORY_AND_DISK
```

O Spark utiliza memória sempre que possível e pode utilizar disco caso o conjunto de dados não caiba completamente na memória disponível.

### Conversão controlada para Pandas

Os 127 mil registros não são enviados diretamente para o Pandas.

O PySpark executa:

* limpeza;
* filtros;
* agrupamentos;
* somas;
* ordenação;
* seleção dos maiores órgãos.

Somente o resultado agregado do Top 10 é convertido para Pandas para geração da visualização.

---

## 📁 Arquivos gerados

Ao final da execução, o pipeline cria:

```text
saida_auditoria_recife_2023/
├── 04_dashboard_portfolio.png
├── resumo_execucao.json
└── top_10_orgaos_por_valor_liquidado.csv
```

Também é gerado um arquivo compactado:

```text
saida_auditoria_recife_2023.zip
```

### Dashboard

O arquivo:

```text
04_dashboard_portfolio.png
```

é gerado em proporção 16:9 e apresenta:

* quantidade de registros processados;
* valor total liquidado;
* percentual pago sobre o liquidado;
* maiores órgãos por valor liquidado.

---

## 🚀 Como executar

### Google Colab

1. Clique no badge **Open in Colab** no início deste README.
2. No Colab, selecione:

```text
Ambiente de execução → Executar tudo
```

3. Aguarde o download e o processamento do dataset.
4. Caso o download automático falhe, selecione o CSV quando a janela de upload for exibida.
5. Acesse a pasta de resultados:

```text
/content/saida_auditoria_recife_2023/
```

O notebook instala automaticamente as dependências ausentes.

---

### Execução local

Clone o repositório:

```bash
git clone https://github.com/Daviramos7/analise-despesas-recife-pyspark.git
cd analise-despesas-recife-pyspark
```

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

No Windows:

```bash
.venv\Scripts\activate
```

No Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install pyspark pandas matplotlib requests
```

Execute o notebook:

```bash
jupyter notebook analise.ipynb
```

Ou execute a versão Python, caso ela esteja presente no repositório:

```bash
python recife_public_audit_2023.py
```

> Para execução local com PySpark, é necessário ter uma versão compatível do Java instalada.

---

## 🧰 Tecnologias utilizadas

* Python
* Apache Spark
* PySpark
* Spark SQL
* Pandas
* Matplotlib
* Requests
* Google Colab
* Portal de Dados Abertos do Recife

---

## 📚 Conceitos aplicados

* ETL;
* processamento distribuído;
* limpeza e normalização de dados;
* tipagem de dados;
* agregações;
* persistência de DataFrames;
* validação de qualidade;
* tratamento de falhas de integração;
* visualização de dados;
* exportação de resultados;
* processamento híbrido com Spark e Pandas.

---

## ⚠️ Observações

* Os dados utilizados são públicos e disponibilizados pelo Portal de Dados Abertos da Prefeitura do Recife.
* Os resultados representam o processamento do dataset de despesas orçamentárias de 2023.
* O tempo de execução pode variar entre ambientes.
* A indisponibilidade temporária do portal não representa falha do pipeline.
* O notebook possui fallback para upload manual do dataset no Google Colab.

---

## 📄 Licença

Copyright © 2026 Davi Ramos Ferreira.

Todos os direitos reservados.

---

Desenvolvido por [Davi Ramos Ferreira](https://github.com/Daviramos7)
