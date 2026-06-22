import os
import time
import warnings
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="COVID-19 ES — Dashboard DW",
    page_icon="🦠",
    layout="wide",
)

DB_URL = os.getenv("DW_COVID_URL", "postgresql://postgres:postgres@localhost:5432/dw_covid")

@st.cache_resource
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)

# Mapeamento das queries SQL OLAP otimizadas
SQL_SERIE_TEMPORAL = """
SELECT t.ano_mes, SUM(f.qtd_notificacao) AS notificacoes
FROM dw.fato_notificacao_covid f
JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_data_notificacao
WHERE t.sk_tempo > 0
  {filtro_ano}
GROUP BY t.ano_mes
ORDER BY t.ano_mes;
"""

SQL_HEATMAP = """
SELECT l.municipio, t.ano::text AS ano, SUM(f.qtd_notificacao) AS notificacoes
FROM dw.fato_notificacao_covid f
JOIN dw.dim_localidade l ON l.sk_local = f.sk_local
JOIN dw.dim_tempo      t ON t.sk_tempo = f.sk_data_notificacao
WHERE t.sk_tempo > 0
  {filtro_ano}
GROUP BY l.municipio, t.ano
ORDER BY notificacoes DESC
LIMIT 10;
"""

SQL_PIRAMIDE = """
SELECT p.faixa_etaria, p.sexo, COUNT(*) AS obitos
FROM dw.fato_notificacao_covid f
JOIN dw.dim_perfil_paciente p ON p.sk_perfil = f.sk_perfil
JOIN dw.dim_tempo           t ON t.sk_tempo  = f.sk_data_notificacao
WHERE f.flag_obito_covid = 1
  {filtro_ano}
GROUP BY p.faixa_etaria, p.sexo;
"""

SQL_COMORBIDADE = """
SELECT 
    SUM(CASE WHEN c.cardio = 'Sim' THEN 1 ELSE 0 END) AS "Cardiovascular",
    SUM(CASE WHEN c.diabetes = 'Sim' THEN 1 ELSE 0 END) AS "Diabetes",
    SUM(CASE WHEN c.obesidade = 'Sim' THEN 1 ELSE 0 END) AS "Obesidade",
    SUM(CASE WHEN c.pulmao = 'Sim' THEN 1 ELSE 0 END) AS "Pulmonar",
    SUM(CASE WHEN c.tabagismo = 'Sim' THEN 1 ELSE 0 END) AS "Tabagismo",
    SUM(CASE WHEN c.renal = 'Sim' THEN 1 ELSE 0 END) AS "Renal"
FROM dw.fato_notificacao_covid f
JOIN dw.dim_comorbidade c ON c.sk_como = f.sk_como
JOIN dw.dim_tempo        t ON t.sk_tempo = f.sk_data_notificacao
WHERE f.flag_obito_covid = 1
  {filtro_ano};
"""

def query(engine, sql_text):
    t0 = time.perf_counter()
    with engine.connect() as conn:
        df = pd.read_sql(text(sql_text), conn)
    return df, time.perf_counter() - t0

engine = get_engine()

st.title("🦠 Painel Analítico COVID-19 ES (Versão Data Warehouse)")
st.sidebar.header("Filtros do Banco de Dados")

# Obter dinamicamente anos para o filtro
with engine.connect() as conn:
    anos_db = pd.read_sql(text("SELECT DISTINCT ano FROM dw.dim_tempo WHERE ano > 0 ORDER BY ano;"), conn)
anos_list = anos_db["ano"].tolist()

ano_selecionado = st.sidebar.selectbox("Selecione o Ano", ["Todos"] + anos_list)

filtro_ano = ""
if ano_selecionado != "Todos":
    filtro_ano = f"AND t.ano = {ano_selecionado}"

# KPIs agregadas direto via Metadados/Tabelas Fato
t0_kpi = time.perf_counter()
with engine.connect() as conn:
    total_notif = conn.execute(text(f"SELECT SUM(qtd_notificacao) FROM dw.fato_notificacao_covid f JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_data_notificacao WHERE 1=1 {filtro_ano}")).scalar() or 0
    total_conf  = conn.execute(text(f"SELECT SUM(flag_confirmado) FROM dw.fato_notificacao_covid f JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_data_notificacao WHERE 1=1 {filtro_ano}")).scalar() or 0
    total_obito = conn.execute(text(f"SELECT SUM(flag_obito_covid) FROM dw.fato_notificacao_covid f JOIN dw.dim_tempo t ON t.sk_tempo = f.sk_data_notificacao WHERE 1=1 {filtro_ano}")).scalar() or 0
