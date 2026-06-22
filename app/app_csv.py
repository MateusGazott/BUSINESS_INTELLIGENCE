import time
import warnings
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

warnings.filterwarnings("ignore")

# Configuração da página do Streamlit
st.set_page_config(
    page_title="COVID-19 ES — Dashboard CSV",
    page_icon="🦠",
    layout="wide",
)

ARQUIVO_CSV = "MICRODADOS.csv"
ENCODING    = "ISO-8859-1"
SEPARADOR   = ";"
AMOSTRA     = 500_000

@st.cache_data(show_spinner="Carregando dados do CSV...")
def load_csv():
    t0 = time.perf_counter()
    df = pd.read_csv(
        ARQUIVO_CSV,
        encoding=ENCODING,
        sep=SEPARADOR,
        nrows=AMOSTRA,
        low_memory=False,
        dtype=str,
    )
    
    # Conversões e Flags de Regras de Negócio
    df["DataNotificacao"] = pd.to_datetime(df.get("DataNotificacao"), dayfirst=True, errors="coerce")
    df["AnoMes"] = df["DataNotificacao"].dt.to_period("M").astype(str)
    df["Ano"]    = df["DataNotificacao"].dt.year.fillna(0).astype(int)
    df["flag_confirmado"] = (df.get("Classificacao", "") == "Confirmados").astype(int)
    df["flag_obito"]      = (df.get("Evolucao", "") == "Óbito pelo COVID-19").astype(int)
    
    # Tratamento para a Pirâmide Etária
    df["IdadeNaDataNotificacao"] = pd.to_numeric(df.get("IdadeNaDataNotificacao"), errors="coerce").fillna(0).astype(int)
    
    t_total = time.perf_counter() - t0
    return df, t_total

# Carregar os dados
df, t_load = load_csv()

st.title("🦠 Painel Analítico COVID-19 ES (Versão CSV)")
st.sidebar.header("Filtros Globais")

# Filtro de Ano
anos_disponiveis = sorted(list(df["Ano"].unique()))
if 0 in anos_disponiveis:
    anos_disponiveis.remove(0)
ano_selecionado = st.sidebar.selectbox("Selecione o Ano", ["Todos"] + anos_disponiveis)

# Aplicar o filtro
if ano_selecionado != "Todos":
    df_fil = df[df["Ano"] == ano_selecionado]
else:
    df_fil = df.copy()

# KPIs no topo
c1, c2, c3, c4 = st.columns(4)
c1.metric("📋 Total Notificações (Amostra)", f"{len(df_fil):,}")
c2.metric("✅ Casos Confirmados", f"{df_fil['flag_confirmado'].sum():,}")
c3.metric("💀 Óbitos por COVID-19", f"{df_fil['flag_obito'].sum():,}")
c4.metric("⏱️ Tempo de Carga CSV", f"{t_load:.3f} s")

# Criação das Abas de Análise Visual
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Série Temporal", 
    "🗺️ Casos por Município", 
    "👥 Pirâmide Etária (Óbitos)", 
    "🩺 Top Comorbidades"
])

with tab1:
    t_chart = time.perf_counter()
    st.subheader("Evolução Mensal de Notificações")
    serie = df_fil.groupby("AnoMes").size().sort_index()
    if not serie.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(serie.index, serie.values, marker="o", color="#1f77b4", linewidth=2)
        ax.set_xticklabels(serie.index, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Notificações")
        ax.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    st.caption(f"⏱️ Renderizado em {time.perf_counter()-t_chart:.3f}s")

with tab2:
    t_chart = time.perf_counter()
    st.subheader("Top 10 Municípios com Mais Notificações")
    municipios = df_fil["Municipio"].value_counts().head(10).sort_values(ascending=True)
    if not municipios.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.barh(municipios.index, municipios.values, color="#2ca02c")
        ax.bar_label(bars, fmt="{:,.0f}", padding=3, fontsize=9)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    st.caption(f"⏱️ Renderizado em {time.perf_counter()-t_chart:.3f}s")

with tab3:
    t_chart = time.perf_counter()
    st.subheader("Distribuição Demográfica dos Óbitos")
    
    # Definição das faixas etárias
    bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 120]
    ordem = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
    df_obitos = df_fil[df_fil["flag_obito"] == 1].copy()
    
    if not df_obitos.empty:
        df_obitos["FaixaEtaria_Calc"] = pd.cut(df_obitos["IdadeNaDataNotificacao"], bins=bins, labels=ordem, right=False)
        pyramid = df_obitos.groupby(["FaixaEtaria_Calc", "Sexo"]).size().unstack(fill_value=0)
        
        if "M" not in pyramid.columns: pyramid["M"] = 0
        if "F" not in pyramid.columns: pyramid["F"] = 0
        
        masc = pyramid["M"]
        fem = pyramid["F"]
        y = range(len(ordem))
        
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.barh(list(y), [-v for v in masc.values], color="#2980b9", label="Masculino")
        ax.barh(list(y), fem.values, color="#e91e8c", label="Feminino")
        ax.set_yticks(list(y))
        ax.set_yticklabels(ordem, fontsize=8)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{abs(int(x)):,}"))
        ax.set_title("Pirâmide Etária dos Óbitos — CSV", fontsize=11, fontweight="bold")
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    st.caption(f"⏱️ Renderizado em {time.perf_counter()-t_chart:.3f}s")

with tab4:
    t_chart = time.perf_counter()
    st.subheader("Top Comorbidades Relacionadas aos Óbitos")
    
    cols_como = {
        "ComorbidadeCardio": "Cardiovascular",
        "ComorbidadeDiabetes": "Diabetes",
        "ComorbidadeObesidade": "Obesidade",
        "ComorbidadePulmao": "Pulmonar",
        "ComorbidadeTabagismo": "Tabagismo",
        "ComorbidadeRenal": "Renal",
    }
    
    obitos = df_fil[df_fil["flag_obito"] == 1]
    contagens = {label: (obitos[col] == "Sim").sum() for col, label in cols_como.items() if col in obitos.columns}
    
    if contagens:
        s = pd.Series(contagens).sort_values(ascending=True).tail(5)
        fig, ax = plt.subplots(figsize=(9, 4))
        bars = ax.barh(s.index, s.values, color="#8e44ad", edgecolor="white")
        ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=9, fontweight="bold")
        ax.set_title("Top 5 Comorbidades nos Óbitos — CSV", fontsize=11, fontweight="bold")
        ax.grid(axis="x", linestyle="--", alpha=0.5)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    else:
        st.info("Nenhum dado de comorbidade encontrado para os óbitos filtrados.")
    st.caption(f"⏱️ Renderizado em {time.perf_counter()-t_chart:.3f}s")