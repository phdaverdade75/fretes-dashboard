import streamlit as st
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
import pydeck as pdk
import io
import os
import uuid
from datetime import datetime

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
# 2. MOTOR DO BANCO DE DADOS E GEOCODIFICAÇÃO
# ==========================================
ARQUIVO_DB = "banco_fretes_v10.csv"

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
        'DATA ENTREGA': 'DATA ENTREGUE',
        'OBSERVACAO': 'OBSERVAÇÃO'
    }
    df.rename(columns=mapeamento, inplace=True)

    if 'Nº DE PEDIDO' not in df.columns: return df, False, "Erro de Coluna"
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

@st.cache_data(show_spinner=False)
def obter_coords(cidades_uf):
    geo = Nominatim(user_agent="app_fretes_orguel_v10")
    limitado = RateLimiter(geo.geocode, min_delay_seconds=0.1)
    coords = {}
    for cid_uf in cidades_uf:
        if cid_uf and 'NÃO INFORMADO' not in cid_uf:
            try:
                loc = limitado(f"{cid_uf}, Brasil")
                if loc: coords[cid_uf] = (loc.latitude, loc.longitude)
            except: pass
    return coords

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
                    df_temp = pd.read_excel(arq_upload, engine=motor, sheet_name=0)
                    df_limpo, sucesso, msg = limpar_dados(df_temp)
                    if sucesso:
                        st.session_state.banco_dados = df_limpo
                        df_limpo.to_csv(ARQUIVO_DB, index=False)
                        st.success("Dados sincronizados com sucesso!")
                        st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

st.divider()
df = st.session_state.banco_dados

if not df.empty:
    df['PERFORMANCE_SLA'] = df.apply(avaliar_prazo, axis=1)
    df['CIDADE/UF_ORIGEM'] = df['CIDADE ORIGEM'] + ", " + df['ESTADO ORIGEM']
    df['CIDADE/UF_DESTINO'] = df['CIDADE DESTINO'] + ", " + df['ESTADO DESTINO']
    
    # Processamento de Coordenadas para o Mapa Traçado
    todas_cidades = pd.concat([df['CIDADE/UF_ORIGEM'], df['CIDADE/UF_DESTINO']]).unique()
    dic_coords = obter_coords(todas_cidades)
    
    df['lat_o'] = df['CIDADE/UF_ORIGEM'].map(lambda x: dic_coords.get(x, (None, None))[0])
    df['lon_o'] = df['CIDADE/UF_ORIGEM'].map(lambda x: dic_coords.get(x, (None, None))[1])
    df['lat_d'] = df['CIDADE/UF_DESTINO'].map(lambda x: dic_coords.get(x, (None, None))[0])
    df['lon_d'] = df['CIDADE/UF_DESTINO'].map(lambda x: dic_coords.get(x, (None, None))[1])

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
            f_filial = st.multiselect("Filial", sorted(df['FILIAL'].unique()))
            f_transp = st.multiselect("Transportadora", sorted(df['TRANSPORTADORA'].unique()))
            f_vei = st.multiselect("Veículo", sorted(df['VEÍCULO'].unique()))
            f_sts = st.multiselect("Status Fretes", sorted(df['STATUS FRETES'].unique()))

        df_t1 = df.copy()
        if f_filial: df_t1 = df_t1[df_t1['FILIAL'].isin(f_filial)]
        if f_transp: df_t1 = df_t1[df_t1['TRANSPORTADORA'].isin(f_transp)]
        if f_vei: df_t1 = df_t1[df_t1['VEÍCULO'].isin(f_vei)]
        if f_sts: df_t1 = df_t1[df_t1['STATUS FRETES'].isin(f_sts)]

        with col_conteudo:
            st.markdown("#### Resumo da Operação")
            # Atualizado: Retirado Cartão NF
            v1, v2, v3 = st.columns(3)
            v1.metric("💰 Valor total de frete", f"R$ {df_t1['VLR DO FRETE'].sum():,.2f}")
            v2.metric("📦 Volume (Pedidos)", df_t1['Nº DE PEDIDO'].nunique())
            v3.metric("🚚 Total Lançamentos", len(df_t1))
            
            st.divider()
            
            # NOVOS GRÁFICOS HORIZONTAIS
            cg1, cg2 = st.columns(2)
            
            with cg1:
                top5_transp = df_t1['TRANSPORTADORA'].value_counts().nlargest(5).reset_index()
                top5_transp.columns = ['TRANSPORTADORA', 'QTD']
                top5_transp = top5_transp.sort_values('QTD', ascending=True) # Para ficar no topo do gráfico
                fig_top5 = px.bar(top5_transp, y='TRANSPORTADORA', x='QTD', orientation='h', 
                                  title="Top 5 Transportadoras (Qtd. de Fretes)", color='QTD', color_continuous_scale='Blues')
                fig_top5.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_top5, use_container_width=True)

            with cg2:
                df_filial_gasto = df_t1.groupby('FILIAL')['VLR DO FRETE'].sum().reset_index().sort_values('VLR DO FRETE', ascending=True)
                fig_filial = px.bar(df_filial_gasto, y='FILIAL', x='VLR DO FRETE', orientation='h', 
                                    title="Valor total de frete por Filial", color='VLR DO FRETE', color_continuous_scale='Teal')
                fig_filial.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_filial, use_container_width=True)
            
            st.divider()
            st.markdown("### 📋 Detalhamento de Dados (Visão Global)")
            st.dataframe(df_t1.drop(columns=['ID_INTERNO', 'lat_o', 'lon_o', 'lat_d', 'lon_d', 'CIDADE/UF_ORIGEM', 'CIDADE/UF_DESTINO'], errors='ignore'), use_container_width=True, height=400)
    else:
        st.info("O Banco de Dados está vazio. Sincronize a matriz no painel acima.")

