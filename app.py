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
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #ffffff, #f4f6f9);
        border: 1px solid #e0e4e8;
        border-left: 5px solid #1C83E1;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 4px 12px rgba(0,0,0,0.05);
    }
    .badge-excelente { background-color: #00C49F; color: white; padding: 6px 16px; border-radius: 20px; font-weight: 600; display: inline-block; margin-top: 8px; font-size: 0.9em; letter-spacing: 0.5px;}
    .badge-ruim { background-color: #FF4B4B; color: white; padding: 6px 16px; border-radius: 20px; font-weight: 600; display: inline-block; margin-top: 8px; font-size: 0.9em; letter-spacing: 0.5px;}
    .badge-andamento { background-color: #FFA500; color: white; padding: 6px 16px; border-radius: 20px; font-weight: 600; display: inline-block; margin-top: 8px; font-size: 0.9em; letter-spacing: 0.5px;}
    .bloco-info { background-color: rgba(128, 128, 128, 0.05); padding: 20px; border-radius: 12px; border: 1px solid rgba(128,128,128,0.1); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DO BANCO DE DADOS E FUNÇÕES
# ==========================================
ARQUIVO_DB = "banco_fretes_final.csv"

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

nomes_estados = {
    'SAO PAULO': 'SP', 'MINAS GERAIS': 'MG', 'RIO DE JANEIRO': 'RJ', 'BAHIA': 'BA',
    'PARANA': 'PR', 'RIO GRANDE DO SUL': 'RS', 'SANTA CATARINA': 'SC', 'GOIAS': 'GO',
    'MATO GROSSO': 'MT', 'MATO GROSSO DO SUL': 'MS', 'PERNAMBUCO': 'PE', 'CEARA': 'CE',
    'PARA': 'PA', 'MARANHAO': 'MA', 'ESPIRITO SANTO': 'ES', 'PARAIBA': 'PB',
    'AMAZONAS': 'AM', 'RIO GRANDE DO NORTE': 'RN', 'ALAGOAS': 'AL', 'PIAUI': 'PI',
    'TOCANTINS': 'TO', 'DISTRITO FEDERAL': 'DF', 'SERGIPE': 'SE', 'RONDONIA': 'RO',
    'RORAIMA': 'RR', 'AMAPA': 'AP', 'ACRE': 'AC'
}

COLUNAS_PADRAO = [
    'ID_INTERNO', 'TRANSPORTADORA', 'CHAMADO DE FRETE / Nº PROCESSO', 'NUMERO DA NOTA', 
    'VALOR DA NOTA', 'CENTRO DE CUSTO', 'Nº DE PEDIDO', 'FILIAL', 'DATA COLETA', 
    'SOLICITANTE DO CHAMADO', 'EMAIL SOLICITANTE', 'STATUS FRETES', 'VLR DO FRETE', 
    'CIDADE ORIGEM', 'ESTADO ORIGEM', 'CIDADE DESTINO', 'ESTADO DESTINO', 'VEÍCULO', 
    'DOCUMENTO', 'MEDIÇÃO/SUPRIMENTOS', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE', 'OBSERVAÇÃO'
]

if 'banco_dados' not in st.session_state:
    st.session_state.banco_dados = pd.DataFrame(columns=COLUNAS_PADRAO)

def limpar_dados(df):
    df.columns = df.columns.astype(str).str.strip().str.upper().str.replace('  ', ' ')
    mapeamento = {
        'NUMERO DO PEDIDO': 'Nº DE PEDIDO', 'PEDIDO': 'Nº DE PEDIDO',
        'VALOR FRETE': 'VLR DO FRETE', 'VALOR DO FRETE': 'VLR DO FRETE',
        'STATUS': 'STATUS FRETES', 'MEDICAO/SUPRIMENTOS': 'MEDIÇÃO/SUPRIMENTOS',
        'DATA PREVISÃO ENTREGA': 'DATA DE PREVISÃO DE ENTREGA',
        'DATA DE PREVISAO DE ENTREGA': 'DATA DE PREVISÃO DE ENTREGA',
        'DATA ENTREGA': 'DATA ENTREGUE', 'OBSERVACAO': 'OBSERVAÇÃO'
    }
    df.rename(columns=mapeamento, inplace=True)
    if 'Nº DE PEDIDO' not in df.columns: return df, False, "A coluna 'Nº DE PEDIDO' não foi encontrada."
    if 'ID_INTERNO' not in df.columns: df['ID_INTERNO'] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in COLUNAS_PADRAO:
        if col not in df.columns: df[col] = "NÃO INFORMADO"
    for col in COLUNAS_PADRAO:
        if col not in ['VALOR DA NOTA', 'VLR DO FRETE', 'DATA COLETA', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE', 'ID_INTERNO']:
            df[col] = df[col].astype(str).str.upper().str.strip()
            df[col] = df[col].replace(['NAN', 'NONE', 'NULL', ''], 'NÃO INFORMADO')
    for col in ['VLR DO FRETE', 'VALOR DA NOTA']:
        df[col] = df[col].astype(str).str.replace('R$', '', regex=False).str.replace(',', '.', regex=False).str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    for col in ['DATA COLETA', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    return df[COLUNAS_PADRAO], True, "Sucesso"

def avaliar_prazo(row):
    if pd.isna(row['DATA ENTREGUE']): return 'EM ANDAMENTO'
    if pd.isna(row['DATA DE PREVISÃO DE ENTREGA']): return 'SEM PREVISÃO'
    if row['DATA ENTREGUE'] <= row['DATA DE PREVISÃO DE ENTREGA']: return 'NO PRAZO'
    return 'ATRASADO'

def get_coords(estado_str, cidade_str):
    if pd.notna(estado_str) and str(estado_str).strip().upper() != 'NÃO INFORMADO':
        est_raw = str(estado_str).strip().upper()
        uf = est_raw.split('-')[0].strip()
        if uf in COORDENADAS_ESTADOS: return COORDENADAS_ESTADOS[uf]
        if est_raw in nomes_estados: return COORDENADAS_ESTADOS[nomes_estados[est_raw]]
    if pd.notna(cidade_str) and str(cidade_str).strip().upper() != 'NÃO INFORMADO':
        cid = str(cidade_str).upper().replace("-", " ").replace("/", " ")
        partes = cid.split()
        for parte in partes:
            if parte in COORDENADAS_ESTADOS: return COORDENADAS_ESTADOS[parte]
        for nome in nomes_estados.keys():
            if nome in cid: return COORDENADAS_ESTADOS[nomes_estados[nome]]
    return (None, None)

@st.cache_data(show_spinner=False)
def obter_rota_rodoviaria(lon1, lat1, lon2, lat2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
        return None, None, None
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        req = requests.get(url, timeout=5)
        if req.status_code == 200:
            dados = req.json()
            if dados.get('code') == 'Ok':
                coords = dados['routes'][0]['geometry']['coordinates']
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                dist_km = dados['routes'][0]['distance'] / 1000.0
                return lons, lats, dist_km
    except:
        pass
    return None, None, None

def calcular_distancia_reta(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2): return None
    R = 6371.0 
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_otd_info(otd):
    if otd < 0: return "N/A", "#808080", "⚪", "Não há volume finalizado para avaliar OTD."
    elif otd >= 95.0: return "EXCELENTE", "#00C49F", "🟢", "Transportadora altamente aderente ao SLA. Recomenda-se priorização em novas demandas."
    elif otd >= 85.0: return "BOA", "#1C83E1", "🔵", "Performance estável, porém com oportunidade de otimização. Monitoramento contínuo recomendado."
    elif otd >= 70.0: return "ALERTA", "#FFA500", "🟡", "Indício de instabilidade operacional. Necessário plano de ação de recuperação de SLA."
    else: return "CRÍTICA", "#FF4B4B", "🔴", "Performance incompatível. Avaliar penalidades contratuais, redução de volume ou substituição."

# ==========================================
# 3. CABEÇALHO E UPLOAD
# ==========================================
st.title("🚚 FRETES ANALYTICS V1.0")
st.caption("Painel Executivo de Gestão Logística | Desenvolvido estrategicamente por Pedro Anjos")

with st.expander("📥 Importar Dados (Atualizar Base)", expanded=True):
    col_up, col_btn = st.columns([8, 2])
    with col_up:
        arq_upload = st.file_uploader("Subir Planilha Matriz (.xlsx, .xlsb, .xls)", type=["xlsx", "xlsb", "xls"], label_visibility="collapsed")
    with col_btn:
        if st.button("🔄 Sincronizar Dados", type="primary", use_container_width=True):
            if arq_upload:
                try:
                    motor = 'pyxlsb' if arq_upload.name.lower().endswith('.xlsb') else 'openpyxl'
                    xls = pd.ExcelFile(arq_upload, engine=motor)
                    aba_correta = xls.sheet_names[0]
                    for aba in xls.sheet_names:
                        if 'FRETE' in aba.upper() or 'DADOS' in aba.upper() or 'OPERA' in aba.upper():
                            aba_correta = aba; break
                            
                    df_temp = pd.read_excel(arq_upload, engine=motor, sheet_name=aba_correta)
                    df_limpo, sucesso, msg = limpar_dados(df_temp)
                    
                    if sucesso:
                        st.session_state.banco_dados = df_limpo
                        st.success("Dados processados com sucesso! Painel atualizado.")
                        st.rerun()
                    else:
                        st.error(f"Erro na Planilha: {msg}")
                except Exception as e: 
                    st.error(f"Erro de processamento: {e}")
            else:
                st.warning("Anexe uma planilha antes de sincronizar.")

st.divider()
df = st.session_state.banco_dados

if not df.empty:
    df['PERFORMANCE_SLA'] = df.apply(avaliar_prazo, axis=1)
    df['lat_o'] = df.apply(lambda row: get_coords(row['ESTADO ORIGEM'], row['CIDADE ORIGEM'])[0], axis=1)
    df['lon_o'] = df.apply(lambda row: get_coords(row['ESTADO ORIGEM'], row['CIDADE ORIGEM'])[1], axis=1)
    df['lat_d'] = df.apply(lambda row: get_coords(row['ESTADO DESTINO'], row['CIDADE DESTINO'])[0], axis=1)
    df['lon_d'] = df.apply(lambda row: get_coords(row['ESTADO DESTINO'], row['CIDADE DESTINO'])[1], axis=1)

# ==========================================
# NAVEGAÇÃO ENTRE ABAS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 Visão Global", "🗺️ Mapa & SLA Logístico", "🏆 Ranking de Transportadoras"])

# ==========================================
# PÁGINA 1: DASHBOARD DINÂMICO
# ==========================================
with tab1:
    if not df.empty:
        col_filtros, col_conteudo = st.columns([2.5, 7.5], gap="large")
        
        with col_filtros:
            st.markdown("<h4 style='color: #1C83E1;'>🔎 Filtros de Análise</h4>", unsafe_allow_html=True)
            f1_dt_inicio = st.date_input("Data Inicial", value=None, key="p1_dt_ini")
            f1_dt_fim = st.date_input("Data Final", value=None, key="p1_dt_fim")
            
            f1_ped = st.selectbox("Nº Pedido Específico", ["TODOS"] + sorted(df['Nº DE PEDIDO'].unique()), key="p1_ped")
            f1_filial = st.selectbox("Filial", ["TODAS"] + sorted(df['FILIAL'].unique()), key="p1_fil")
            f1_transp = st.selectbox("Transportadora", ["TODAS"] + sorted(df['TRANSPORTADORA'].unique()), key="p1_tra")
            f1_vei = st.selectbox("Veículo", ["TODOS"] + sorted(df['VEÍCULO'].unique()), key="p1_vei")

        df_t1 = df.copy()
        if f1_dt_inicio: df_t1 = df_t1[df_t1['DATA COLETA'].dt.date >= f1_dt_inicio]
        if f1_dt_fim: df_t1 = df_t1[df_t1['DATA COLETA'].dt.date <= f1_dt_fim]
        if f1_ped != "TODOS": df_t1 = df_t1[df_t1['Nº DE PEDIDO'] == f1_ped]
        if f1_filial != "TODAS": df_t1 = df_t1[df_t1['FILIAL'] == f1_filial]
        if f1_transp != "TODAS": df_t1 = df_t1[df_t1['TRANSPORTADORA'] == f1_transp]
        if f1_vei != "TODOS": df_t1 = df_t1[df_t1['VEÍCULO'] == f1_vei]

        with col_conteudo:
            v1, v2 = st.columns(2)
            v1.metric("💰 Faturamento Total Fretes", f"R$ {df_t1['VLR DO FRETE'].sum():,.2f}")
            v2.metric("📦 Total Fretes (Qtd. Pedidos)", df_t1['Nº DE PEDIDO'].nunique())
            
            st.divider()
            
            cg1, cg2 = st.columns(2)
            with cg1:
                df_filial_gasto = df_t1.groupby('FILIAL')['VLR DO FRETE'].sum().reset_index().sort_values('VLR DO FRETE', ascending=True)
                fig_filial = px.bar(df_filial_gasto, y='FILIAL', x='VLR DO FRETE', orientation='h', title="Faturamento por Filial", color='VLR DO FRETE', color_continuous_scale='Teal')
                fig_filial.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_filial, use_container_width=True)

            with cg2:
                df_veiculo_uso = df_t1.groupby('VEÍCULO')['Nº DE PEDIDO'].nunique().reset_index().sort_values('Nº DE PEDIDO', ascending=True)
                fig_veiculo = px.bar(df_veiculo_uso, y='VEÍCULO', x='Nº DE PEDIDO', orientation='h', title="Veículos Mais Utilizados", color='Nº DE PEDIDO', color_continuous_scale='Blues')
                fig_veiculo.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_veiculo, use_container_width=True)
            
            st.write("")
            
            # === DE VOLTA COM DESTAQUE: GRÁFICO DE PIZZA (MEDIÇÃO X SUPRIMENTOS) ===
            df_med_gasto = df_t1.groupby('MEDIÇÃO/SUPRIMENTOS')['Nº DE PEDIDO'].nunique().reset_index()
            fig_med_sup = px.pie(df_med_gasto, values='Nº DE PEDIDO', names='MEDIÇÃO/SUPRIMENTOS', hole=0.4, 
                                 title="Volume: Suprimentos x Medição")
            fig_med_sup.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig_med_sup, use_container_width=True)
        
        # === AQUI FORA DA COLUNA PARA OCUPAR A TELA TODA ===
        st.divider()
        
        # Se um pedido específico for selecionado, mostra o detalhamento visual
        if f1_ped != "TODOS" and not df_t1.empty:
            linha = df_t1.iloc[0]
            st.markdown(f"### 📋 Detalhes do Pedido: {f1_ped}")
            st.markdown('<div class="bloco-info">', unsafe_allow_html=True)
            st.write(f"🏢 **FILIAL:** {linha['FILIAL']} | 📊 **CENTRO DE CUSTO:** {linha['CENTRO DE CUSTO']}")
            st.write(f"💰 **FRETE:** R$ {linha['VLR DO FRETE']:,.2f} | 📄 **NOTA:** R$ {linha['VALOR DA NOTA']:,.2f}")
            st.write(f"📤 **ORIGEM:** {linha['CIDADE ORIGEM']} ➡️ 📥 **DESTINO:** {linha['CIDADE DESTINO']}")
            
            d_col = linha['DATA COLETA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA COLETA']) else 'N/A'
            d_pre = linha['DATA DE PREVISÃO DE ENTREGA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA DE PREVISÃO DE ENTREGA']) else 'N/A'
            d_ent = linha['DATA ENTREGUE'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA ENTREGUE']) else 'N/A'
            
            st.write(f"📅 **COLETA:** {d_col} | **PREVISÃO:** {d_pre} | **DATA ENTREGA:** {d_ent}")
            
            obs_texto = str(linha['OBSERVAÇÃO']).strip().upper()
            if pd.isna(linha['OBSERVAÇÃO']) or obs_texto in ["NAN", "NÃO INFORMADO", "NONE", ""]: obs_texto = "NÃO INFORMADA"
            st.write(f"📝 **OBSERVAÇÃO:** {obs_texto}")
            
            if linha['PERFORMANCE_SLA'] == 'NO PRAZO': st.markdown('<div class="badge-excelente">✅ NO PRAZO</div>', unsafe_allow_html=True)
            elif linha['PERFORMANCE_SLA'] == 'ATRASADO': st.markdown('<div class="badge-ruim">🚨 ATRASADO</div>', unsafe_allow_html=True)
            else: st.markdown('<div class="badge-andamento">⏳ EM ANDAMENTO</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            st.write("")

        # A famosa Linha de Dados / Tabela (Ocupando a largura total)
        st.markdown("### 📋 Diário de Bordo (Tabela de Dados Filtrada)")
        st.dataframe(df_t1.drop(columns=['ID_INTERNO', 'lat_o', 'lon_o', 'lat_d', 'lon_d'], errors='ignore'), use_container_width=True, height=400)
    else:
        st.info("👆 Por favor, faça o upload de uma folha de cálculo para iniciar.")

# ==========================================
# PÁGINA 2: MAPA DE CALOR E SLA
# ==========================================
with tab2:
    if not df.empty:
        st.markdown("<h4 style='color: #1C83E1;'>🧭 Filtros de Rastreamento Total</h4>", unsafe_allow_html=True)
        
        cf1, cf2, cf3 = st.columns(3)
        f2_dt_inicio = cf1.date_input("Período Coleta (De)", value=None, key="p2_dt_ini")
        f2_dt_fim = cf2.date_input("Período Coleta (Até)", value=None, key="p2_dt_fim")
        f2_sla = cf3.selectbox("🚥 Status SLA", ["TODOS", "NO PRAZO", "ATRASADO", "EM ANDAMENTO"], key="p2_sla") 

        c1, c2, c3, c4 = st.columns(4)
        f2_ped = c1.selectbox("📌 Nº de Pedido", ["TODOS"] + sorted(df['Nº DE PEDIDO'].unique()), key="p2_ped")
        f2_tra = c2.selectbox("🏢 Transportadora", ["TODAS"] + sorted(df['TRANSPORTADORA'].unique()), key="p2_tra")
        f2_ccusto = c3.selectbox("📊 Centro de Custo", ["TODOS"] + sorted(df['CENTRO DE CUSTO'].astype(str).unique()), key="p2_cc")
        f2_filial = c4.selectbox("🏢 Filial", ["TODAS"] + sorted(df['FILIAL'].astype(str).unique()), key="p2_fil")

        df_t2 = df.copy()
        if f2_dt_inicio: df_t2 = df_t2[df_t2['DATA COLETA'].dt.date >= f2_dt_inicio]
        if f2_dt_fim: df_t2 = df_t2[df_t2['DATA COLETA'].dt.date <= f2_dt_fim]
        if f2_sla != "TODOS": df_t2 = df_t2[df_t2['PERFORMANCE_SLA'] == f2_sla]
        if f2_ped != "TODOS": df_t2 = df_t2[df_t2['Nº DE PEDIDO'] == f2_ped]
        if f2_tra != "TODAS": df_t2 = df_t2[df_t2['TRANSPORTADORA'] == f2_tra]
        if f2_ccusto != "TODOS": df_t2 = df_t2[df_t2['CENTRO DE CUSTO'].astype(str) == f2_ccusto]
        if f2_filial != "TODAS": df_t2 = df_t2[df_t2['FILIAL'].astype(str) == f2_filial]

        st.write("")
        col_mapa, col_dados = st.columns([6, 4], gap="large")
        
        sem_filtro = (f2_ped == "TODOS" and f2_tra == "TODAS" and f2_sla == "TODOS" and f2_ccusto == "TODOS" and f2_filial == "TODAS" and not f2_dt_inicio and not f2_dt_fim)

        with col_mapa:
            df_mapa = df_t2.dropna(subset=['lat_o', 'lon_o', 'lat_d', 'lon_d']).copy()
            
            if not df_mapa.empty:
                fig_mapa = go.Figure()
                
                if sem_filtro:
                    st.markdown("**📍 Mapa de Calor (Volume Geral de Entregas)**")
                    fig_mapa.add_trace(go.Densitymapbox(
                        lat=df_mapa['lat_d'], lon=df_mapa['lon_d'], z=[1] * len(df_mapa),
                        radius=25, colorscale='Inferno', showscale=False
                    ))
                else:
                    st.markdown("**🛣️ Rotas de Entrega Reais (Cores do SLA)**")
                    
                    cores_rotas = {'NO PRAZO': '#00C49F', 'ATRASADO': '#FF4B4B', 'EM ANDAMENTO': '#FFA500', 'SEM PREVISÃO': '#808080'}
                    
                    for status, cor in cores_rotas.items():
                        df_status = df_mapa[df_mapa['PERFORMANCE_SLA'] == status]
                        if not df_status.empty:
                            rotas_unicas = df_status[['lat_o', 'lon_o', 'lat_d', 'lon_d']].drop_duplicates()
                            
                            lats, lons = [], []
                            for _, rota in rotas_unicas.iterrows():
                                ro_lons, ro_lats, _ = obter_rota_rodoviaria(rota['lon_o'], rota['lat_o'], rota['lon_d'], rota['lat_d'])
                                
                                if ro_lons: 
                                    lons.extend(ro_lons + [None])
                                    lats.extend(ro_lats + [None])
                                else: 
                                    lons.extend([rota['lon_o'], rota['lon_d'], None])
                                    lats.extend([rota['lat_o'], rota['lat_d'], None])
                            
                            fig_mapa.add_trace(go.Scattermapbox(
                                mode="lines", lon=lons, lat=lats,
                                line=dict(width=3, color=cor),
                                name=status, hoverinfo='none'
                            ))
                    
                    fig_mapa.add_trace(go.Scattermapbox(
                        mode="markers", lon=df_mapa['lon_o'], lat=df_mapa['lat_o'],
                        marker=dict(size=8, color="#1C83E1"), text="Origem", hoverinfo='text'
                    ))
                    fig_mapa.add_trace(go.Scattermapbox(
                        mode="markers", lon=df_mapa['lon_d'], lat=df_mapa['lat_d'],
                        marker=dict(size=8, color="#808080"), text="Destino", hoverinfo='text'
                    ))
                
                fig_mapa.update_layout(
                    margin={"r":0,"t":0,"l":0,"b":0},
                    mapbox=dict(style="carto-darkmatter", center=dict(lon=-52.0, lat=-14.0), zoom=3.5),
                    showlegend=False
                )
                st.plotly_chart(fig_mapa, use_container_width=True)
            else:
                st.warning("⚠️ O mapa não possui rotas válidas para os filtros selecionados.")

        with col_dados:
            if f2_tra != "TODAS":
                qtd_atraso = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'ATRASADO'])
                qtd_no_prazo = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'NO PRAZO'])
                total_validos = qtd_atraso + qtd_no_prazo
                otd = (qtd_no_prazo / total_validos) * 100 if total_validos > 0 else -1
                nota_text, cor_nota, icone, msg_nota = get_otd_info(otd)

                if otd >= 0:
                    st.markdown(f"""
                    <div style='background-color: {cor_nota}15; border-left: 5px solid {cor_nota}; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                        <h5 style='color: {cor_nota}; margin-top: 0;'>{icone} Performance SLA: {nota_text}</h5>
                        <h2 style='color: {cor_nota}; margin: 10px 0;'>OTD: {otd:.1f}%</h2>
                        <p style='margin-bottom: 0; font-size: 0.95em;'><strong>Direcionamento:</strong> {msg_nota}</p>
                    </div>
                    """, unsafe_allow_html=True)

            tem_pedido_unico = (f2_ped != "TODOS" and not df_t2.empty)
            if tem_pedido_unico:
                linha = df_t2.iloc[0]
                st.markdown('<div class="bloco-info">', unsafe_allow_html=True)
                st.markdown(f"##### Detalhes da Rota (Pedido: {f2_ped})")
                st.write(f"🏢 **FILIAL:** {linha['FILIAL']}")
                st.write(f"💰 **FRETE:** R$ {linha['VLR DO FRETE']:,.2f} | 📄 **NOTA:** R$ {linha['VALOR DA NOTA']:,.2f}")
                st.write(f"📤 **ORIGEM:** {linha['CIDADE ORIGEM']} | 📥 **DESTINO:** {linha['CIDADE DESTINO']}")
                
                _, _, dist_km = obter_rota_rodoviaria(linha['lon_o'], linha['lat_o'], linha['lon_d'], linha['lat_d'])
                if dist_km is not None:
                    st.write(f"🛣️ **DISTÂNCIA:** {dist_km:,.0f} km (Rota Real via Rodovias)".replace(',', '.'))
                else:
                    dist_km = calcular_distancia_reta(linha['lat_o'], linha['lon_o'], linha['lat_d'], linha['lon_d'])
                    st.write(f"📏 **DISTÂNCIA:** {dist_km:,.0f} km (Estimativa em Linha Reta)".replace(',', '.')) if dist_km else None
                
                d_col = linha['DATA COLETA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA COLETA']) else 'N/A'
                d_pre = linha['DATA DE PREVISÃO DE ENTREGA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA DE PREVISÃO DE ENTREGA']) else 'N/A'
                d_ent = linha['DATA ENTREGUE'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA ENTREGUE']) else 'N/A'
                
                st.write(f"📅 **COLETA:** {d_col} | **PREVISÃO:** {d_pre} | **DATA ENTREGA:** {d_ent}")
                
                obs_texto = str(linha['OBSERVAÇÃO']).strip().upper()
                if pd.isna(linha['OBSERVAÇÃO']) or obs_texto in ["NAN", "NÃO INFORMADO", "NONE", ""]: obs_texto = "NÃO INFORMADA"
                st.write(f"📝 **OBSERVAÇÃO:** {obs_texto}")
                
                if linha['PERFORMANCE_SLA'] == 'NO PRAZO': st.markdown('<div class="badge-excelente">✅ NO PRAZO</div>', unsafe_allow_html=True)
                elif linha['PERFORMANCE_SLA'] == 'ATRASADO': st.markdown('<div class="badge-ruim">🚨 ATRASADO</div>', unsafe_allow_html=True)
                else: st.markdown('<div class="badge-andamento">⏳ EM ANDAMENTO</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown(f"##### Volume Geral de Entregas")
                df_pie_sla = df_t2['PERFORMANCE_SLA'].value_counts().reset_index()
                df_pie_sla.columns = ['PERFORMANCE', 'CONTAGEM']
                cores_sla = {'NO PRAZO': '#00C49F', 'ATRASADO': '#FF4B4B', 'EM ANDAMENTO': '#FFA500', 'SEM PREVISÃO': '#808080'}
                fig_sla = px.pie(df_pie_sla, values='CONTAGEM', names='PERFORMANCE', color='PERFORMANCE', color_discrete_map=cores_sla, hole=0.3)
                fig_sla.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.plotly_chart(fig_sla, use_container_width=True)

        st.divider()
        st.markdown("### 📋 Detalhamento das Entregas (Filtrado)")
        st.dataframe(df_t2.drop(columns=['ID_INTERNO', 'lat_o', 'lon_o', 'lat_d', 'lon_d'], errors='ignore'), use_container_width=True, height=400)

# ==========================================
# PÁGINA 3: RANKING ESTRATÉGICO
# ==========================================
with tab3:
    if not df.empty:
        st.markdown("<h4 style='color: #1C83E1;'>🏆 Quadro de Líderes (Ranking)</h4>", unsafe_allow_html=True)
        
        cr_f1, cr_f2, cr_f3, cr_f4 = st.columns(4)
        f3_dt_inicio = cr_f1.date_input("Período Coleta (De)", value=None, key="p3_dt_ini")
        f3_dt_fim = cr_f2.date_input("Período Coleta (Até)", value=None, key="p3_dt_fim")
        f3_filial = cr_f3.selectbox("Filial", ["TODAS"] + sorted(df['FILIAL'].astype(str).unique()), key="p3_filial")
        f3_sla_rank = cr_f4.selectbox("Performance OTIF / SLA", ["TODOS", "EXCELENTE (>= 95%)", "BOA (85% a 94%)", "ALERTA (70% a 84%)", "CRÍTICA (< 70%)"], key="p3_sla")
        
        df_t3 = df.copy()
        if f3_dt_inicio: df_t3 = df_t3[df_t3['DATA COLETA'].dt.date >= f3_dt_inicio]
        if f3_dt_fim: df_t3 = df_t3[df_t3['DATA COLETA'].dt.date <= f3_dt_fim]
        if f3_filial != "TODAS": df_t3 = df_t3[df_t3['FILIAL'].astype(str) == f3_filial]
        
        cr1, cr2 = st.columns(2)
        with cr1:
            rank_vol = df_t3.groupby('TRANSPORTADORA')['Nº DE PEDIDO'].nunique().reset_index().sort_values('Nº DE PEDIDO', ascending=True) 
            fig_rank_vol = px.bar(rank_vol, y='TRANSPORTADORA', x='Nº DE PEDIDO', orientation='h', title="🏆 Ranking Volume", color='Nº DE PEDIDO', color_continuous_scale='Blues')
            fig_rank_vol.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_rank_vol, use_container_width=True)

        with cr2:
            def calc_otd_global(grupo):
                validos = grupo[grupo['PERFORMANCE_SLA'].isin(['NO PRAZO', 'ATRASADO'])]
                if len(validos) == 0: return -1.0 
                return (len(validos[validos['PERFORMANCE_SLA'] == 'NO PRAZO']) / len(validos)) * 100
                
            rank_sla = df_t3.groupby('TRANSPORTADORA').apply(calc_otd_global).reset_index()
            rank_sla.columns = ['TRANSPORTADORA', 'OTD_PERCENTUAL']
            rank_sla = rank_sla[rank_sla['OTD_PERCENTUAL'] >= 0] 
            rank_sla['CLASSIFICAÇÃO'] = rank_sla['OTD_PERCENTUAL'].apply(lambda x: get_otd_info(x)[0])
            
            if f3_sla_rank == "EXCELENTE (>= 95%)": rank_sla = rank_sla[rank_sla['CLASSIFICAÇÃO'] == 'EXCELENTE']
            elif f3_sla_rank == "BOA (85% a 94%)": rank_sla = rank_sla[rank_sla['CLASSIFICAÇÃO'] == 'BOA']
            elif f3_sla_rank == "ALERTA (70% a 84%)": rank_sla = rank_sla[rank_sla['CLASSIFICAÇÃO'] == 'ALERTA']
            elif f3_sla_rank == "CRÍTICA (< 70%)": rank_sla = rank_sla[rank_sla['CLASSIFICAÇÃO'] == 'CRÍTICA']
            
            rank_sla = rank_sla.sort_values('OTD_PERCENTUAL', ascending=True) 
            mapa_cores = {'EXCELENTE': '#00C49F', 'BOA': '#1C83E1', 'ALERTA': '#FFA500', 'CRÍTICA': '#FF4B4B'}
            
            fig_rank_sla = px.bar(rank_sla, y='TRANSPORTADORA', x='OTD_PERCENTUAL', orientation='h', title="⭐ Ranking de SLA Logístico (OTD %)", color='CLASSIFICAÇÃO', color_discrete_map=mapa_cores)
            fig_rank_sla.update_layout(xaxis_title="% Entregas no Prazo", margin=dict(l=0, r=0, t=40, b=0), showlegend=True)
            st.plotly_chart(fig_rank_sla, use_container_width=True)
    else:
        st.info("👆 Por favor, faça o upload de uma folha de cálculo para gerar os rankings.")
