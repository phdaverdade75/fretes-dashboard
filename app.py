import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import uuid
import math
import requests

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E DESIGN PREMIUM
# ==========================================
st.set_page_config(page_title="FRETES ANALYTICS V1.0", page_icon="🚚", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .status-card {
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 2px 4px 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .card-verde { background-color: #00C49F; color: white; border-bottom: 5px solid #008f73; }
    .card-vermelho { background-color: #FF4B4B; color: white; border-bottom: 5px solid #b33434; }
    .card-amarelo { background-color: #FFA500; color: white; border-bottom: 5px solid #cc8400; }
    
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #ffffff, #f4f6f9);
        border: 1px solid #e0e4e8;
        border-left: 5px solid #1C83E1;
        padding: 20px;
        border-radius: 10px;
    }
    .bloco-info { background-color: rgba(128, 128, 128, 0.05); padding: 20px; border-radius: 12px; border: 1px solid rgba(128,128,128,0.1); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DO BANCO DE DADOS E FUNÇÕES
# ==========================================
COORDENADAS_ESTADOS = {
    'AC': (-9.0238, -70.8120), 'AL': (-9.5328, -36.6698), 'AP': (1.4192, -51.7792),
    'AM': (-3.4168, -65.8561), 'BA': (-12.5797, -41.7007), 'CE': (-5.4984, -39.3206),
    'DF': (-15.7998, -47.8645), 'ES': (-19.1834, -40.3089), 'GO': (-15.8270, -49.8362),
    'MA': (-4.9609, -45.2744), 'MT': (-12.6819, -56.9211), 'MS': (-20.7722, -54.3647),
    'MG': (-18.5122, -44.5550), 'PA': (-1.9981, -54.9306), 'PB': (-7.2399, -36.7820),
    'PR': (-25.2521, -52.0215), 'PE': (-8.8137, -36.9541), 'PI': (-7.7183, -42.7289),
    'RJ': (-22.9094, -43.2094), 'RN': (-5.7945, -36.5664), 'RS': (-30.0346, -51.2177),
    'RO': (-11.5057, -63.5806), 'RR': (2.7376, -62.0751), 'SC': (-27.2423, -50.2189),
    'SP': (-23.5505, -46.6333), 'SE': (-10.5741, -37.3857), 'TO': (-10.1843, -48.3336)
}

def limpar_dados(df_entrada):
    df = df_entrada.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    
    # Mapeamento Inteligente Seguro (Não sobrescreve colunas)
    mapeamento = {}
    for col in df.columns:
        if col in ['Nº DE PEDIDO', 'NUMERO DO PEDIDO', 'PEDIDO']: mapeamento[col] = 'Nº DE PEDIDO'
        elif 'VLR DO FRETE' in col or 'VALOR FRETE' in col or 'VALOR DO FRETE' in col: mapeamento[col] = 'VLR DO FRETE'
        elif 'PREVISÃO' in col or 'PREVISAO' in col: mapeamento[col] = 'DATA DE PREVISÃO DE ENTREGA'
        elif 'ENTREGA' in col and 'PREVIS' not in col: mapeamento[col] = 'DATA ENTREGUE'
        elif 'MEDICAO' in col or 'MEDIÇÃO' in col: mapeamento[col] = 'MEDIÇÃO/SUPRIMENTOS'
        elif 'STATUS' in col: mapeamento[col] = 'STATUS FRETES'
        elif 'OBSERVA' in col: mapeamento[col] = 'OBSERVAÇÃO'
        elif 'VEICULO' in col or 'VEÍCULO' in col: mapeamento[col] = 'VEÍCULO'

    df.rename(columns=mapeamento, inplace=True)
    
    # Se ainda não tiver 'Nº DE PEDIDO', aí sim ele tenta usar o Chamado/Processo
    if 'Nº DE PEDIDO' not in df.columns:
        for col in df.columns:
            if 'CHAMADO' in col or 'PROCESSO' in col:
                df.rename(columns={col: 'Nº DE PEDIDO'}, inplace=True)
                break

    if 'Nº DE PEDIDO' not in df.columns:
        return df, False, "Erro: Coluna de Pedido não encontrada. Nomes lidos: " + ", ".join(df.columns)

    if 'ID_INTERNO' not in df.columns: 
        df['ID_INTERNO'] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    colunas_finais = [
        'ID_INTERNO', 'TRANSPORTADORA', 'CHAMADO DE FRETE / Nº PROCESSO', 'NUMERO DA NOTA', 
        'VALOR DA NOTA', 'CENTRO DE CUSTO', 'Nº DE PEDIDO', 'FILIAL', 'DATA COLETA', 
        'SOLICITANTE DO CHAMADO', 'EMAIL SOLICITANTE', 'STATUS FRETES', 'VLR DO FRETE', 
        'CIDADE ORIGEM', 'ESTADO ORIGEM', 'CIDADE DESTINO', 'ESTADO DESTINO', 'VEÍCULO', 
        'DOCUMENTO', 'MEDIÇÃO/SUPRIMENTOS', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE', 'OBSERVAÇÃO'
    ]
    
    for c in colunas_finais:
        if c not in df.columns: df[c] = "NÃO INFORMADO"

    for c in ['VLR DO FRETE', 'VALOR DA NOTA']:
        df[c] = df[c].astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    
    for c in ['DATA COLETA', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE']:
        df[c] = pd.to_datetime(df[c], errors='coerce')
        
    return df[colunas_finais], True, "Sucesso"

def avaliar_prazo(row):
    if pd.isna(row['DATA ENTREGUE']): return 'EM ANDAMENTO'
    if pd.isna(row['DATA DE PREVISÃO DE ENTREGA']): return 'SEM PREVISÃO'
    if row['DATA ENTREGUE'].date() <= row['DATA DE PREVISÃO DE ENTREGA'].date(): return 'NO PRAZO'
    return 'ATRASADO'

def get_coords(estado_str):
    if pd.notna(estado_str) and str(estado_str).strip().upper() != 'NÃO INFORMADO':
        uf = str(estado_str).strip().upper().split('-')[0].strip()
        if uf in COORDENADAS_ESTADOS: return COORDENADAS_ESTADOS[uf]
    return (None, None)

@st.cache_data(show_spinner=False)
def obter_rota_rodoviaria(lon1, lat1, lon2, lat2):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        req = requests.get(url, timeout=3)
        if req.status_code == 200:
            dados = req.json()
            if dados.get('code') == 'Ok':
                coords = dados['routes'][0]['geometry']['coordinates']
                return [c[0] for c in coords], [c[1] for c in coords], dados['routes'][0]['distance'] / 1000.0
    except: pass
    return None, None, None

def get_otd_info(otd):
    if otd < 0: return "N/A", "#808080", "⚪", "Sem dados."
    if otd >= 95: return "EXCELENTE", "#00C49F", "🟢", "Transportadora altamente aderente."
    if otd >= 85: return "BOA", "#1C83E1", "🔵", "Performance estável."
    if otd >= 70: return "ALERTA", "#FFA500", "🟡", "Necessário plano de ação."
    return "CRÍTICA", "#FF4B4B", "🔴", "Avaliar substituição."

# ==========================================
# 3. CABEÇALHO E UPLOAD
# ==========================================
st.title("🚚 FRETES ANALYTICS V1.0")
st.caption("Painel Executivo de Gestão Logística | Elaborado por Pedro Anjos")

if 'banco_dados' not in st.session_state:
    st.session_state.banco_dados = pd.DataFrame()

with st.expander("📥 Importar Dados (Atualizar Base)", expanded=st.session_state.banco_dados.empty):
    col_up, col_btn = st.columns([8, 2])
    with col_up:
        arq_upload = st.file_uploader("Subir Planilha Matriz", type=["xlsx", "xlsb", "xls", "csv"], label_visibility="collapsed")
    with col_btn:
        if st.button("🔄 Sincronizar", type="primary", use_container_width=True):
            if arq_upload:
                try:
                    if arq_upload.name.lower().endswith('.csv'):
                        try:
                            df_temp = pd.read_csv(arq_upload, encoding='utf-8')
                        except UnicodeDecodeError:
                            arq_upload.seek(0)
                            df_temp = pd.read_csv(arq_upload, encoding='latin1')
                        
                        df_limpo, sucesso, msg = limpar_dados(df_temp)
                        if sucesso:
                            st.session_state.banco_dados = df_limpo
                            st.rerun()
                        else: st.error("Aba incorreta lida no CSV: " + msg)
                    
                    else:
                        motor = 'pyxlsb' if arq_upload.name.lower().endswith('.xlsb') else 'openpyxl'
                        xls = pd.ExcelFile(arq_upload, engine=motor)
                        
                        sucesso_global = False
                        msg_erro = ""
                        
                        for aba in xls.sheet_names:
                            df_temp = pd.read_excel(xls, sheet_name=aba)
                            df_limpo, sucesso, msg = limpar_dados(df_temp)
                            
                            if sucesso:
                                st.session_state.banco_dados = df_limpo
                                sucesso_global = True
                                break 
                            else:
                                msg_erro = msg
                        
                        if sucesso_global:
                            st.rerun()
                        else:
                            st.error(f"Erro: Nenhuma aba válida com a coluna de Pedidos foi encontrada na planilha. Última aba lida: {msg_erro}")

                except Exception as e: st.error(f"Erro no arquivo: {e}")

st.divider()
df_raw = st.session_state.banco_dados

if not df_raw.empty:
    df_raw['PERFORMANCE_SLA'] = df_raw.apply(avaliar_prazo, axis=1)
    df_raw['lat_o'] = df_raw.apply(lambda r: get_coords(r['ESTADO ORIGEM'])[0], axis=1)
    df_raw['lon_o'] = df_raw.apply(lambda r: get_coords(r['ESTADO ORIGEM'])[1], axis=1)
    df_raw['lat_d'] = df_raw.apply(lambda r: get_coords(r['ESTADO DESTINO'])[0], axis=1)
    df_raw['lon_d'] = df_raw.apply(lambda r: get_coords(r['ESTADO DESTINO'])[1], axis=1)

    tab1, tab2, tab3 = st.tabs(["📊 Visão Global", "🗺️ Mapa & SLA", "🏆 Ranking"])

    # ==========================================
    # PÁGINA 1
    # ==========================================
    with tab1:
        c1, c2 = st.columns([2.5, 7.5])
        with c1:
            st.markdown("### 🔎 Filtros")
            f1_dt_ini = st.date_input("Início", value=None, key="f1i")
            f1_dt_fim = st.date_input("Fim", value=None, key="f1f")
            f1_ped = st.selectbox("Pedido", ["TODOS"] + sorted(df_raw['Nº DE PEDIDO'].astype(str).unique()))
            f1_fil = st.selectbox("Filial", ["TODAS"] + sorted(df_raw['FILIAL'].astype(str).unique()))
            f1_tra = st.selectbox("Transportadora", ["TODAS"] + sorted(df_raw['TRANSPORTADORA'].astype(str).unique()))
            f1_vei = st.selectbox("Veículo", ["TODOS"] + sorted(df_raw['VEÍCULO'].astype(str).unique()))

        df1 = df_raw.copy()
        if f1_dt_ini: df1 = df1[df1['DATA COLETA'].dt.date >= f1_dt_ini]
        if f1_dt_fim: df1 = df1[df1['DATA COLETA'].dt.date <= f1_dt_fim]
        if f1_ped != "TODOS": df1 = df1[df1['Nº DE PEDIDO'].astype(str) == f1_ped]
        if f1_fil != "TODAS": df1 = df1[df1['FILIAL'].astype(str) == f1_fil]
        if f1_tra != "TODAS": df1 = df1[df1['TRANSPORTADORA'].astype(str) == f1_tra]
        if f1_vei != "TODOS": df1 = df1[df1['VEÍCULO'].astype(str) == f1_vei]

        with c2:
            m1, m2 = st.columns(2)
            m1.metric("💰 Faturamento Total Fretes", f"R$ {df1['VLR DO FRETE'].sum():,.2f}")
            m2.metric("📦 Total Fretes (Pedidos)", df1['Nº DE PEDIDO'].nunique())
            
            g1, g2 = st.columns(2)
            with g1:
                df_f = df1.groupby('FILIAL')['VLR DO FRETE'].sum().reset_index().sort_values('VLR DO FRETE', ascending=False)
                fig1 = px.bar(df_f, x='FILIAL', y='VLR DO FRETE', text='VLR DO FRETE', title="Faturamento por Filial", color_discrete_sequence=['#1C83E1'])
                fig1.update_traces(texttemplate='R$ %{text:,.2f}', textposition='outside')
                fig1.update_layout(margin=dict(t=40), yaxis=dict(visible=False))
                st.plotly_chart(fig1, use_container_width=True)
            with g2:
                df_v = df1.groupby('VEÍCULO')['Nº DE PEDIDO'].nunique().reset_index().sort_values('Nº DE PEDIDO', ascending=False)
                fig2 = px.bar(df_v, x='VEÍCULO', y='Nº DE PEDIDO', text='Nº DE PEDIDO', title="Veículos Utilizados", color_discrete_sequence=['#00C49F'])
                fig2.update_traces(texttemplate='%{text}', textposition='outside')
                fig2.update_layout(margin=dict(t=40), yaxis=dict(visible=False))
                st.plotly_chart(fig2, use_container_width=True)
            
            df_p = df1.groupby('MEDIÇÃO/SUPRIMENTOS')['Nº DE PEDIDO'].nunique().reset_index()
            st.plotly_chart(px.pie(df_p, values='Nº DE PEDIDO', names='MEDIÇÃO/SUPRIMENTOS', hole=0.4, title="Suprimentos x Medição"), use_container_width=True)

        st.markdown("### 📋 Diário de Bordo")
        st.dataframe(df1.drop(columns=['ID_INTERNO','lat_o','lon_o','lat_d','lon_d'], errors='ignore'), use_container_width=True)

    # ==========================================
    # PÁGINA 2
    # ==========================================
    with tab2:
        df2_b = df_raw.copy()
        colf1, colf2, colf3 = st.columns(3)
        f2_sla = colf1.selectbox("🚥 Status SLA", ["TODOS", "NO PRAZO", "ATRASADO", "EM ANDAMENTO"], key="f2s")
        if f2_sla != "TODOS": df2_b = df2_b[df2_b['PERFORMANCE_SLA'] == f2_sla]
        
        f2_tra = colf2.selectbox("🏢 Transportadora", ["TODAS"] + sorted(df2_b['TRANSPORTADORA'].astype(str).unique()), key="f2t")
        if f2_tra != "TODAS": df2_b = df2_b[df2_b['TRANSPORTADORA'].astype(str) == f2_tra]
        
        f2_ped = colf3.selectbox("📌 Pedido", ["TODOS"] + sorted(df2_b['Nº DE PEDIDO'].astype(str).unique()), key="f2p")
        if f2_ped != "TODOS": df2_b = df2_b[df2_b['Nº DE PEDIDO'].astype(str) == f2_ped]

        st.write("")
        c_prazo, c_atraso, c_andamento = st.columns(3)
        
        n_prazo = len(df2_b[df2_b['PERFORMANCE_SLA'] == 'NO PRAZO'])
        n_atraso = len(df2_b[df2_b['PERFORMANCE_SLA'] == 'ATRASADO'])
        n_andamento = len(df2_b[df2_b['PERFORMANCE_SLA'] == 'EM ANDAMENTO'])

        c_prazo.markdown(f"<div class='status-card card-verde'><h3>✅ NO PRAZO</h3><h1>{n_prazo}</h1></div>", unsafe_allow_html=True)
        c_atraso.markdown(f"<div class='status-card card-vermelho'><h3>🚨 ATRASADO</h3><h1>{n_atraso}</h1></div>", unsafe_allow_html=True)
        c_andamento.markdown(f"<div class='status-card card-amarelo'><h3>⏳ EM ANDAMENTO</h3><h1>{n_andamento}</h1></div>", unsafe_allow_html=True)

        col_m, col_d = st.columns([6, 4])
        with col_m:
            df_mapa = df2_b.dropna(subset=['lat_o','lon_o','lat_d','lon_d'])
            fig_mapa = go.Figure()
            if f2_ped == "TODOS":
                fig_mapa.add_trace(go.Densitymapbox(lat=df_mapa['lat_d'], lon=df_mapa['lon_d'], z=[1]*len(df_mapa), radius=20, colorscale='Inferno', showscale=False))
            else:
                for _, r in df_mapa.iterrows():
                    lons, lats, _ = obter_rota_rodoviaria(r['lon_o'], r['lat_o'], r['lon_d'], r['lat_d'])
                    cor = "#00C49F" if r['PERFORMANCE_SLA'] == 'NO PRAZO' else "#FF4B4B" if r['PERFORMANCE_SLA'] == 'ATRASADO' else "#FFA500"
                    if lons: fig_mapa.add_trace(go.Scattermapbox(mode="lines", lon=lons, lat=lats, line=dict(width=3, color=cor)))
            fig_mapa.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, mapbox=dict(style="carto-darkmatter", center=dict(lon=-52, lat=-15), zoom=3.5), showlegend=False)
            st.plotly_chart(fig_mapa, use_container_width=True)
        
        with col_d:
            if f2_tra != "TODAS":
                total_f = n_prazo + n_atraso
                otd = (n_prazo/total_f)*100 if total_f > 0 else -1
                txt, cor, ico, msg = get_otd_info(otd)
                if otd >= 0:
                    st.markdown(f"<div style='background:{cor}15; border-left:5px solid {cor}; padding:15px; border-radius:8px;'><h5>{ico} Performance: {txt}</h5><h2>OTD: {otd:.1f}%</h2><p>{msg}</p></div>", unsafe_allow_html=True)
            
            if f2_ped != "TODOS":
                r = df2_b.iloc[0]
                st.markdown(f"<div class='bloco-info'><h5>Pedido: {f2_ped}</h5><p><b>Origem:</b> {r['CIDADE ORIGEM']} | <b>Destino:</b> {r['CIDADE DESTINO']}<br><b>Data Coleta:</b> {r['DATA COLETA'].strftime('%d/%m/%Y')}<br><b>Data Entrega:</b> {r['DATA ENTREGUE'].strftime('%d/%m/%Y') if pd.notnull(r['DATA ENTREGUE']) else 'N/A'}<br><b>Obs:</b> {str(r['OBSERVAÇÃO']).upper()}</p></div>", unsafe_allow_html=True)

        st.dataframe(df2_b.drop(columns=['ID_INTERNO','lat_o','lon_o','lat_d','lon_d'], errors='ignore'), use_container_width=True)

    # ==========================================
    # PÁGINA 3
    # ==========================================
    with tab3:
        df3 = df_raw.copy()
        cf1, cf2 = st.columns(2)
        f3_fil = cf1.selectbox("Filial", ["TODAS"] + sorted(df3['FILIAL'].astype(str).unique()), key="f3fil")
        f3_sla_regua = cf2.selectbox("Régua SLA", ["TODOS", "EXCELENTE", "BOA", "ALERTA", "CRÍTICA"], key="f3r")
        if f3_fil != "TODAS": df3 = df3[df3['FILIAL'].astype(str) == f3_fil]

        n3_p = len(df3[df3['PERFORMANCE_SLA'] == 'NO PRAZO'])
        n3_at = len(df3[df3['PERFORMANCE_SLA'] == 'ATRASADO'])
        n3_an = len(df3[df3['PERFORMANCE_SLA'] == 'EM ANDAMENTO'])

        c3a, c3b, c3c = st.columns(3)
        c3a.markdown(f"<div class='status-card card-verde'><h3>✅ NO PRAZO</h3><h1>{n3_p}</h1></div>", unsafe_allow_html=True)
        c3b.markdown(f"<div class='status-card card-vermelho'><h3>🚨 ATRASADO</h3><h1>{n3_at}</h1></div>", unsafe_allow_html=True)
        c3c.markdown(f"<div class='status-card card-amarelo'><h3>⏳ EM ANDAMENTO</h3><h1>{n3_an}</h1></div>", unsafe_allow_html=True)

        cr1, cr2 = st.columns(2)
        with cr1:
            df_v3 = df3.groupby('TRANSPORTADORA')['Nº DE PEDIDO'].nunique().reset_index().sort_values('Nº DE PEDIDO', ascending=False)
            fig_v3 = px.bar(df_v3, x='TRANSPORTADORA', y='Nº DE PEDIDO', text='Nº DE PEDIDO', title="Ranking Volume", color_discrete_sequence=['#1C83E1'])
            fig_v3.update_traces(textposition='outside')
            fig_v3.update_layout(margin=dict(t=40), yaxis=dict(visible=False))
            st.plotly_chart(fig_v3, use_container_width=True)
        
        with cr2:
            def calc_otd(g):
                v = g[g['PERFORMANCE_SLA'].isin(['NO PRAZO','ATRASADO'])]
                return (len(v[v['PERFORMANCE_SLA']=='NO PRAZO'])/len(v))*100 if len(v)>0 else -1
            r_sla = df3.groupby('TRANSPORTADORA').apply(calc_otd).reset_index()
            r_sla.columns = ['TRANSPORTADORA','OTD']
            r_sla = r_sla[r_sla['OTD'] >= 0]
            r_sla['CLASS'] = r_sla['OTD'].apply(lambda x: get_otd_info(x)[0])
            if f3_sla_regua != "TODOS": r_sla = r_sla[r_sla['CLASS'] == f3_sla_regua]
            r_sla = r_sla.sort_values('OTD', ascending=False)
            
            fig_s3 = px.bar(r_sla, x='TRANSPORTADORA', y='OTD', text='OTD', title="Ranking SLA (OTD %)", 
                            color='CLASS', color_discrete_map={'EXCELENTE':'#00C49F','BOA':'#1C83E1','ALERTA':'#FFA500','CRÍTICA':'#FF4B4B'})
            fig_s3.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_s3.update_layout(margin=dict(t=40), yaxis=dict(visible=False))
            st.plotly_chart(fig_s3, use_container_width=True)
