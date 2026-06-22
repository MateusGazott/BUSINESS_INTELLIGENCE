#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIPELINE DE ETL: Carga da Staging para as Dimensões e Fato do DW COVID-19
Disciplina: Business Intelligence — Prof. Otávio Lube
"""

import os
import sys
import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Configuração do Logging para fins de auditoria exigidos na C3
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

DB_URL = os.getenv("DW_COVID_URL", "postgresql://postgres:postgres@localhost:5432/dw_covid")
CSV_PATH = "MICRODADOS.csv"
AMOSTRA = 500_000

def get_engine():
    return create_engine(DB_URL)

def popular_dim_tempo(engine):
    """Gera e popula de forma determinística a dimensão de tempo (2020 a 2026)"""
    logging.info("Iniciando povoamento da dim_tempo...")
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2026, 12, 31)
    
    dates = []
    curr = start_date
    while curr <= end_date:
        sk_tempo = int(curr.strftime("%Y%m%d"))
        dates.append({
            "sk_tempo": sk_tempo,
            "data": curr.date(),
            "ano": curr.year,
            "mes": curr.month,
            "ano_mes": curr.strftime("%Y-%m")
        })
        curr += timedelta(days=1)
        
    df_tempo = pd.DataFrame(dates)
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            df_tempo.to_sql("dim_tempo", schema="dw", con=conn, if_exists="append", index=False, method="multi")
            trans.commit()
            logging.info(f"dim_tempo populada com sucesso! {len(df_tempo)} dias inseridos.")
        except Exception as e:
            trans.rollback()
            logging.warning(f"Aviso ao inserir dim_tempo (pode já estar populada): {e}")

def mapear_faixa_etaria(idade_str):
    """Agrupa idades nas faixas idênticas às usadas na pirâmide do dashboard"""
    try:
        idade = int(float(idade_str))
    except:
        return "DESCONHECIDO"
    
    if idade < 10: return "0-9"
    elif idade < 20: return "10-19"
    elif idade < 30: return "20-29"
    elif idade < 40: return "30-39"
    elif idade < 50: return "40-49"
    elif idade < 60: return "50-59"
    elif idade < 70: return "60-69"
    elif idade < 80: return "70-79"
    else: return "80+"

def executar_pipeline():
    t_inicio = time.perf_counter()
    engine = get_engine()
    
    # 1. Garantir dim_tempo populada antes de tudo
    popular_dim_tempo(engine)
    
    # 2. Extração (Extract) do arquivo CSV local
    logging.info(f"Lendo as primeiras {AMOSTRA} linhas de {CSV_PATH}...")
    if not os.path.exists(CSV_PATH):
        logging.error(f"Arquivo {CSV_PATH} não encontrado na raiz!")
        return
        
    df_raw = pd.read_csv(
        CSV_PATH,
        encoding="ISO-8859-1",
        sep=";",
        nrows=AMOSTRA,
        low_memory=False,
        dtype=str
    )
    
    # Limpeza básica de colunas textuais nulas ou vazias
    for col in df_raw.columns:
        df_raw[col] = df_raw[col].fillna("DESCONHECIDO").str.strip()

    # Carga na tabela de staging
    logging.info("Limpando e populando tabela stg_microdados...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE dw.stg_microdados;"))
        df_raw.to_sql("stg_microdados", schema="dw", con=conn, if_exists="append", index=False, method="multi")
    
    # 3. Transformação e Carga das Dimensões (Transform & Load)
    logging.info("Processando dimensões multidimensionais...")
    
    with engine.connect() as conn:
        # Dimensão Localidade
        conn.execute(text("""
            INSERT INTO dw.dim_localidade (municipio)
            SELECT DISTINCT Municipio FROM dw.stg_microdados
            WHERE Municipio IS NOT NULL AND Municipio <> 'DESCONHECIDO'
            ON CONFLICT (municipio) DO NOTHING;
        """))
        
        # Dimensão Comorbidade
        conn.execute(text("""
            INSERT INTO dw.dim_comorbidade (cardio, diabetes, obesidade, pulmao, tabagismo, renal)
            SELECT DISTINCT 
                ComorbidadeCardio, ComorbidadeDiabetes, ComorbidadeObesidade, 
                ComorbidadePulmao, ComorbidadeTabagismo, ComorbidadeRenal
            FROM dw.stg_microdados
            ON CONFLICT (cardio, diabetes, obesidade, pulmao, tabagismo, renal) DO NOTHING;
        """))
    
    # Dimensão Perfil Paciente (Requer cálculo python para mapeamento de faixas)
    logging.info("Processando dim_perfil_paciente...")
    df_perfil = pd.DataFrame()
    df_perfil["sexo"] = df_raw["Sexo"]
    df_perfil["faixa_etaria"] = df_raw["IdadeNaDataNotificacao"].apply(mapear_faixa_etaria)
    df_perfil = df_perfil.drop_duplicates()
    
    with engine.connect() as conn:
        for _, row in df_perfil.iterrows():
            conn.execute(text("""
                INSERT INTO dw.dim_perfil_paciente (faixa_etaria, sexo)
                VALUES (:faixa, :sexo) ON CONFLICT (faixa_etaria, sexo) DO NOTHING;
            """), {"faixa": row["faixa_etaria"], "sexo": row["sexo"]})

    # 4. Construção e Carga da Tabela Fato
    logging.info("Limpando e processando tabela fato_notificacao_covid...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE dw.fato_notificacao_covid;"))
        
        # Query OLAP de inserção em Massa cruzando Staging com Dimensões
        query_fato = """
            INSERT INTO dw.fato_notificacao_covid 
                (sk_data_notificacao, sk_local, sk_perfil, sk_como, qtd_notificacao, flag_confirmado, flag_obito_covid)
            SELECT 
                COALESCE(t.sk_tempo, -1) as sk_data_notificacao,
                COALESCE(l.sk_local, -1) as sk_local,
                COALESCE(p.sk_perfil, -1) as sk_perfil,
                COALESCE(c.sk_como, -1) as sk_como,
                1 as qtd_notificacao,
                CASE WHEN stg.Classificacao = 'Confirmados' THEN 1 ELSE 0 END as flag_confirmado,
                CASE WHEN stg.Evolucao = 'Óbito pelo COVID-19' THEN 1 ELSE 0 END as flag_obito_covid
            FROM dw.stg_microdados stg
            LEFT JOIN dw.dim_tempo t 
                ON t.data = TO_DATE(stg.DataNotificacao, 'DD/MM/YYYY')
            LEFT JOIN dw.dim_localidade l 
                ON l.municipio = stg.Municipio
            LEFT JOIN dw.dim_comorbidade c 
                ON c.cardio = stg.ComorbidadeCardio 
               AND c.diabetes = stg.ComorbidadeDiabetes
               AND c.obesidade = stg.ComorbidadeObesidade
               AND c.pulmao = stg.ComorbidadePulmao
               AND c.tabagismo = stg.ComorbidadeTabagismo
               AND c.renal = stg.ComorbidadeRenal
            LEFT JOIN dw.dim_perfil_paciente p 
                ON p.sexo = stg.Sexo 
               AND p.faixa_etaria = CASE 
                    WHEN stg.IdadeNaDataNotificacao ~ '^[0-9]+$' THEN
                        CASE 
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 10 THEN '0-9'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 20 THEN '10-19'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 30 THEN '20-29'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 40 THEN '30-39'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 50 THEN '40-49'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 60 THEN '50-59'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 70 THEN '60-69'
                            WHEN CAST(stg.IdadeNaDataNotificacao AS INT) < 80 THEN '70-79'
                            ELSE '80+'
                        END
                    ELSE 'DESCONHECIDO'
               END;
        """
        conn.execute(text(query_fato))
        
    t_total = time.perf_counter() - t_inicio
    logging.info(f"✨ Processo de ETL concluído com sucesso em {t_total:.2f} segundos!")

if __name__ == "__main__":
    executar_pipeline()