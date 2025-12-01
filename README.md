# 📊 Análise de Despesas Públicas do Recife com PySpark

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![PySpark](https://img.shields.io/badge/PySpark-3.x-orange?style=for-the-badge&logo=apachespark&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Concluído-success?style=for-the-badge)

Este projeto consiste em um pipeline de **Engenharia de Dados** desenvolvido para extrair, limpar, transformar e analisar os dados de despesas orçamentárias da Prefeitura do Recife (exercício de 2023).

O objetivo principal foi aplicar técnicas de **Big Data** utilizando o framework **Apache Spark (PySpark)** para processar grandes volumes de dados públicos e gerar insights sobre a gestão municipal.

---

## 🚀 Funcionalidades e Pipeline (ETL)

O projeto segue o fluxo de ETL (Extract, Transform, Load) e Análise:

1.  **Extração (Extract):**
    * Ingestão automatizada de dados brutos (CSV) diretamente do [Portal de Dados Abertos do Recife](http://dados.recife.pe.gov.br/).
    * Utilização de comandos de sistema (`wget`) para garantia de download robusto.

2.  **Transformação e Limpeza (Transform):**
    * **Tratamento de Encoding:** Leitura forçada em `UTF-8` para correção de caracteres especiais (acentuação em nomes de órgãos).
    * **Conversão de Tipos:** Transformação de valores monetários no padrão brasileiro (ex: `1.000,00`) para formato numérico computacional (`DoubleType`) utilizando Expressões Regulares (`Regex`).

3.  **Análise e Visualização (Analytics):**
    * Cálculo de estatísticas descritivas (Soma total, Média por lançamento).
    * Filtragem de dados específicos (Fundo Municipal de Saúde).
    * Geração de Ranking (Top 10) dos órgãos com maior orçamento executado.
    * Visualização gráfica com **Matplotlib**.

---

## 📈 Principais Insights (2023)

A análise dos dados processados revelou que o orçamento municipal é fortemente concentrado em serviços essenciais à população:

* **💰 Total Liquidado:** ~R$ 7,8 Bilhões.
* **🏥 Maior Despesa:** O Fundo Municipal de Saúde lidera o ranking com gastos superiores a **R$ 1,6 Bilhão**.
* **🎓 Educação:** A Secretaria de Educação aparece em segundo lugar, seguida pela Infraestrutura Urbana.

---

## 🛠️ Tecnologias Utilizadas

* **Google Colab:** Ambiente de desenvolvimento em nuvem.
* **Python:** Linguagem base.
* **PySpark (Apache Spark):** Processamento distribuído de dados e manipulação de DataFrames.
* **Pandas:** Refinamento de tabelas para apresentação final.
* **Matplotlib:** Criação de gráficos para visualização de dados.

---

## 💻 Como Executar

Este projeto foi desenvolvido para rodar preferencialmente no **Google Colab**, pois realiza a instalação automática das dependências do Java/Spark.

1.  Clone este repositório ou baixe o arquivo `.ipynb`.
2.  Abra o [Google Colab](https://colab.research.google.com/).
3.  Faça o upload do arquivo `analise_despesas_recife.ipynb`.
4.  Execute todas as células (Runtime > Run all).

---

## 👨‍💻 Autor

Desenvolvido como parte de atividades práticas de Big Data e Engenharia de Dados.

* [Seu LinkedIn Aqui](Coloque o Link do seu perfil)
