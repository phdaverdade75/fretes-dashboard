import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import uuid

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
# 2. MOTOR DO BANCO DE DADOS (ULTRA-RÁPIDO)
# ==========================================
ARQUIVO_DB = "banco_fretes_final.csv"

# Coordenadas estáticas embutidas para carregamento em 0.001 segundos (Sem satélite externo)
COORDENADAS_ESTADOS = {
    'AC': (-9.0238, -70.8120), 'AL': (-9.5328, -36.6698), 'AP': (1.4192, -51.7792),
    'AM': (-3.4168, -65.8561), 'BA': (-12.5797, -41.7007), 'CE': (-5.4984, -39.3206),
    'DF': (-15.7998, -47.8645), 'ES': (-19.1834, -40.3089), 'GO': (-15.8270, -49.8362),
    'MA': (-4.9609, -45.2744), 'MT': (-12.6819, -56.9211), 'MS': (-20.7722, -54.3647),
    'MG': (-18.5122, -44.5550), 'PA': (-1.9981, -54.9306), 'PB': (-7.2399, -36.7820),
    'PR': (-25.2521, -52.0215), 'PE': (-8.8137, -36.9541), 'PI': (-7.7183, -42.7289),
    'RJ': (-22.9094, -43.2094), 'RN': (-5.7945, -36.5664), 'RS': (-30.0346, -51.2177),
    'RO': (-11.5057, -63.5806), 'RR': (2.7376, -62.0751), 'SC': (-27.2423, -50.2189),
    'SP': (-23.5505, -46.6333), 'SE': (-10.5741, -37.3857), 'TO': (-10.1843, -48.3336),
    'SAO PAULO': (-23.5505, -46.6333), 'MINAS GERAIS': (-18.5122, -44.5550), 
    'RIO DE JANEIRO': (-22.9094, -43.2094), 'BAHIA': (-12.5797, -41.7007),
    'PARANA': (-25.2521, -52.0215), 'RIO GRANDE DO SUL': (-30.0346, -51.2177),
    'SANTA CATARINA': (-27.2423, -50.2189), 'GOIAS': (-15.8270, -49.8362)
}

COLUNAS_PADRAO = [
    'ID_INTERNO', 'TRANSPORTADORA', 'CHAMADO DE FRETE / Nº PROCESSO', 'NUMERO DA NOTA', 
    'VALOR DA NOTA', 'CENTRO DE CUSTO', 'Nº DE PEDIDO', 'FILIAL', 'DATA COLETA', 
    'SOLICITANTE DO CHAMADO', 'EMAIL SOLICITANTE', 'STATUS FRETES', 'VLR DO FRETE', 
    'CIDADE ORIGEM', 'ESTADO ORIGEM', 'CIDADE DESTINO', 'ESTADO DESTINO', 'VEÍCULO', 
    'DOCUMENTO', 'MEDIÇÃO/SUPRIMENTOS', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE', 'OBSERVAÇÃO'
]

