## 1. INTRODUÇÃO E METODOLOGIA DE ENSAIO
O presente relatório apresenta o comparativo de desempenho entre duas abordagens arquiteturais de consumo de dados para painéis gerenciais construídos em Streamlit. A base de dados utilizada provém dos microdados contendo mais de 5 milhões de registros sobre notificações e diagnósticos de COVID-19 do Estado do Espírito Santo.
Para garantir a equidade dos testes o ensaio foi dividido em dois cenários:

* Cenário A (Abordagem Flat / Arquivo): Execução do script app_csv.py, realizando a leitura de uma amostra de 500.000 registros do arquivo MICRODADOS.csv via biblioteca Pandas.
* Cenário B (Abordagem SGBD): Execução do script app_dw.py, realizando consultas SQL direcionadas a um Data Warehouse PostgreSQL modelado em Esquema Estrela (Star Schema) com a totalidade do dataset persistido na tabela dw.fato_notificacao_covid.

Todas as métricas de tempo foram capturadas internamente via instrução nativa time.perf_counter().

## 2. TECNOLOGIAS UTILIZADAS, PRÉ-REQUISITOS E DEPENDÊNCIAS
# 2.1.Stack Tecnológica

* Linguagem de Programação: Python, atuando como a ferramenta orquestradora do pipeline de ETL e da renderização das interfaces visuais.
* SGBD Analítico: PostgreSQL, responsável pelo armazenamento definitivo do Data Warehouse, dos schemas analíticos e pelo processamento de consultas OLAP.
* Framework Web de Visualização: Streamlit, utilizado para a construção interativa do dashboard e exibição de métricas.

# 2.3. Dependências e Instruções de Instalação (Terminal)
As bibliotecas específicas do Python necessárias para a plena execução do pipeline de ETL e do dashboard compreendem:
pandas: Essencial para a leitura, manipulação e transformação de estruturas de dados.

* Matplotlib e seaborn: Utilizadas na renderização dos gráficos de série temporal, barras e mapas de calor.
* Streamlit: Encarregada de renderizar toda a camada de interface e de interações com o usuário.
* Sqlalchemy e psycopg2-binary: Motores de conexão e drivers que permitem ao Python disparar comandos SQL nativos e interagir com o PostgreSQL.

### 3.RESULTADOS

A implementação do Data Warehouse utilizando PostgreSQL mostrou-se uma solução mais adequada para o tratamento e análise dos mais de 5 milhões de registros do conjunto de dados estudado. Os resultados obtidos evidenciaram uma melhora significativa no desempenho das consultas, com redução expressiva do tempo de resposta em comparação à abordagem baseada em arquivos CSV.

Além do ganho de performance, a modelagem dimensional permitiu uma melhor organização das informações, simplificando consultas analíticas e aumentando a qualidade dos dados por meio de regras de integridade e padronização.

Embora o uso de arquivos CSV seja útil em análises exploratórias e projetos de menor porte, o Data Warehouse oferece maior escalabilidade, segurança, governança e capacidade de expansão. Portanto, para cenários que exigem análises frequentes, grandes volumes de dados e suporte à tomada de decisão, a arquitetura baseada em Data Warehouse apresenta-se como a alternativa mais eficiente e confiável.











