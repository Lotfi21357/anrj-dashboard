import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# ----------------------------------------------------------------------
# CONFIGURATION & DESIGN
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Executive Portfolio Management System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium dark theme
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1A1E25 0%, #12161C 100%);
        border: 1px solid #2A2E35;
        border-radius: 12px;
        padding: 1.2rem 1rem 0.8rem 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    div[data-testid="stMetric"] label { color: #9AA0A6 !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 2.2rem !important;
        font-weight: 700;
        background: linear-gradient(90deg, #00E676, #69F0AE);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    section[data-testid="stSidebar"] { border-right: 1px solid #2A2E35; }
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #00E676, #69F0AE); }
    .stButton button { border-radius: 8px; border: 1px solid #2A2E35; background: #1A1E25; color: white; }
    .stButton button:hover { border-color: #00E676; color: #00E676; }
</style>
""", unsafe_allow_html=True)

# Rafraîchissement automatique toutes les 5 minutes (300 000 ms)
st_autorefresh(interval=300_000, key="autorefresh")

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
DATE_ANCHOR = datetime(2026, 5, 8)
CAPITAL_INVESTI = 13796.71
START_DATE = "2025-09-17"
WORLD_PERF_AT_8MAY = 10.16  # référence document

# Positions fixes (quantités réelles)
QUANTITIES = {
    "DCAM.PA": 481,
    "MWRD.PA": 36.33,
    "ANRJ.PA": 4.77,
    "AASI.PA": 40.83,
    "CGLD.PA": 4.59,
}

# ----------------------------------------------------------------------
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES (avec robustesse)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live_prices():
    """Récupère les cours actuels des ETF."""
    tickers = ["DCAM.PA", "MWRD.PA", "ANRJ.PA", "AASI.PA", "CGLD.PA"]
    try:
        data = yf.download(tickers, period="1d", progress=False)
        if data.empty or "Close" not in data.columns:
            raise ValueError("Données vides")
        prices = data["Close"].iloc[-1].to_dict()
    except Exception:
        prices = {
            "DCAM.PA": 5.805, "MWRD.PA": 150.21,
            "ANRJ.PA": 762.50, "AASI.PA": 56.70, "CGLD.PA": 158.27
        }
    return prices

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_historical_data():
    """Récupère l'historique depuis le 17/09/2025 pour tous les ETF du portefeuille."""
    tickers = list(QUANTITIES.keys())
    try:
        data = yf.download(tickers, start=START_DATE, end=DATE_ANCHOR + timedelta(days=1), progress=False)
        if data.empty or "Close" not in data.columns:
            raise ValueError("Données historiques vides")
        close = data["Close"].copy()
        # S'assurer que toutes les colonnes attendues existent
        for t in tickers:
            if t not in close.columns:
                close[t] = np.nan
        close = close.asfreq('B').ffill()
    except Exception:
        # Données simulées minimales si échec complet
        idx = pd.bdate_range(START_DATE, DATE_ANCHOR)
        close = pd.DataFrame({t: np.linspace(100, 100*1.1, len(idx)) for t in tickers}, index=idx)
    return close

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_world_index():
    """Récupère l'historique du MSCI World (CW8.PA) depuis le 17/09/2025."""
    try:
        data = yf.download("CW8.PA", start=START_DATE, end=DATE_ANCHOR + timedelta(days=1), progress=False)
        if data.empty or "Close" not in data.columns:
            raise ValueError("Données World vides")
        close = data["Close"].asfreq('B').ffill()
    except Exception:
        idx = pd.bdate_range(START_DATE, DATE_ANCHOR)
        close = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    return close

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tsmc_sma():
    """Récupère le cours actuel de TSMC et sa SMA50."""
    try:
        tsm = yf.download("TSM", period="3mo", progress=False)
        if tsm.empty or "Close" not in tsm.columns:
            return None, None
        tsm_close = tsm["Close"]
        sma50 = tsm_close.rolling(window=50).mean().iloc[-1]
        last = tsm_close.iloc[-1]
        # Si SMA est NaN (pas assez de données), on retourne None
        if pd.isna(sma50):
            return last, None
        return last, sma50
    except Exception:
        return None, None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dxy():
    """Récupère le dernier cours du Dollar Index."""
    try:
        dxy = yf.download("DX-Y.NYB", period="5d", progress=False)
        if dxy.empty or "Close" not in dxy.columns:
            return 99.0
        return dxy["Close"].iloc[-1]
    except Exception:
        return 99.0

# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------
if 'bonus_active' not in st.session_state:
    st.session_state.bonus_active = False

# ----------------------------------------------------------------------
# CALCULS DU PORTEFEUILLE (dynamiques)
# ----------------------------------------------------------------------
def get_portfolio_details(bonus=False):
    prices = fetch_live_prices()
    total_value = 0.0
    world_value = QUANTITIES["DCAM.PA"] * prices["DCAM.PA"] + QUANTITIES["MWRD.PA"] * prices["MWRD.PA"]
    gold_value = QUANTITIES["CGLD.PA"] * prices["CGLD.PA"]
    anrj_value = QUANTITIES["ANRJ.PA"] * prices["ANRJ.PA"]
    aasi_value = QUANTITIES["AASI.PA"] * prices["AASI.PA"]
    
    portfolio_value = world_value + anrj_value + aasi_value + gold_value
    
    if bonus:
        portfolio_value += 160.0
        world_value += 160.0  # le bonus est considéré comme investi en World
    
    capital = CAPITAL_INVESTI
    performance = (portfolio_value / capital - 1) * 100
    gap = performance - WORLD_PERF_AT_8MAY
    
    # Allocations
    total = portfolio_value
    world_pct = (world_value / total * 100) if total else 0
    gold_pct = (gold_value / total * 100) if total else 0
    
    # Progression Lazy (94% World)
    target_world = 0.94
    progression = (world_pct / 100.0) / target_world * 100 if target_world else 0
    
    sell_hydro = anrj_value
    sell_asia = aasi_value
    total_reinvest = sell_hydro + sell_asia
    
    return {
        "total_val": portfolio_value,
        "world_val": world_value,
        "gold_val": gold_value,
        "anrj_val": anrj_value,
        "aasi_val": aasi_value,
        "world_pct": world_pct,
        "gold_pct": gold_pct,
        "progression": progression,
        "sell_hydrogen": sell_hydro,
        "sell_asia": sell_asia,
        "total_reinvest": total_reinvest,
        "performance": performance,
        "gap": gap,
        "capital": capital,
        "prices": prices,
    }

# ----------------------------------------------------------------------
# SCORING (avec gestion des NaN)
# ----------------------------------------------------------------------
def _safe_sma(series, window):
    """Calcule la SMA et retourne la dernière valeur, ou None si indisponible."""
    if len(series) < window:
        return None
    sma = series.rolling(window).mean().iloc[-1]
    return sma if not pd.isna(sma) else None

def score_anrj(prices):
    cours = prices["ANRJ.PA"]
    hist = fetch_historical_data()
    sma50 = 722.0
    sma200 = 620.0
    if hist is not None and "ANRJ.PA" in hist.columns:
        s50 = _safe_sma(hist["ANRJ.PA"], 50)
        s200 = _safe_sma(hist["ANRJ.PA"], 200)
        if s50 is not None:
            sma50 = s50
        if s200 is not None:
            sma200 = s200
    
    bloom_ok = True
    us10y = 4.36
    world_surperf = False
    brent = 98.5
    adx_strong = True
    
    score = 0
    if cours > sma50: score += 30
    if cours > sma200: score += 20
    if bloom_ok: score += 15
    if us10y < 4.60: score += 15
    if not world_surperf: score += 10
    if 95 <= brent <= 105: score += 5
    if adx_strong: score += 5
    return min(score, 100)

def verdict(score):
    if score >= 70: return "MAINTIEN", "#00E676"
    elif score >= 50: return "VIGILANCE", "#FF9800"
    else: return "ARBITRAGE", "#FF1744"

def score_aasi(prices):
    cours = prices["AASI.PA"]
    hist = fetch_historical_data()
    sma50 = 54.20
    if hist is not None and "AASI.PA" in hist.columns:
        s50 = _safe_sma(hist["AASI.PA"], 50)
        if s50 is not None:
            sma50 = s50
    
    # TSMC sentinel
    tsm_last, tsm_sma50 = fetch_tsmc_sma()
    tsm_ok = True
    if tsm_last is not None and tsm_sma50 is not None:
        if tsm_last < tsm_sma50:
            tsm_ok = False
    
    # Dollar Index
    dxy = fetch_dxy()
    dxy_ok = True
    if dxy is not None and dxy > 102:
        dxy_ok = False
    
    score = 0
    if cours > sma50: score += 25
    if tsm_ok: score += 20
    else: score -= 30
    if dxy_ok: score += 25
    else: score -= 15
    
    score += 15  # momentum régional
    return max(0, min(score, 100))

# ----------------------------------------------------------------------
# GRAPHIQUE DE PERFORMANCE RÉELLE
# ----------------------------------------------------------------------
def build_performance_chart():
    hist = fetch_historical_data()
    world_idx = fetch_world_index()
    
    # Valeur du portefeuille par jour (quantités fixes actuelles)
    portf_value = pd.Series(0.0, index=hist.index)
    for ticker, qty in QUANTITIES.items():
        if ticker in hist.columns:
            portf_value += hist[ticker].fillna(method='ffill') * qty
    
    init_portf = portf_value.iloc[0]
    init_world = world_idx.iloc[0]
    
    perf_portf = (portf_value / init_portf - 1) * 100
    perf_world = (world_idx / init_world - 1) * 100
    
    gap_series = perf_portf - perf_world
    
    # Figure performance
    fig_area = go.Figure()
    fig_area.add_trace(go.Scatter(
        x=perf_world.index, y=perf_world.values,
        mode='lines', line=dict(width=2, color='#9AA0A6'),
        fill='tozeroy', fillcolor='rgba(200,200,200,0.05)',
        name='MSCI World'
    ))
    fig_area.add_trace(go.Scatter(
        x=perf_portf.index, y=perf_portf.values,
        mode='lines', line=dict(width=3, color='#00E676'),
        fill='tozeroy', fillcolor='rgba(0,230,118,0.12)',
        name='Portefeuille'
    ))
    fig_area.update_layout(
        template="plotly_dark",
        paper_bgcolor='#0E1117', plot_bgcolor='#0E1117',
        font=dict(color='white'), margin=dict(l=0, r=20, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified"
    )
    fig_area.update_xaxes(showgrid=False)
    fig_area.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
    
    # Figure gap
    fig_gap = go.Figure()
    fig_gap.add_trace(go.Scatter(
        x=gap_series.index, y=gap_series.values,
        mode='lines', line=dict(width=2, color='#FFA500'),
        name='Écart vs World'
    ))
    fig_gap.add_hline(y=0, line_dash="dot", line_color="white", opacity=0.5)
    fig_gap.update_layout(
        template="plotly_dark",
        paper_bgcolor='#0E1117', plot_bgcolor='#0E1117',
        font=dict(color='white'), margin=dict(l=0, r=20, t=30, b=0),
        height=300,
        title="Convergence du Gap (cible 0%)"
    )
    return fig_area, fig_gap

# ----------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("<h2 style='color:#00E676;'>⚙️ Pilotage</h2>", unsafe_allow_html=True)
    st.markdown("---")
    bonus_toggle = st.toggle("🔮 Activer Bonus Fortuneo (160 €)", value=st.session_state.bonus_active)
    if bonus_toggle != st.session_state.bonus_active:
        st.session_state.bonus_active = bonus_toggle
        st.rerun()
    st.markdown("---")
    st.caption(f"Données arrêtées au {DATE_ANCHOR.strftime('%d/%m/%Y')}")
    st.caption("Système décisionnel v3 · ANRJ · Terminé ✅")
    st.markdown("ℹ️ Données de marché en direct (yfinance)")

# ----------------------------------------------------------------------
# CORPS PRINCIPAL
# ----------------------------------------------------------------------
st.markdown("<h1 style='color:#FFFFFF;'>📊 Executive Portfolio Management System</h1>", unsafe_allow_html=True)
st.markdown("---")

details = get_portfolio_details(bonus=st.session_state.bonus_active)
prices = details['prices']

# 1. Métriques clés
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Valeur Totale", f"{details['total_val']:,.0f} €")
with col2:
    st.metric("Performance Réelle", f"{details['performance']:+.2f} %")
with col3:
    st.metric("Écart vs MSCI World", f"{details['gap']:+.2f} %")
with col4:
    st.metric("Progression Lazy", f"{details['progression']:.1f} %")

# 2. Graphiques performance et gap
fig_area, fig_gap = build_performance_chart()
st.subheader("📈 Performance Cumulée (base 100)")
st.plotly_chart(fig_area, use_container_width=True)
st.plotly_chart(fig_gap, use_container_width=True)

# 3. Satellites diagnostics
st.subheader("🛰️ Diagnostic Satellites")
col_a, col_b = st.columns(2)

with col_a:
    sc_anrj = score_anrj(prices)
    verd_anrj, col_anrj = verdict(sc_anrj)
    st.markdown(f"### ⚗️ Hydrogen (ANRJ) : {verd_anrj}")
    fig_gauge_anrj = go.Figure(go.Indicator(
        mode="gauge+number", value=sc_anrj,
        title={'text': "Score de Conviction", 'font': {'color': 'white'}},
        gauge={
            'axis': {'range': [0,100]},
            'bar': {'color': col_anrj},
            'steps': [
                {'range': [0,50], 'color':'rgba(255,0,0,0.2)'},
                {'range': [50,70], 'color':'rgba(255,165,0,0.2)'},
                {'range': [70,100], 'color':'rgba(0,255,0,0.2)'}],
            'threshold': {'line': {'color': "white", 'width':2}, 'thickness':0.8, 'value':70}
        }
    ))
    fig_gauge_anrj.update_layout(paper_bgcolor='#0E1117', font={'color':"white"}, margin=dict(l=20,r=20,t=30,b=20))
    st.plotly_chart(fig_gauge_anrj, use_container_width=True)
    st.markdown(f"Cours actuel ANRJ : {prices['ANRJ.PA']:.2f} €")

with col_b:
    sc_aasi = score_aasi(prices)
    verd_aasi, col_aasi = verdict(sc_aasi)
    st.markdown(f"### 🌏 EM Asia (AASI) : {verd_aasi}")
    fig_gauge_aasi = go.Figure(go.Indicator(
        mode="gauge+number", value=sc_aasi,
        title={'text': "Score de Conviction", 'font': {'color': 'white'}},
        gauge={
            'axis': {'range': [0,100]},
            'bar': {'color': col_aasi},
            'steps': [
                {'range': [0,50], 'color':'rgba(255,0,0,0.2)'},
                {'range': [50,70], 'color':'rgba(255,165,0,0.2)'},
                {'range': [70,100], 'color':'rgba(0,255,0,0.2)'}],
            'threshold': {'line': {'color': "white", 'width':2}, 'thickness':0.8, 'value':70}
        }
    ))
    fig_gauge_aasi.update_layout(paper_bgcolor='#0E1117', font={'color':"white"}, margin=dict(l=20,r=20,t=30,b=20))
    st.plotly_chart(fig_gauge_aasi, use_container_width=True)
    tsm_last, tsm_sma50 = fetch_tsmc_sma()
    dxy = fetch_dxy()
    st.markdown(f"Cours actuel AASI : {prices['AASI.PA']:.2f} € | TSMC : {tsm_last:.1f}$ (SMA50:{tsm_sma50:.1f}$) | DXY : {dxy:.1f}")

# 4. Transition Lazy
st.markdown("---")
st.subheader("🎯 Transition vers Portefeuille Lazy (94% World / 6% Or)")
col_l, col_r = st.columns([1,2])
with col_l:
    st.metric("Allocation World actuelle", f"{details['world_pct']:.1f} %", delta="Cible 94%")
    st.progress(min(details['progression']/100.0, 1.0))
with col_r:
    st.markdown(f"""
    **Arbitrages nécessaires :**  
    - 💧 Vendre Hydrogène : **{details['sell_hydrogen']:,.0f} €**  
    - 🌏 Vendre EM Asia : **{details['sell_asia']:,.0f} €**  
    - ♻️ Réinvestir total : **{details['total_reinvest']:,.0f} €** → MSCI World
    """)

st.markdown("---")
st.caption("Document strictement personnel · Système décisionnel v3 · Terminé ✅")