if 'banco_dados' not in st.session_state:
    if os.path.exists(ARQUIVO_DB):
        st.session_state.banco_dados = pd.read_csv(ARQUIVO_DB)
        for col in ['DATA COLETA', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE']:
            if col in st.session_state.banco_dados.columns:
                st.session_state.banco_dados[col] = pd.to_datetime(st.session_state.banco_dados[col], errors='coerce')
    else:
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

# ==========================================
# 3. CABEÇALHO E UPLOAD
# ==========================================
st.title("🚚 FRETES ANALYTICS V1.0")
st.caption("Painel Executivo de Gestão Logística")

with st.expander("📥 Importar Dados (Atualizar Base)"):
    col_up, col_btn = st.columns([8, 2])
    with col_up:
        arq_upload = st.file_uploader("Subir Planilha Matriz (.xlsx, .xlsb)", type=["xlsx", "xlsb", "xls"], label_visibility="collapsed")
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
                        df_limpo.to_csv(ARQUIVO_DB, index=False)
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
    df['CIDADE/UF_ORIGEM'] = df['CIDADE ORIGEM'] + ", " + df['ESTADO ORIGEM']
    df['CIDADE/UF_DESTINO'] = df['CIDADE DESTINO'] + ", " + df['ESTADO DESTINO']
    
    # Mapeamento Instantâneo sem internet
    df['lat_o'] = df['ESTADO ORIGEM'].map(lambda x: COORDENADAS_ESTADOS.get(str(x).upper(), (None, None))[0])
    df['lon_o'] = df['ESTADO ORIGEM'].map(lambda x: COORDENADAS_ESTADOS.get(str(x).upper(), (None, None))[1])
    df['lat_d'] = df['ESTADO DESTINO'].map(lambda x: COORDENADAS_ESTADOS.get(str(x).upper(), (None, None))[0])
    df['lon_d'] = df['ESTADO DESTINO'].map(lambda x: COORDENADAS_ESTADOS.get(str(x).upper(), (None, None))[1])

# ==========================================
# NAVEGAÇÃO ENTRE ABAS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 Visão Global", "🗺️ Mapa & SLA Logístico", "🏆 Ranking de Transportadoras"])

# ==========================================
# PÁGINA 1: DASHBOARD
# ==========================================
with tab1:
    if not df.empty:
        col_filtros, col_conteudo = st.columns([2.5, 7.5], gap="large")
        
        with col_filtros:
            st.markdown("<h4 style='color: #1C83E1;'>🔎 Filtros de Análise</h4>", unsafe_allow_html=True)
            
            f_dt_inicio = st.date_input("Data Coleta (A partir de)", value=None, key="p1_dt_ini")
            f_dt_fim = st.date_input("Data Coleta (Até)", value=None, key="p1_dt_fim")
            
            opcoes_pedidos_p1 = ["TODOS"] + sorted(df['Nº DE PEDIDO'].unique())
            f_ped_p1 = st.selectbox("Nº Pedido", opcoes_pedidos_p1, key="p1_ped")
            
            f_filial = st.multiselect("Filial", sorted(df['FILIAL'].unique()))
            f_transp = st.multiselect("Transportadora", sorted(df['TRANSPORTADORA'].unique()))
            f_vei = st.multiselect("Veículo", sorted(df['VEÍCULO'].unique()))

        df_t1 = df.copy()
        if f_dt_inicio: df_t1 = df_t1[df_t1['DATA COLETA'].dt.date >= f_dt_inicio]
        if f_dt_fim: df_t1 = df_t1[df_t1['DATA COLETA'].dt.date <= f_dt_fim]
        if f_ped_p1 != "TODOS": df_t1 = df_t1[df_t1['Nº DE PEDIDO'] == f_ped_p1]
        
        if f_filial: df_t1 = df_t1[df_t1['FILIAL'].isin(f_filial)]
        if f_transp: df_t1 = df_t1[df_t1['TRANSPORTADORA'].isin(f_transp)]
        if f_vei: df_t1 = df_t1[df_t1['VEÍCULO'].isin(f_vei)]

        with col_conteudo:
            st.markdown("#### Resumo da Operação")
            v1, v2 = st.columns(2)
            v1.metric("💰 Valor Total de Fretes", f"R$ {df_t1['VLR DO FRETE'].sum():,.2f}")
            v2.metric("📋 Indicador Responsável", "Pedro Anjos")
            
            st.divider()
            
            cg1, cg2 = st.columns(2)
            with cg1:
                top5_transp = df_t1['TRANSPORTADORA'].value_counts().nlargest(5).reset_index()
                top5_transp.columns = ['TRANSPORTADORA', 'QTD']
                top5_transp = top5_transp.sort_values('QTD', ascending=True) 
                fig_top5 = px.bar(top5_transp, y='TRANSPORTADORA', x='QTD', orientation='h', 
                                  title="Top 5 Transportadoras (Qtd. Fretes)", color='QTD', color_continuous_scale='Blues')
                fig_top5.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_top5, use_container_width=True)

            with cg2:
                df_filial_gasto = df_t1.groupby('FILIAL')['VLR DO FRETE'].sum().reset_index().sort_values('VLR DO FRETE', ascending=True)
                fig_filial = px.bar(df_filial_gasto, y='FILIAL', x='VLR DO FRETE', orientation='h', 
                                    title="Valor Total de Frete por Filial", color='VLR DO FRETE', color_continuous_scale='Teal')
                fig_filial.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_filial, use_container_width=True)
            
            st.write("")
            
            df_med_gasto = df_t1.groupby('MEDIÇÃO/SUPRIMENTOS')['VLR DO FRETE'].sum().reset_index()
            fig_med_sup = px.pie(df_med_gasto, values='VLR DO FRETE', names='MEDIÇÃO/SUPRIMENTOS', hole=0.4, 
                                 title="Medição x Suprimentos (Custo)")
            fig_med_sup.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig_med_sup, use_container_width=True)
            
            st.divider()
            st.markdown("### 📋 Detalhamento de Dados")
            st.dataframe(df_t1.drop(columns=['ID_INTERNO', 'lat_o', 'lon_o', 'lat_d', 'lon_d', 'CIDADE/UF_ORIGEM', 'CIDADE/UF_DESTINO'], errors='ignore'), use_container_width=True, height=400)
    else:
        st.info("👆 Importe a planilha para visualizar os dados.")

