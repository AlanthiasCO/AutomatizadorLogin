import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()
CAMINHO_CREDENCIAL = 'credentials.json'
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
# Carrega e processa os dados da aba 'Logs' da planilha do Google Sheets
@st.cache_data(ttl=30)
def carregar_dados_log():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CAMINHO_CREDENCIAL, SCOPE)
        client = gspread.authorize(creds)
        worksheet_logs = client.open("contas_app").worksheet("Logs")
        dados = worksheet_logs.get_all_records()
        if not dados:
            return pd.DataFrame()
        df = pd.DataFrame(dados)
        if 'Timestamp' in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%d/%m/%Y %H:%M:%S')
        else:
            df['Timestamp'] = pd.NaT
        return df.sort_values(by='Timestamp')
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        return pd.DataFrame()

#Retorna logins que violaram a regra: >2 usuários únicos por máquina em 60 minutos
def encontrar_violacoes(df):
    if df.empty or 'Timestamp' not in df.columns:
        return pd.DataFrame()
    violacoes = []
    for _, login_atual in df.iterrows():
        maquina = login_atual['Nome da Máquina']
        ts = login_atual['Timestamp']
        inicio = ts - timedelta(minutes=60)
        logs_na_janela = df[(df['Nome da Máquina'] == maquina) & (df['Timestamp'] >= inicio) & (df['Timestamp'] <= ts)]
        usuarios_unicos = logs_na_janela['Nome Aluno'].nunique()
        if usuarios_unicos > 2:
            entry = login_atual.copy()
            entry['Motivo'] = f'{usuarios_unicos} usuários únicos na última hora'
            violacoes.append(entry)
    if not violacoes:
        return pd.DataFrame()
    return pd.DataFrame(violacoes).drop_duplicates()

st.set_page_config(page_title="Dashboard de Acessos", layout="wide", initial_sidebar_state="collapsed")
st.title("Dashboard de Monitoramento de Acessos")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

df_logs = carregar_dados_log()
df_violacoes = encontrar_violacoes(df_logs)

if not df_violacoes.empty:
    st.warning(f"🚨 ALERTA: Detectada(s) {len(df_violacoes)} violação(ões) da regra de limite de contas. Verifique a aba de alertas para mais detalhes.", icon="⚠️")

if df_logs.empty:
    st.warning("Ainda não há dados de log para exibir ou a planilha está vazia.")
    st.stop()

agora = datetime.now()
limite_tempo_ativo = agora - timedelta(minutes=36)
sessoes_ativas = df_logs[df_logs['Timestamp'] > limite_tempo_ativo]

tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "💻 Análise por Máquina", "📜 Histórico Completo", "🚨 Alertas de Violação"])

with tab1:
    st.header("Status em Tempo Real")
    col1, col2, col3 = st.columns(3)
    col1.metric("Sessões Ativas Agora", len(sessoes_ativas))
    col2.metric("Total de Logins Hoje", len(df_logs[df_logs['Timestamp'].dt.date == agora.date()]))
    col3.metric("Total de Logins (Geral)", len(df_logs))
    st.divider()
    st.subheader("Tabela de Sessões Ativas")
    if not sessoes_ativas.empty:
        cols = ['Timestamp', 'Nome Aluno', 'Escola', 'Nome da Máquina']
        st.dataframe(sessoes_ativas[cols].sort_values(by='Timestamp', ascending=False), use_container_width=True)
    else:
        st.info("Nenhuma sessão ativa no momento.")

with tab2:
    st.header("Uso por Máquina")
    col1, col2 = st.columns([1, 2])
    with col1:
        logins_por_maquina = df_logs['Nome da Máquina'].value_counts().reset_index()
        logins_por_maquina.columns = ['Máquina', 'Total de Logins']
        st.subheader("Total de Logins")
        st.dataframe(logins_por_maquina, use_container_width=True)
    with col2:
        st.subheader("Gráfico de Logins por Máquina")
        st.bar_chart(logins_por_maquina.set_index('Máquina'))

with tab3:
    st.header("Todos os Registros de Log")
    st.dataframe(df_logs.sort_values(by='Timestamp', ascending=False), use_container_width=True)

with tab4:
    st.header("Registros de Violação da Regra de Limite")
    st.info("Regra: no máximo 2 contas diferentes por máquina em 60 minutos. A tabela abaixo mostra as violações.")
    if not df_violacoes.empty:
        st.dataframe(df_violacoes[['Timestamp', 'Nome Aluno', 'Nome da Máquina', 'Motivo']], use_container_width=True)
    else:
        st.success("Nenhuma violação detectada")

if st.button('Recarregar Dados'):
    st.cache_data.clear()
    st.experimental_rerun()