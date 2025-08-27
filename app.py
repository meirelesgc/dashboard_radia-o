import requests
import streamlit as st
import pandas as pd
import altair as alt
import numpy_financial as npf

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Simulador Solar",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNÇÕES DE API ---
@st.cache_data
def get_coordinates(city):
    """Busca as coordenadas geográficas de uma cidade."""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'SolarViabilityApp/1.4 (contato@seuemail.com )'}
    params = {'q': city, 'format': 'json', 'limit': 1}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        return None, None
    except requests.exceptions.RequestException:
        return None, None

@st.cache_data
def get_pvgis_data(lat, lon, perdas):
    """Busca dados de irradiação solar da API PVGIS."""
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    params = {
        'lat': lat,
        'lon': lon,
        'peakpower': 1,
        'loss': perdas,
        'outputformat': 'json',
        'pvcalculation': 1,
        'mounting_system': 'fixed'
    }
    try:
        response = requests.get(url, params=params, timeout=15 )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

# --- INTERFACE PRINCIPAL DO APLICATIVO ---
st.title("☀️ Simulador de Viabilidade de Energia Solar")
st.markdown("Uma ferramenta completa para analisar o potencial técnico e financeiro de um sistema fotovoltaico.")

# --- Formulário de Coleta de Dados ---
with st.form(key='simulation_form'):
    st.header("1. Preencha os dados para a simulação")

    col1, col2 = st.columns(2)
    with col1:
        cidade = st.text_input("Cidade e Estado", "Feira de Santana, BA", help="Ex: São Paulo, SP")
        consumo_mensal_kwh = st.number_input("Consumo médio mensal de energia (kWh)", min_value=50, value=350, step=10)
    with col2:
        tarifa_energia = st.number_input("Valor da tarifa de energia (R$/kWh)", min_value=0.10, value=0.95, step=0.01, format="%.2f")

    with st.expander("⚙️ Opções Avançadas e Técnicas"):
        st.subheader("Parâmetros de Custo e Geração")
        col3, col4, col5 = st.columns(3)
        with col3:
            custo_watt_pico_modulo = st.number_input("Custo do Módulo (R$/Wp)", 0.50, 3.00, 1.20, 0.05)
        with col4:
            custo_bos_watt_pico = st.number_input("Custo do BoS* (R$/Wp)", 0.80, 4.00, 1.60, 0.05, help="*Balance of System: Inversor, cabos, estruturas e mão de obra.")
        with col5:
            tipo_conexao = st.selectbox("Tipo de Conexão da Unidade", ["Trifásico", "Bifásico", "Monofásico"], help="Define o valor da taxa mínima (custo de disponibilidade) cobrada pela concessionária.")

        st.subheader("Parâmetros de Simulação e Financeiros")
        col6, col7, col8 = st.columns(3)
        with col6:
            perdas_sistema = st.slider("Perdas totais do sistema (%)", 5, 25, 14, help="Perdas por sujeira, temperatura, cabos, etc.")
        with col7:
            margem_geracao_percent = st.slider("Margem de segurança na geração (%)", 0, 50, 15, help="Quanto a mais você quer gerar para compensar dias nublados ou aumento de consumo.")
        with col8:
            inflacao_energia = st.slider("Inflação da tarifa de energia (% ao ano)", 1.0, 15.0, 7.0, 0.5, help="Estimativa de quanto a conta de luz aumentará por ano.")

    submit_button = st.form_submit_button(label='▶️ Iniciar Simulação Completa')