# ==========================================
# PÁGINA 2: MAPA TRAÇADO E SLA
# ==========================================
with tab2:
    if not df.empty:
        st.markdown("<h4 style='color: #1C83E1;'>🧭 Filtros de Rastreamento</h4>", unsafe_allow_html=True)
        
        cf1, cf2, cf3 = st.columns(3)
        f2_dcoleta = cf1.date_input("Data Coleta (Até)", value=None, key="p2_dt_col")
        f2_dentrega = cf2.date_input("Data Entrega (Até)", value=None, key="p2_dt_ent")
        
        opcoes_sla = ["TODOS", "NO PRAZO", "ATRASADO", "EM ANDAMENTO"]
        f2_sla = cf3.selectbox("🚥 Status SLA", opcoes_sla, key="p2_sla") 

        c1, c2, c3, c4 = st.columns(4)
        opcoes_pedidos = ["TODOS"] + sorted(df['Nº DE PEDIDO'].unique())
        opcoes_transp = ["TODOS"] + sorted(df['TRANSPORTADORA'].unique())
        opcoes_ccusto = ["TODOS"] + sorted(df['CENTRO DE CUSTO'].astype(str).unique())
        opcoes_filial = ["TODOS"] + sorted(df['FILIAL'].astype(str).unique())
        
        f2_ped = c1.selectbox("📌 Nº de Pedido", opcoes_pedidos, key="p2_ped")
        f2_tra = c2.selectbox("🏢 Transportadora", opcoes_transp, key="p2_tra")
        f2_ccusto = c3.selectbox("📊 Centro de Custo", opcoes_ccusto, key="p2_cc")
        f2_filial = c4.selectbox("🏢 Filial", opcoes_filial, key="p2_fil")

        df_t2 = df.copy()
        
        if f2_dcoleta: df_t2 = df_t2[df_t2['DATA COLETA'].dt.date <= f2_dcoleta]
        if f2_dentrega: df_t2 = df_t2[df_t2['DATA ENTREGUE'].dt.date <= f2_dentrega]
        if f2_sla != "TODOS": df_t2 = df_t2[df_t2['PERFORMANCE_SLA'] == f2_sla]
        if f2_ped != "TODOS": df_t2 = df_t2[df_t2['Nº DE PEDIDO'] == f2_ped]
        if f2_tra != "TODOS": df_t2 = df_t2[df_t2['TRANSPORTADORA'] == f2_tra]
        if f2_ccusto != "TODOS": df_t2 = df_t2[df_t2['CENTRO DE CUSTO'].astype(str) == f2_ccusto]
        if f2_filial != "TODOS": df_t2 = df_t2[df_t2['FILIAL'].astype(str) == f2_filial]

        st.write("")
        col_mapa, col_dados = st.columns([6, 4], gap="large")
        
        with col_mapa:
            st.markdown("**Rotas de Frete (Mapa Tracejado Rápido)**")
            
            df_mapa = df_t2.dropna(subset=['lat_o', 'lon_o', 'lat_d', 'lon_d']).copy()
            
            if not df_mapa.empty:
                lats, lons = [], []
                for _, row in df_mapa.iterrows():
                    lats.extend([row['lat_o'], row['lat_d'], None])
                    lons.extend([row['lon_o'], row['lon_d'], None])
                
                fig_mapa = go.Figure(go.Scattermapbox(
                    mode="lines+markers", lon=lons, lat=lats,
                    marker={'size': 8, 'color': '#00C49F'},
                    line={'width': 2, 'color': '#1C83E1'}
                ))
                
                fig_mapa.update_layout(
                    margin={"r":0,"t":0,"l":0,"b":0},
                    mapbox={
                        'style': "carto-positron",
                        'center': {'lon': -52.0, 'lat': -14.0},
                        'zoom': 3
                    },
                    showlegend=False
                )
                st.plotly_chart(fig_mapa, use_container_width=True)
            else:
                st.info("O filtro atual não possui destinos mapeados ou a base está vazia.")

        with col_dados:
            tem_pedido_unico = (f2_ped != "TODOS" and not df_t2.empty)
            if tem_pedido_unico:
                linha = df_t2.iloc[0]
                st.markdown('<div class="bloco-info">', unsafe_allow_html=True)
                st.markdown(f"##### Detalhes da Rota (Pedido: {f2_ped})")
                st.write(f"🏢 **FILIAL:** {linha['FILIAL']} | **C. CUSTO:** {linha['CENTRO DE CUSTO']}")
                st.write(f"💰 **FRETE:** R$ {linha['VLR DO FRETE']:,.2f} | 📄 **NOTA:** R$ {linha['VALOR DA NOTA']:,.2f}")
                st.write(f"📤 **ORIGEM:** {linha['CIDADE/UF_ORIGEM']}")
                st.write(f"📥 **DESTINO:** {linha['CIDADE/UF_DESTINO']}")
                
                d_col = linha['DATA COLETA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA COLETA']) else 'N/A'
                d_pre = linha['DATA DE PREVISÃO DE ENTREGA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA DE PREVISÃO DE ENTREGA']) else 'N/A'
                d_ent = linha['DATA ENTREGUE'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA ENTREGUE']) else 'N/A'
                
                st.write(f"📅 **COLETA:** {d_col} | **PREVISÃO:** {d_pre} | **ENTREGUE:** {d_ent}")
                
                obs_texto = str(linha['OBSERVAÇÃO']).strip()
                if not pd.isna(linha['OBSERVAÇÃO']) and obs_texto not in ["nan", "NÃO INFORMADO", "None", ""]:
                    st.write(f"📝 **OBSERVAÇÃO:** {obs_texto}")
                
                if linha['PERFORMANCE_SLA'] == 'NO PRAZO': st.markdown('<div class="badge-excelente">✅ NO PRAZO</div>', unsafe_allow_html=True)
                elif linha['PERFORMANCE_SLA'] == 'ATRASADO': st.markdown('<div class="badge-ruim">🚨 ATRASADO</div>', unsafe_allow_html=True)
                else: st.markdown('<div class="badge-andamento">⏳ EM ANDAMENTO</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                if f2_tra != "TODOS":
                    qtd_atraso = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'ATRASADO'])
                    qtd_no_prazo = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'NO PRAZO'])
                    total_validos = qtd_atraso + qtd_no_prazo

                    if total_validos > 0:
                        otd = (qtd_no_prazo / total_validos) * 100
                        cor_nota = "#00C49F" if otd >= 95 else "#1C83E1" if otd >= 85 else "#FFA500" if otd >= 70 else "#FF4B4B"
                        icone = "🟢" if otd >= 95 else "🔵" if otd >= 85 else "🟡" if otd >= 70 else "🔴"
                        nota_text = "EXCELENTE" if otd >= 95 else "BOA" if otd >= 85 else "ALERTA" if otd >= 70 else "CRÍTICA"

                        st.markdown(f"""
                        <div style='background-color: {cor_nota}15; border-left: 5px solid {cor_nota}; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                            <h5 style='color: {cor_nota}; margin-top: 0;'>{icone} Avaliação: {nota_text}</h5>
                            <h3 style='color: {cor_nota}; margin: 10px 0;'>OTD: {otd:.1f}%</h3>
                        </div>
                        """, unsafe_allow_html=True)

                st.markdown(f"##### Performance de Entregas")
                df_pie_sla = df_t2['PERFORMANCE_SLA'].value_counts().reset_index()
                df_pie_sla.columns = ['PERFORMANCE', 'CONTAGEM']
                cores_sla = {'NO PRAZO': '#00C49F', 'ATRASADO': '#FF4B4B', 'EM ANDAMENTO': '#FFA500', 'SEM PREVISÃO': '#808080'}
                fig_sla = px.pie(df_pie_sla, values='CONTAGEM', names='PERFORMANCE', color='PERFORMANCE', color_discrete_map=cores_sla, hole=0.3)
                fig_sla.update_layout(margin=dict(t=20, b=20, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.plotly_chart(fig_sla, use_container_width=True)

# ==========================================
# PÁGINA 3: RANKING DE TRANSPORTADORAS
# ==========================================
with tab3:
    if not df.empty:
        st.markdown("<h4 style='color: #1C83E1;'>🏆 Quadro de Líderes (Ranking)</h4>", unsafe_allow_html=True)
        
        cf_r1, cf_r2 = st.columns(2)
        
        opcoes_filial_rank = ["TODAS"] + sorted(df['FILIAL'].astype(str).unique())
        f_filial_rank = cf_r1.selectbox("Filtrar por Filial", opcoes_filial_rank, key="p3_filial")
        
        opcoes_otif = ["TODOS", "ADERENTES (>= 95%)", "CRÍTICOS (< 70%)"]
        f_otif_rank = cf_r2.selectbox("Performance OTIF / SLA", opcoes_otif, key="p3_otif")
        
        df_t3 = df.copy()
        if f_filial_rank != "TODAS":
            df_t3 = df_t3[df_t3['FILIAL'].astype(str) == f_filial_rank]
        
        cr1, cr2 = st.columns(2)
        
        with cr1:
            rank_vol = df_t3.groupby('TRANSPORTADORA')['Nº DE PEDIDO'].nunique().reset_index()
            rank_vol = rank_vol.sort_values('Nº DE PEDIDO', ascending=True) 
            fig_rank_vol = px.bar(rank_vol, y='TRANSPORTADORA', x='Nº DE PEDIDO', orientation='h', 
                                  title="🏆 Ranking de Volume", color='Nº DE PEDIDO', color_continuous_scale='Blues')
            fig_rank_vol.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_rank_vol, use_container_width=True)

        with cr2:
            def calc_otd_global(grupo):
                validos = grupo[grupo['PERFORMANCE_SLA'].isin(['NO PRAZO', 'ATRASADO'])]
                if len(validos) == 0: return 0.0
                return (len(validos[validos['PERFORMANCE_SLA'] == 'NO PRAZO']) / len(validos)) * 100
                
            rank_sla = df_t3.groupby('TRANSPORTADORA').apply(calc_otd_global).reset_index()
            rank_sla.columns = ['TRANSPORTADORA', 'OTD_PERCENTUAL']
            rank_sla = rank_sla[rank_sla['OTD_PERCENTUAL'] > 0]
            
            if f_otif_rank == "ADERENTES (>= 95%)":
                rank_sla = rank_sla[rank_sla['OTD_PERCENTUAL'] >= 95.0]
            elif f_otif_rank == "CRÍTICOS (< 70%)":
                rank_sla = rank_sla[rank_sla['OTD_PERCENTUAL'] < 70.0]
                
            rank_sla = rank_sla.sort_values('OTD_PERCENTUAL', ascending=True) 
            
            fig_rank_sla = px.bar(rank_sla, y='TRANSPORTADORA', x='OTD_PERCENTUAL', orientation='h', 
                                  title="⭐ Ranking de SLA (OTD %)", color='OTD_PERCENTUAL', color_continuous_scale='RdYlGn')
            fig_rank_sla.update_layout(xaxis_title="% Entregas no Prazo", margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_rank_sla, use_container_width=True)

    else:
        st.info("Sincronize os dados para visualizar o ranking.")
