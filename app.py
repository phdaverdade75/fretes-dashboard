import streamlit as st
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
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
# 2. MOTOR DO BANCO DE DADOS
# ==========================================
ARQUIVO_DB = "banco_fretes_v94.csv"

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
        'DATA ENTREGA': 'DATA ENTREGUE'
    }
    df.rename(columns=mapeamento, inplace=True)

    if 'Nº DE PEDIDO' not in df.columns:
        return df, False, f"A coluna 'Nº DE PEDIDO' não foi encontrada. Colunas atuais: {list(df.columns)}"

    if 'ID_INTERNO' not in df.columns:
        df['ID_INTERNO'] = [str(uuid.uuid4()) for _ in range(len(df))]

    for col in COLUNAS_PADRAO:
        if col not in df.columns: df[col] = "NÃO INFORMADO"

    for col in COLUNAS_PADRAO:
        if col not in ['VALOR DA NOTA', 'VLR DO FRETE', 'DATA COLETA', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE', 'ID_INTERNO']:
            df[col] = df[col].astype(str).str.upper().str.strip()
            df[col] = df[col].replace(['NAN', 'NONE', 'NULL', ''], 'NÃO INFORMADO')

    for col in ['VLR DO FRETE', 'VALOR DA NOTA']:
        df[col] = df[col].astype(str).str.replace('R$', '', regex=False).str.replace(',', '.', regex=False).str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    def conv_data(val):
        if pd.isna(val) or str(val).strip() == '' or 'NÃO' in str(val).upper(): return pd.NaT
        try:
            num = float(val)
            if num > 1000: return pd.to_datetime(num - 25569, unit='D').floor('D')
        except: pass
        return pd.to_datetime(val, errors='coerce').floor('D')

    for col in ['DATA COLETA', 'DATA DE PREVISÃO DE ENTREGA', 'DATA ENTREGUE']:
        df[col] = df[col].apply(conv_data)

    return df[COLUNAS_PADRAO], True, "Sucesso"

@st.cache_data(show_spinner=False)
def obter_coords(cidades_uf):
    geo = Nominatim(user_agent="app_fretes_orguel_v8")
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
                        st.success("Dados sincronizados com sucesso!")
                        st.rerun()
                    else: st.error(msg)
                except Exception as e: st.error(f"Erro: {e}")

st.divider()
df = st.session_state.banco_dados

if not df.empty:
    df['PERFORMANCE_SLA'] = df.apply(avaliar_prazo, axis=1)
    df['CIDADE/UF_ORIGEM'] = df['CIDADE ORIGEM'] + ", " + df['ESTADO ORIGEM']
    df['CIDADE/UF_DESTINO'] = df['CIDADE DESTINO'] + ", " + df['ESTADO DESTINO']
    
    df['ANO_COLETA'] = df['DATA COLETA'].dt.year.fillna(0).astype(int).astype(str).replace('0', 'NÃO INFORMADO')
    meses = {1:'JANEIRO', 2:'FEVEREIRO', 3:'MARÇO', 4:'ABRIL', 5:'MAIO', 6:'JUNHO', 7:'JULHO', 8:'AGOSTO', 9:'SETEMBRO', 10:'OUTUBRO', 11:'NOVEMBRO', 12:'DEZEMBRO'}
    df['MES_COLETA'] = df['DATA COLETA'].dt.month.map(meses).fillna('NÃO INFORMADO')
    df['SEMESTRE_COLETA'] = df['DATA COLETA'].dt.month.apply(lambda x: '1º SEMESTRE' if pd.notnull(x) and x <= 6 else ('2º SEMESTRE' if pd.notnull(x) else 'NÃO INFORMADO'))

tab1, tab2 = st.tabs(["📊 Visão Global", "🗺️ Mapa & SLA Logístico"])

# ==========================================
# PÁGINA 1: DASHBOARD
# ==========================================
with tab1:
    if not df.empty:
        col_filtros, col_conteudo = st.columns([2.5, 7.5], gap="large")
        
        with col_filtros:
            st.markdown("<h4 style='color: #1C83E1;'>🔎 Filtros de Análise</h4>", unsafe_allow_html=True)
            
            st.markdown("**📅 Dimensão Temporal**")
            f_ano = st.multiselect("Ano Coleta", sorted(df[df['ANO_COLETA'] != 'NÃO INFORMADO']['ANO_COLETA'].unique()))
            f_semestre = st.multiselect("Semestre", sorted(df[df['SEMESTRE_COLETA'] != 'NÃO INFORMADO']['SEMESTRE_COLETA'].unique()))
            f_mes = st.multiselect("Mês", sorted(df[df['MES_COLETA'] != 'NÃO INFORMADO']['MES_COLETA'].unique()))
            
            st.markdown("**⚙️ Dimensão Operacional**")
            f_filial = st.multiselect("Filial", sorted(df['FILIAL'].unique()))
            f_transp = st.multiselect("Transportadora", sorted(df['TRANSPORTADORA'].unique()))
            f_vei = st.multiselect("Veículo", sorted(df['VEÍCULO'].unique()))
            f_ped = st.multiselect("Nº Pedido", sorted(df['Nº DE PEDIDO'].unique()))
            f_sts = st.multiselect("Status Fretes", sorted(df['STATUS FRETES'].unique()))
            f_med = st.multiselect("Medição/Suprimentos", sorted(df['MEDIÇÃO/SUPRIMENTOS'].unique()))

        df_t1 = df.copy()
        if f_ano: df_t1 = df_t1[df_t1['ANO_COLETA'].isin(f_ano)]
        if f_semestre: df_t1 = df_t1[df_t1['SEMESTRE_COLETA'].isin(f_semestre)]
        if f_mes: df_t1 = df_t1[df_t1['MES_COLETA'].isin(f_mes)]
        if f_filial: df_t1 = df_t1[df_t1['FILIAL'].isin(f_filial)]
        if f_transp: df_t1 = df_t1[df_t1['TRANSPORTADORA'].isin(f_transp)]
        if f_vei: df_t1 = df_t1[df_t1['VEÍCULO'].isin(f_vei)]
        if f_ped: df_t1 = df_t1[df_t1['Nº DE PEDIDO'].isin(f_ped)]
        if f_sts: df_t1 = df_t1[df_t1['STATUS FRETES'].isin(f_sts)]
        if f_med: df_t1 = df_t1[df_t1['MEDIÇÃO/SUPRIMENTOS'].isin(f_med)]

        with col_conteudo:
            st.markdown("#### Resumo da Operação")
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("💰 Total Frete", f"R$ {df_t1['VLR DO FRETE'].sum():,.2f}")
            v2.metric("📄 Total NF", f"R$ {df_t1['VALOR DA NOTA'].sum():,.2f}")
            v3.metric("📦 Volume (Pedidos)", df_t1['Nº DE PEDIDO'].nunique())
            v4.metric("🚚 Total Lançamentos", len(df_t1))
            
            st.write("")
            
            st.markdown("#### Status & Categorias")
            k1, k2, k3, k4, k5 = st.columns(5)
            sts_counts = df_t1['STATUS FRETES'].value_counts()
            k1.metric("Reg. Filiais", sts_counts.get("REGULARIZAÇÃO FILIAIS", 0))
            k2.metric("Cotação Spot", sts_counts.get("COTAÇÃO SPOT", 0))
            k3.metric("Contrato", sts_counts.get("CONTRATO", 0))
            
            med_counts = df_t1['MEDIÇÃO/SUPRIMENTOS'].value_counts()
            k4.metric("📏 Medição", med_counts.get("MEDIÇÃO", 0))
            k5.metric("📦 Suprimentos", med_counts.get("SUPRIMENTOS", 0))

            st.divider()

            st.markdown("#### 📈 Análise Gráfica de Custos e Status")
            
            cg1, cg2 = st.columns(2)
            with cg1:
                df_filial_gasto = df_t1.groupby('FILIAL')['VLR DO FRETE'].sum().reset_index().sort_values('VLR DO FRETE', ascending=False)
                fig_filial = px.bar(df_filial_gasto, x='FILIAL', y='VLR DO FRETE', title="Gasto de Frete por Filial", 
                                    color='VLR DO FRETE', color_continuous_scale='Blues')
                fig_filial.update_layout(coloraxis_showscale=False, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_filial, use_container_width=True)
                
            with cg2:
                df_veiculo_gasto = df_t1.groupby('VEÍCULO')['VLR DO FRETE'].sum().reset_index().sort_values('VLR DO FRETE', ascending=False)
                fig_veiculo = px.bar(df_veiculo_gasto, x='VEÍCULO', y='VLR DO FRETE', title="Gasto de Frete por Tipo de Veículo",
                                     color='VLR DO FRETE', color_continuous_scale='Teal')
                fig_veiculo.update_layout(coloraxis_showscale=False, margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_veiculo, use_container_width=True)

            st.write("")
            cg3, cg4 = st.columns(2)
            with cg3:
                df_status_gasto = df_t1.groupby('STATUS FRETES')['VLR DO FRETE'].sum().reset_index()
                fig_status = px.pie(df_status_gasto, values='VLR DO FRETE', names='STATUS FRETES', hole=0.4, 
                                    title="Status de frete")
                fig_status.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.plotly_chart(fig_status, use_container_width=True)

            with cg4:
                df_med_gasto = df_t1.groupby('MEDIÇÃO/SUPRIMENTOS')['VLR DO FRETE'].sum().reset_index()
                fig_med_sup = px.pie(df_med_gasto, values='VLR DO FRETE', names='MEDIÇÃO/SUPRIMENTOS', hole=0.4, 
                                     title="Medição x Suprimentos")
                fig_med_sup.update_layout(margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.plotly_chart(fig_med_sup, use_container_width=True)

    else:
        st.info("O Banco de Dados está vazio. Sincronize a matriz no painel acima.")

# ==========================================
# PÁGINA 2: MAPA E PERFORMANCE (SLA)
# ==========================================
with tab2:
    if not df.empty:
        st.markdown("<h4 style='color: #1C83E1;'>🧭 Filtros de Rastreamento</h4>", unsafe_allow_html=True)
        
        cf1, cf2, cf3 = st.columns(3)
        f2_ano = cf1.multiselect("Ano Coleta", sorted(df[df['ANO_COLETA'] != 'NÃO INFORMADO']['ANO_COLETA'].unique()), key="p2_ano")
        f2_sem = cf2.multiselect("Semestre", sorted(df[df['SEMESTRE_COLETA'] != 'NÃO INFORMADO']['SEMESTRE_COLETA'].unique()), key="p2_sem")
        f2_mes = cf3.multiselect("Mês", sorted(df[df['MES_COLETA'] != 'NÃO INFORMADO']['MES_COLETA'].unique()), key="p2_mes")

        c1, c2, c3 = st.columns(3)
        opcoes_pedidos = ["TODOS"] + sorted(df['Nº DE PEDIDO'].unique())
        opcoes_transp = ["TODOS"] + sorted(df['TRANSPORTADORA'].unique())
        opcoes_sla = ["TODOS", "NO PRAZO", "ATRASADO", "EM ANDAMENTO"]
        
        f2_ped = c1.selectbox("📌 Nº de Pedido", opcoes_pedidos, key="p2_ped")
        f2_tra = c2.selectbox("🏢 Transportadora", opcoes_transp, key="p2_tra")
        f2_sla = c3.selectbox("🚥 Status SLA", opcoes_sla, key="p2_sla")

        df_t2 = df.copy()
        if f2_ano: df_t2 = df_t2[df_t2['ANO_COLETA'].isin(f2_ano)]
        if f2_sem: df_t2 = df_t2[df_t2['SEMESTRE_COLETA'].isin(f2_sem)]
        if f2_mes: df_t2 = df_t2[df_t2['MES_COLETA'].isin(f2_mes)]
        if f2_ped != "TODOS": df_t2 = df_t2[df_t2['Nº DE PEDIDO'] == f2_ped]
        if f2_tra != "TODOS": df_t2 = df_t2[df_t2['TRANSPORTADORA'] == f2_tra]
        if f2_sla != "TODOS": df_t2 = df_t2[df_t2['PERFORMANCE_SLA'] == f2_sla]

        st.write("")
        col_mapa, col_dados = st.columns([6, 4], gap="large")
        
        tem_pedido_unico = (f2_ped != "TODOS" and not df_t2.empty)
        if tem_pedido_unico:
            linha = df_t2.iloc[0]
            coords = obter_coords([linha['CIDADE/UF_ORIGEM'], linha['CIDADE/UF_DESTINO']])
        
        with col_mapa:
            if tem_pedido_unico:
                st.markdown(f"**Rota Traçada (Pedido: {f2_ped})**")
                if len(coords) == 2:
                    st.map(pd.DataFrame({'lat': [c[0] for c in coords.values()], 'lon': [c[1] for c in coords.values()]}))
                else:
                    st.warning("Não foi possível plotar o mapa. Verifique a grafia da Cidade/Estado.")
            else:
                st.markdown("**Visão de Calor (Zonas de Origem)**")
                with st.spinner("Desenhando zonas..."):
                    top_origens = df_t2['CIDADE/UF_ORIGEM'].value_counts().head(30).index.tolist()
                    coords_calor = obter_coords(top_origens)
                    if coords_calor:
                        df_calor = pd.DataFrame({
                            'lat': [c[0] for c in coords_calor.values()], 
                            'lon': [c[1] for c in coords_calor.values()], 
                            'tamanho': [df_t2[df_t2['CIDADE/UF_ORIGEM'] == cid].shape[0] * 15 for cid in coords_calor.keys()]
                        })
                        fig_map = px.scatter_mapbox(df_calor, lat="lat", lon="lon", size="tamanho", 
                                                    color_discrete_sequence=["#1C83E1"], zoom=3, mapbox_style="carto-positron")
                        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                        st.plotly_chart(fig_map, use_container_width=True)

        with col_dados:
            if tem_pedido_unico:
                st.markdown('<div class="bloco-info">', unsafe_allow_html=True)
                st.markdown(f"##### Detalhes da Rota")
                
                st.write(f"🏢 **FILIAL:** {linha['FILIAL']}")
                
                vlr_frete = f"R$ {linha['VLR DO FRETE']:,.2f}"
                vlr_nota = f"R$ {linha['VALOR DA NOTA']:,.2f}"
                st.write(f"💰 **VALOR DO FRETE:** {vlr_frete} | 📄 **VALOR DA NOTA:** {vlr_nota}")
                
                st.write(f"📤 **CIDADE ORIGEM:** {linha['CIDADE ORIGEM']} | **ESTADO ORIGEM:** {linha['ESTADO ORIGEM']}")
                st.write(f"📥 **CIDADE DESTINO:** {linha['CIDADE DESTINO']} | **ESTADO DESTINO:** {linha['ESTADO DESTINO']}")
                
                if len(coords) == 2:
                    st.write(f"🛣️ **KM PERCORRIDO:** {geodesic(coords[linha['CIDADE/UF_ORIGEM']], coords[linha['CIDADE/UF_DESTINO']]).km:.1f} km")
                
                d_col = linha['DATA COLETA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA COLETA']) else 'N/A'
                d_pre = linha['DATA DE PREVISÃO DE ENTREGA'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA DE PREVISÃO DE ENTREGA']) else 'N/A'
                d_ent = linha['DATA ENTREGUE'].strftime('%d/%m/%Y') if pd.notnull(linha['DATA ENTREGUE']) else 'N/A'
                
                st.write(f"📅 **DATA COLETA:** {d_col}")
                st.write(f"📅 **DATA DE PREVISÃO DE ENTREGA:** {d_pre}")
                st.write(f"📅 **DATA ENTREGA:** {d_ent}")
                
                obs_texto = linha['OBSERVAÇÃO'] if pd.notnull(linha['OBSERVAÇÃO']) and linha['OBSERVAÇÃO'] != "NÃO INFORMADO" else ""
                if obs_texto:
                    st.write(f"📝 **OBSERVAÇÃO:** {obs_texto}")
                
                if linha['PERFORMANCE_SLA'] == 'NO PRAZO': 
                    st.markdown('<div class="badge-excelente">✅ NO PRAZO</div>', unsafe_allow_html=True)
                elif linha['PERFORMANCE_SLA'] == 'ATRASADO': 
                    st.markdown('<div class="badge-ruim">🚨 ATRASADO</div>', unsafe_allow_html=True)
                else: 
                    st.markdown('<div class="badge-andamento">⏳ EM ANDAMENTO</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
            else:
                if f2_tra != "TODOS":
                    qtd_atraso = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'ATRASADO'])
                    qtd_no_prazo = len(df_t2[df_t2['PERFORMANCE_SLA'] == 'NO PRAZO'])
                    total_validos = qtd_atraso + qtd_no_prazo

                    if total_validos > 0:
                        otd = (qtd_no_prazo / total_validos) * 100

                        if otd >= 95.0:
                            nota_text = "EXCELENTE (Alta Confiabilidade Operacional)"
                            cor_nota = "#00C49F" 
                            icone = "🟢"
                            msg_nota = "Transportadora altamente aderente ao SLA. Recomenda-se priorização em novas demandas, ampliação de volume e fortalecimento da parceria."
                        elif otd >= 85.0:
                            nota_text = "BOA (Performance Controlada)"
                            cor_nota = "#1C83E1" 
                            icone = "🔵"
                            msg_nota = "Performance estável, porém com oportunidade de otimização. Monitoramento contínuo e reuniões periódicas de alinhamento operacional."
                        elif otd >= 70.0:
                            nota_text = "ALERTA (Risco Operacional)"
                            cor_nota = "#FFA500" 
                            icone = "🟡"
                            msg_nota = "Indício de instabilidade operacional. Necessário plano de ação estruturado com metas claras de recuperação de SLA e acompanhamento mensal."
                        else:
                            nota_text = "CRÍTICA (Comprometimento do Nível de Serviço)"
                            cor_nota = "#FF4B4B" 
                            icone = "🔴"
                            msg_nota = "Performance incompatível com o nível de serviço esperado. Avaliar aplicação de penalidades contratuais, redução de volume ou substituição do fornecedor."

                        st.markdown(f"""
                        <div style='background-color: {cor_nota}15; border-left: 5px solid {cor_nota}; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                            <h5 style='color: {cor_nota}; margin-top: 0;'>{icone} Avaliação: {nota_text}</h5>
                            <h3 style='color: {cor_nota}; margin: 10px 0;'>OTD: {otd:.1f}%</h3>
                            <p style='margin-bottom: 0; font-size: 0.95em;'>{msg_nota}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("Não há entregas finalizadas para calcular o OTD desta Transportadora.")

                titulo_grafico = f"Performance de Entregas ({f2_tra})" if f2_tra != "TODOS" else "Performance de Entregas Global"
                st.markdown(f"##### {titulo_grafico}")
                
                df_pie_sla = df_t2['PERFORMANCE_SLA'].value_counts().reset_index()
                df_pie_sla.columns = ['PERFORMANCE', 'CONTAGEM']
                
                cores_sla = {'NO PRAZO': '#00C49F', 'ATRASADO': '#FF4B4B', 'EM ANDAMENTO': '#FFA500', 'SEM PREVISÃO': '#808080'}
                
                fig_sla = px.pie(df_pie_sla, values='CONTAGEM', names='PERFORMANCE', 
                                 color='PERFORMANCE', color_discrete_map=cores_sla, hole=0.3)
                
                fig_sla.update_layout(
                    margin=dict(t=20, b=20, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_sla, use_container_width=True)

        st.divider()
        st.markdown("### 📋 Diário de Rotas")
        st.dataframe(df_t2.drop(columns=['ID_INTERNO', 'CIDADE/UF_ORIGEM', 'CIDADE/UF_DESTINO', 'ANO_COLETA', 'MES_COLETA', 'SEMESTRE_COLETA'], errors='ignore'), use_container_width=True)