# ==========================================
# PÁGINA 2: MAPA TRAÇADO E PERFORMANCE (SLA)
# ==========================================
with tab2:
    if not df.empty:
        st.markdown("<h4 style='color: #1C83E1;'>🧭 Filtros de Rastreamento</h4>", unsafe_allow_html=True)
        
        # NOVOS FILTROS DE DATA "ATÉ"
        cf1, cf2 = st.columns(2)
        f2_dcoleta = cf1.date_input("Data Coleta (Até esta data)", value=None)
        f2_dentrega = cf2.date_input("Data Entrega (Até esta data)", value=None)

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
        
        if f2_ped != "TODOS": df_t2 = df_t2[df_t2['Nº DE PEDIDO'] == f2_ped]
        if f2_tra != "TODOS": df_t2 = df_t2[df_t2['TRANSPORTADORA'] == f2_tra]
        if f2_ccusto != "TODOS": df_t2 = df_t2[df_t2['CENTRO DE CUSTO'].astype(str) == f2_ccusto]
        if f2_filial != "TODOS": df_t2 = df_t2[df_t2['FILIAL'].astype(str) == f2_filial]

        st.write("")
        col_mapa, col_dados = st.columns([6, 4], gap="large")
        
        with col_mapa:
            st.markdown("**Rotas de Frete (Origem 🔵 -> Destino 🟢)**")
            
            # FILTRAGEM SEGURA PARA O MAPA DE ROTAS (PYDECK 3D)
            df_mapa = df_t2.dropna(subset=['lat_o', 'lon_o', 'lat_d', 'lon_d']).copy()
            
            if not df_mapa.empty:
                layer_rotas = pdk.Layer(
                    "ArcLayer",
                    data=df_mapa,
                    get_source_position=["lon_o", "lat_o"],
                    get_target_position=["lon_d", "lat_d"],
                    get_source_color=[28, 131, 225, 200],  # Azul Origem
                    get_target_color=[0, 196, 159, 200],   # Verde Destino
                    get_width=3,
                    auto_highlight=True,
                    pickable=True
                )
                
                estado_visual = pdk.ViewState(
                    latitude=df_mapa['lat_o'].mean(),
                    longitude=df_mapa['lon_o'].mean(),
                    zoom=4,
                    pitch=40
                )
                
                st.pydeck_chart(pdk.Deck(
                    layers=[layer_rotas],
                    initial_view_state=estado_visual,
                    tooltip={"text": "Rota Identificada"}
                ))
            else:
                st.warning("Nenhuma rota com coordenadas válidas para traçar o mapa com os filtros atuais.")

        with col_dados:
            tem_pedido_unico = (f2_ped != "TODOS" and not df_t2.empty)
            if tem_pedido_unico:
                linha = df_t2.iloc[0]
                st.markdown('<div class="bloco-info">', unsafe_allow_html=True)
                st.markdown(f"##### Detalhes da Rota (Pedido: {f2_ped})")
                st.write(f"🏢 **FILIAL:** {linha['FILIAL']} | **CENTRO DE CUSTO:** {linha['CENTRO DE CUSTO']}")
                st.write(f"💰 **VALOR DO FRETE:** R$ {linha['VLR DO FRETE']:,.2f} | 📄 **VALOR DA NOTA:** R$ {linha['VALOR DA NOTA']:,.2f}")
                st.write(f"📤 **ORIGEM:** {linha['CIDADE/UF_ORIGEM']}  ➔  📥 **DESTINO:** {linha['CIDADE/UF_DESTINO']}")
                
                d_col = linha['DATA COLETA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA COLETA']) else 'N/A'
                d_pre = linha['DATA DE PREVISÃO DE ENTREGA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA DE PREVISÃO DE ENTREGA']) else 'N/A'
                d_ent = linha['DATA ENTREGUE'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA ENTREGUE']) else 'N/A'
                
                st.write(f"📅 **DATA COLETA:** {d_col} | **PREVISÃO:** {d_pre} | **ENTREGUE:** {d_ent}")
                
                obs_texto = str(linha['OBSERVAÇÃO']).strip()
                if pd.isna(linha['OBSERVAÇÃO']) or obs_texto in ["nan", "NÃO INFORMADO", "None", ""]:
                    st.write("📝 **OBSERVAÇÃO:** Nenhuma observação registrada.")
                else:
                    st.write(f"📝 **OBSERVAÇÃO:** {obs_texto}")
                
                if linha['PERFORMANCE_SLA'] == 'NO PRAZO': st.markdown('<div class="badge-excelente">✅ NO PRAZO</div>', unsafe_allow_html=True)
                elif linha['PERFORMANCE_SLA'] == 'ATRASADO': st.markdown('<div class="badge-ruim">🚨 ATRASADO</div>', unsafe_allow_html=True)
                else: st.markdown('<div class="badge-andamento">⏳ EM ANDAMENTO</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                # Motor de Avaliação SLA Logístico
                if f2_tra != "TODOS":
                    qtd_atraso = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'ATRASADO'])
                    qtd_no_prazo = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'NO PRAZO'])
                    total_validos = qtd_atraso + qtd_no_prazo

                    if total_validos > 0:
                        otd = (qtd_no_prazo / total_validos) * 100
                        if otd >= 95.0:
                            nota_text = "EXCELENTE"; cor_nota = "#00C49F"; icone = "🟢"
                            msg_nota = "Transportadora altamente aderente ao SLA."
                        elif otd >= 85.0:
                            nota_text = "BOA"; cor_nota = "#1C83E1"; icone = "🔵"
                            msg_nota = "Performance estável, oportunidade de otimização."
                        elif otd >= 70.0:
                            nota_text = "ALERTA"; cor_nota = "#FFA500"; icone = "🟡"
                            msg_nota = "Necessário plano de ação para recuperação de SLA."
                        else:
                            nota_text = "CRÍTICA"; cor_nota = "#FF4B4B"; icone = "🔴"
                            msg_nota = "Performance incompatível. Avaliar substituição."

                        st.markdown(f"""
                        <div style='background-color: {cor_nota}15; border-left: 5px solid {cor_nota}; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                            <h5 style='color: {cor_nota}; margin-top: 0;'>{icone} Avaliação: {nota_text}</h5>
                            <h3 style='color: {cor_nota}; margin: 10px 0;'>OTD: {otd:.1f}%</h3>
                            <p style='margin-bottom: 0; font-size: 0.95em;'>{msg_nota}</p>
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
        st.write("Acompanhe o desempenho das transportadoras em toda a rede. Os melhores resultados figuram no topo.")
        
        cr1, cr2 = st.columns(2)
        
        with cr1:
            # Ranking de Volume (Pedidos)
            rank_vol = df.groupby('TRANSPORTADORA')['Nº DE PEDIDO'].nunique().reset_index()
            rank_vol = rank_vol.sort_values('Nº DE PEDIDO', ascending=True) # Ascending para barra horizontal exibir maior no topo
            fig_rank_vol = px.bar(rank_vol, y='TRANSPORTADORA', x='Nº DE PEDIDO', orientation='h', 
                                  title="🏆 Ranking de Volume (Total de Pedidos)", color='Nº DE PEDIDO', color_continuous_scale='Blues')
            fig_rank_vol.update_layout(margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_rank_vol, use_container_width=True)

        with cr2:
            # Ranking de SLA (OTD)
            def calc_otd_global(grupo):
                validos = grupo[grupo['PERFORMANCE_SLA'].isin(['NO PRAZO', 'ATRASADO'])]
                if len(validos) == 0: return 0.0
                return (len(validos[validos['PERFORMANCE_SLA'] == 'NO PRAZO']) / len(validos)) * 100
                
            rank_sla = df.groupby('TRANSPORTADORA').apply(calc_otd_global).reset_index()
            rank_sla.columns = ['TRANSPORTADORA', 'OTD_PERCENTUAL']
            
            # Filtra quem tem OTD e ordena do melhor (topo) para o pior
            rank_sla = rank_sla[rank_sla['OTD_PERCENTUAL'] > 0].sort_values('OTD_PERCENTUAL', ascending=True) 
            
            fig_rank_sla = px.bar(rank_sla, y='TRANSPORTADORA', x='OTD_PERCENTUAL', orientation='h', 
                                  title="⭐ Ranking de Performance Logística (OTD %)", color='OTD_PERCENTUAL', color_continuous_scale='RdYlGn')
            fig_rank_sla.update_layout(xaxis_title="% Entregas no Prazo", margin=dict(l=0, r=0, t=40, b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_rank_sla, use_container_width=True)

    else:
        st.info("Sincronize os dados para visualizar o ranking de transportadoras.")