# --- Lógica de Execução e Apresentação em Abas ---
if submit_button:
    if not cidade or not consumo_mensal_kwh:
        st.warning("Por favor, preencha a cidade e o consumo para iniciar.")
    else:
        lat, lon = get_coordinates(cidade)
        if not lat:
            st.error(f"Não foi possível encontrar as coordenadas para '{cidade}'. Verifique o nome e tente novamente.")
        else:
            with st.spinner(f"Buscando dados de irradiação para {cidade} e calculando..."):
                pvgis_data = get_pvgis_data(lat, lon, perdas_sistema)

            if not pvgis_data:
                st.error("Falha ao obter os dados de irradiação solar da API PVGIS. Tente novamente mais tarde.")
            else:
                st.header("2. Resultados da Simulação")

                # --- Cálculos Chave ---
                mapa_disponibilidade = {"Monofásico": 30, "Bifásico": 50, "Trifásico": 100}
                disponibilidade_kwh = mapa_disponibilidade[tipo_conexao]
                custo_disponibilidade_mensal = disponibilidade_kwh * tarifa_energia

                df = pd.DataFrame(pvgis_data['outputs']['monthly']['fixed'])
                pior_mes_geracao_por_kwp = df['E_m'].min()
                consumo_desejado_kwh = consumo_mensal_kwh * (1 + margem_geracao_percent / 100)
                tamanho_sistema_kwp = consumo_desejado_kwh / pior_mes_geracao_por_kwp if pior_mes_geracao_por_kwp > 0 else 0
                geracao_anual_estimada = df['E_m'].sum() * tamanho_sistema_kwp
                
                custo_total_watt_pico = custo_watt_pico_modulo + custo_bos_watt_pico
                custo_estimado_sistema = tamanho_sistema_kwp * custo_total_watt_pico * 1000

                economia_anual_bruta = geracao_anual_estimada * tarifa_energia
                economia_anual_liquida = economia_anual_bruta - (custo_disponibilidade_mensal * 12)
                payback_simples_anos = custo_estimado_sistema / economia_anual_liquida if economia_anual_liquida > 0 else float('inf')

                # --- Criação das Abas ---
                tab_resumo, tab_financeiro, tab_grafico, tab_detalhes, tab_info = st.tabs(["📊 Resumo Geral", "💰 Análise de Investimento", "📈 Geração vs Consumo", "⚙️ Detalhes Técnicos", "📚 Como Funciona?"])

                with tab_resumo:
                    st.subheader("Principais Indicadores do Projeto")
                    resumo_col1, resumo_col2, resumo_col3 = st.columns(3)
                    with resumo_col1:
                        st.metric("Potência Recomendada", f"{tamanho_sistema_kwp:.2f} kWp")
                    with resumo_col2:
                        st.metric("Custo Estimado da Instalação", f"R$ {custo_estimado_sistema:,.2f}")
                    with resumo_col3:
                        st.metric("Economia Anual Líquida", f"R$ {economia_anual_liquida:,.2f}", help=f"Economia já descontando o custo de disponibilidade de {disponibilidade_kwh} kWh/mês.")

                    st.divider()
                    st.subheader("Indicadores Ambientais (Estimativa para 25 anos)")
                    co2_evitado_ton = (geracao_anual_estimada * 25 * 0.475) / 1000
                    arvores_equivalentes = co2_evitado_ton * 7.14
                    
                    amb_col1, amb_col2 = st.columns(2)
                    with amb_col1:
                        st.metric("🌳 Árvores Equivalentes", f"{arvores_equivalentes:,.0f} árvores")
                    with amb_col2:
                        st.metric("💨 CO₂ Evitado", f"{co2_evitado_ton:,.2f} toneladas")

                with tab_financeiro:
                    st.subheader("Análise de Investimento a Longo Prazo (25 anos)")
                    
                    fin_col_input, fin_col_vazio = st.columns([1, 2])
                    with fin_col_input:
                        tma_anual = st.slider("Taxa Mínima de Atratividade (TMA % ao ano)", 1.0, 20.0, 10.0, 0.5, help="O rendimento mínimo que você aceitaria em um investimento. Use a SELIC como referência.") / 100
                    
                    degradacao_paineis_anual = 0.005

                    fluxo_caixa = [-custo_estimado_sistema]
                    economia_ano_a_ano = economia_anual_liquida
                    
                    for ano in range(1, 26):
                        fluxo_caixa.append(economia_ano_a_ano)
                        economia_ano_a_ano *= (1 + inflacao_energia / 100) * (1 - degradacao_paineis_anual)

                    vpl = npf.npv(tma_anual, fluxo_caixa)
                    tir = npf.irr(fluxo_caixa) * 100
                    
                    st.divider()
                    st.subheader("Resultados da Análise Financeira")
                    fin_col1, fin_col2 = st.columns(2)
                    with fin_col1:
                        st.metric("Valor Presente Líquido (VPL)", f"R$ {vpl:,.2f}", help="Se > 0, o investimento é atrativo e supera a rentabilidade mínima esperada (TMA).")
                        if vpl > 0: st.success("✅ Viável: O VPL é positivo.")
                        else: st.warning("⚠️ Atenção: O VPL é negativo.")
                    with fin_col2:
                        st.metric("Taxa Interna de Retorno (TIR)", f"{tir:.2f}% ao ano", delta=f"{(tir - tma_anual*100):.2f} p.p. vs TMA", help="Rentabilidade real do projeto. O delta mostra a diferença em relação à TMA.")
                        if tir > tma_anual * 100: st.success(f"✅ Viável: A TIR é maior que a TMA.")
                        else: st.error(f"❌ Inviável: A TIR é menor que a TMA.")
                    
                    st.divider()
                    st.subheader("Evolução do Investimento e Payback Descontado")
                    
                    vpl_anual = [npf.npv(tma_anual, fluxo_caixa[:i+1]) for i in range(len(fluxo_caixa))]
                    df_vpl = pd.DataFrame({'Ano': list(range(26)), 'VPL Acumulado (R$)': vpl_anual})
                    
                    payback_descontado_ano = "Não alcançado"
                    for ano, vpl_valor in enumerate(vpl_anual):
                        if vpl_valor > 0:
                            payback_descontado_ano = f"~{ano} anos"
                            break
                    
                    payback_col1, payback_col2 = st.columns(2)
                    payback_col1.metric("Payback Simples", f"{payback_simples_anos:.1f} anos")
                    payback_col2.metric("Payback Descontado", payback_descontado_ano)

                    vpl_chart = alt.Chart(df_vpl).mark_area(line={'color':'#1f77b4'}, color=alt.Gradient(gradient='linear', stops=[alt.GradientStop(color='#d62728', offset=0), alt.GradientStop(color='#2ca02c', offset=1)], x1=1, x2=1, y1=1, y2=0)).encode(x=alt.X('Ano:O', title='Ano'), y=alt.Y('VPL Acumulado (R$):Q', title='VPL (R$)'), tooltip=['Ano', alt.Tooltip('VPL Acumulado (R$)', format=',.2f')]).properties(title='Evolução do Valor Presente Líquido (VPL)')
                    st.altair_chart(vpl_chart.interactive(), use_container_width=True)

                with tab_grafico:
                    st.subheader("Geração Mensal Estimada (kWh) vs Consumo Médio")
                    df['geracao_estimada_kwh'] = df['E_m'] * tamanho_sistema_kwp
                    meses_pt = {m+1: n for m, n in enumerate(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])}
                    df['mes'] = df['month'].map(meses_pt)
                    
                    bar_chart = alt.Chart(df).mark_bar().encode(x=alt.X('mes:N', sort=alt.EncodingSortField(field="month"), title='Mês'), y=alt.Y('geracao_estimada_kwh:Q', title='Energia Gerada (kWh)'), tooltip=[alt.Tooltip('mes', title='Mês'), alt.Tooltip('geracao_estimada_kwh', title='Geração (kWh)', format='.0f')])
                    text_labels = bar_chart.mark_text(align='center', baseline='bottom', dy=-5).encode(text=alt.Text('geracao_estimada_kwh:Q', format='.0f'))
                    
                    rule_consumo = alt.Chart(pd.DataFrame({'consumo': [consumo_mensal_kwh]})).mark_rule(color='red', strokeDash=[5,5], size=2).encode(y='consumo:Q')
                    text_consumo = rule_consumo.mark_text(align='right', text='Consumo Médio', dx=-5, dy=-10, color='red').encode(text=alt.value('← Consumo Médio'))

                    st.altair_chart(bar_chart + text_labels + rule_consumo + text_consumo, use_container_width=True)

                with tab_detalhes:
                    st.subheader("Parâmetros Técnicos e de Simulação")
                    angulo_otimo = pvgis_data['inputs']['mounting_system']['fixed']['slope']['value']
                    azimuth_otimo = pvgis_data['inputs']['mounting_system']['fixed']['azimuth']['value']
                    
                    st.markdown(f"""
                    - **Localização:** {cidade} (Latitude: `{lat:.4f}`, Longitude: `{lon:.4f}`)
                    - **Tipo de Conexão:** `{tipo_conexao}` (Custo de disp.: `{disponibilidade_kwh}` kWh/mês)
                    - **Consumo de Referência:** `{consumo_mensal_kwh}` kWh/mês
                    - **Tarifa de Energia Inicial:** `R$ {tarifa_energia:.2f}` / kWh
                    - **Custo Total do Sistema por Wp:** `R$ {custo_total_watt_pico:.2f}` / Wp
                    - **Ângulo de Inclinação Ótimo:** `{angulo_otimo}`°
                    - **Azimute Ótimo:** `{azimuth_otimo}`° (0° = Sul, 180° = Norte)
                    """)
                    
                    st.subheader("Dados Brutos de Geração (por 1 kWp)")
                    st.dataframe(df[['month', 'E_m', 'H(i)_m']].rename(columns={'month': 'Mês', 'E_m': 'Geração Média (kWh)', 'H(i)_m': 'Irradiação Média (kWh/m²)'}), use_container_width=True)

                # --- ABA EDUCACIONAL ---
                # CORREÇÃO APLICADA AQUI: Garantindo que o texto seja passado como argumento para st.markdown()
                with tab_info:
                    st.header("📚 A Jornada da Energia Solar: Do Sol à Tomada")
                    st.markdown("Entenda o passo a passo de como a luz do sol se transforma em eletricidade na sua casa ou empresa.")

                    st.subheader("1. ⚛️ O Princípio Físico: Efeito Fotovoltaico")
                    st.markdown("""
                    - **Mágica do Silício:** Tudo começa nos painéis solares, compostos por células de silício. O silício é um material semicondutor que é 'dopado' com outros elementos para criar um campo elétrico.
                    - **Fótons em Ação:** Quando um fóton (uma partícula de luz solar) atinge a célula de silício, ele transfere sua energia para um elétron.
                    - **Nasce a Corrente:** Esse elétron energizado se liberta e é 'empurrado' pelo campo elétrico, criando um fluxo de elétrons. Esse fluxo é o que chamamos de **corrente elétrica contínua (CC)**.
                    """)

                    st.subheader("2. 🔌 Os Equipamentos: Geração e Conversão")
                    st.markdown("""
                    - **Painéis Solares (Módulos Fotovoltaicos):** Capturam a luz do sol e geram energia em corrente contínua (CC).
                    - **Inversor Solar:** É o cérebro do sistema. Ele converte a energia de corrente contínua (CC) dos painéis para **corrente alternada (CA)**, que é o padrão utilizado em nossas casas e na rede elétrica. Ele também é responsável pela segurança e monitoramento do sistema.
                    - **Estruturas de Montagem:** Fixam os painéis no telhado ou no solo, garantindo a angulação correta e a segurança contra ventos e intempéries.
                    - **String Box (Caixa de Junção):** É um componente de segurança que protege o sistema contra surtos de tensão e curtos-circuitos.
                    """)

                    st.subheader("3. ⚡ Geração, Consumo e Créditos de Energia")
                    st.markdown("""
                    - **Consumo Instantâneo:** Durante o dia, a energia gerada pelos painéis alimenta diretamente os aparelhos da casa. Se a geração for maior que o consumo, o excedente vai para a rede.
                    - **Injeção na Rede:** A energia excedente é 'injetada' na rede elétrica da concessionária. O medidor de energia (que é bidirecional) registra essa injeção.
                    - **Créditos de Energia:** Toda a energia injetada vira **créditos energéticos** em kWh. Esses créditos são usados para abater o consumo da rede durante a noite ou em dias nublados.
                    - **Sistema de Compensação (Net Metering):** É essa 'troca' de energia com a rede. Você usa a rede como uma grande bateria, armazenando seus créditos para quando precisar.
                    """)

                    st.subheader("4. 📝 O Processo Burocrático: Projeto e Homologação")
                    st.markdown("""
                    - **Visita Técnica e Projeto:** Uma empresa especializada avalia o local, analisa o consumo e elabora um projeto técnico detalhado (memorial descritivo, diagramas, etc.).
                    - **Solicitação de Acesso:** O projeto é submetido à concessionária de energia local. Ela analisa se o projeto e a rede elétrica atendem às normas.
                    - **Parecer de Acesso:** Se tudo estiver correto, a concessionária emite o 'Parecer de Acesso', autorizando a instalação.
                    - **Instalação e Vistoria:** A equipe instala o sistema. Após a conclusão, a concessionária realiza uma vistoria para garantir que a instalação está segura e de acordo com o projeto aprovado.
                    - **Troca do Medidor e Conexão:** Com a vistoria aprovada, a concessionária troca o medidor antigo por um bidirecional e o sistema é finalmente conectado à rede.
                    """)

                    st.subheader("5. 🛠️ Operação e Manutenção")
                    st.markdown("""
                    - **Monitoramento:** A maioria dos inversores modernos permite o acompanhamento da geração de energia em tempo real por meio de aplicativos de celular ou web.
                    - **Manutenção:** A manutenção é mínima. Recomenda-se a limpeza dos painéis a cada 6 ou 12 meses (dependendo da poeira e poluição local) para garantir a máxima eficiência. Inspeções elétricas periódicas também são uma boa prática.
                    """)