t_kpi = time.perf_counter() - t0_kpi

c1, c2, c3, c4 = st.columns(4)
c1.metric("📋 Total Notificações (Fato)", f"{total_notif:,}")
c2.metric("✅ Casos Confirmados", f"{total_conf:,}")
c3.metric("💀 Óbitos por COVID-19", f"{total_obito:,}")
c4.metric("⏱️ Consulta KPIs", f"{t_kpi:.3f} s")

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Série Temporal", 
    "🗺️ Casos por Município", 
    "👥 Pirâmide Etária (Óbitos)", 
    "🩺 Top Comorbidades"
])

with tab1:
    t_chart = time.perf_counter()
    df_st, q_time = query(engine, SQL_SERIE_TEMPORAL.format(filtro_ano=filtro_ano))
    if not df_st.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_st["ano_mes"], df_st["notificacoes"], marker="s", color="#e74c3c", linewidth=2)
        ax.set_xticklabels(df_st["ano_mes"], rotation=45, ha="right", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    st.caption(f"⏱️ SQL: {q_time:.3f}s | Render total: {time.perf_counter()-t_chart:.3f}s")

with tab2:
    t_chart = time.perf_counter()
    df_loc, q_time = query(engine, SQL_HEATMAP.format(filtro_ano=filtro_ano))
    if not df_loc.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        df_loc = df_loc.sort_values("notificacoes", ascending=True)
        bars = ax.barh(df_loc["municipio"], df_loc["notificacoes"], color="#34495e")
        ax.bar_label(bars, fmt="{:,.0f}", padding=3, fontsize=9)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    st.caption(f"⏱️ SQL: {q_time:.3f}s | Render total: {time.perf_counter()-t_chart:.3f}s")

with tab3:
    t_chart = time.perf_counter()
    df_p, q_time = query(engine, SQL_PIRAMIDE.format(filtro_ano=filtro_ano))
    ordem = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
    
    if not df_p.empty:
        pyramid = df_p.pivot(index="faixa_etaria", columns="sexo", values="obitos").fillna(0)
        for col in ["M", "F"]:
            if col not in pyramid.columns: pyramid[col] = 0
            
        pyramid = pyramid.reindex(ordem, fill_value=0)
        masc = pyramid["M"]
        fem = pyramid["F"]
        y = range(len(ordem))
        
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.barh(list(y), [-v for v in masc.values], color="#93d4ff", label="Masculino")
        ax.barh(list(y), fem.values, color="#ff008c", label="Feminino")
        ax.set_yticks(list(y))
        ax.set_yticklabels(ordem, fontsize=8)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{abs(int(x)):,}"))
        ax.set_title("Pirâmide Etária dos Óbitos — DW", fontsize=11, fontweight="bold")
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    st.caption(f"⏱️ SQL: {q_time:.3f}s | Render total: {time.perf_counter()-t_chart:.3f}s")

with tab4:
    t_chart = time.perf_counter()
    df_como, q_time = query(engine, SQL_COMORBIDADE.format(filtro_ano=filtro_ano))
    
    if not df_como.empty:
        contagens = df_como.iloc[0].to_dict()
        s = pd.Series(contagens).sort_values(ascending=True)
        
        fig, ax = plt.subplots(figsize=(9, 4))
        bars = ax.barh(s.index, s.values, color="#543a5f", edgecolor="white")
        ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=9, fontweight="bold")
        ax.set_title("Top Comorbidades nos Óbitos — DW", fontsize=11, fontweight="bold")
        ax.grid(axis="x", linestyle="--", alpha=0.5)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    else:
        st.info("Nenhum dado de comorbidade retornado pelo banco.")
    st.caption(f"⏱️ SQL: {q_time:.3f}s | Render total: {time.perf_counter()-t_chart:.3f}s")