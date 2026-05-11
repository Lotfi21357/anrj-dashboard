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

# Rafraîchissement auto (600 secondes = 10 min)
st_autorefresh(interval=600000, key="datarefresh")

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
        font-size: 2.2rem !important; font-weight: 700;
        background: linear-gradient(90deg, #00E676, #69F0AE);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #00E676, #69F0AE); }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------
DATE_ANCHOR = datetime(2026, 5, 8)
CAPITAL_INVESTI = 13796.71
START_DATE = "2025-09-17"
WORLD_PERF_AT_8MAY = 10.16

QUANTITIES = {
    "DCAM.PA": 481,
    "MWRD.PA": 36.33,
    "ANRJ.PA": 4.77,
    "AASI.PA": 40.83,
    "CGLD.PA": 4.59,
}

# ----------------------------------------------------------------------
# DATA FETCHING (CACHE OPTIMISÉ)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_live_prices():
    tickers = list(QUANTITIES.keys())
    try:
        data = yf.download(tickers, period="5d", progress=False)
        # On prend la dernière ligne non nulle pour chaque ticker
        prices = data["Close"].ffill().iloc[-1].to_dict()
    except:
        prices = {"DCAM.PA": 5.80, "MWRD.PA": 150.0, "ANRJ.PA": 760.0, "AASI.PA": 56.0, "CGLD.PA": 158.0}
    return prices

@st.cache_data(ttl=3600)
def fetch_historical_data():
    tickers = list(QUANTITIES.keys())
    try:
        data = yf.download(tickers, start=START_DATE, progress=False)["Close"]
        return data.ffill()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_world_index():
    try:
        return yf.download("CW8.PA", start=START_DATE, progress=False)["Close"].ffill()
    except:
        return pd.Series()

@st.cache_data(ttl=3600)
def fetch_macro_data():
    """Récupère TSMC et le Dollar Index"""
    try:
        tsm = yf.download("TSM", period="6mo", progress=False)["Close"]
        dxy = yf.download("DX-Y.NYB", period="5d", progress=False)["Close"]
        return tsm, dxy.iloc[-1]
    except:
        return pd.Series(), 100.0

# ----------------------------------------------------------------------
# LOGIQUE MÉTIER
# ----------------------------------------------------------------------
def get_portfolio_details(bonus_active):
    prices = fetch_live_prices()
    
    vals = {t: QUANTITIES[t] * prices.get(t, 0) for t in QUANTITIES}
    
    world_value = vals["DCAM.PA"] + vals["MWRD.PA"]
    if bonus_active:
        world_value += 160.0 # Le bonus est injecté dans la poche World (PEA)
        
    portfolio_value = world_value + vals["ANRJ.PA"] + vals["AASI.PA"] + vals["CGLD.PA"]
    
    performance = (portfolio_value / CAPITAL_INVESTI - 1) * 100
    gap = performance - WORLD_PERF_AT_8MAY
    
    world_pct = (world_value / portfolio_value * 100)
    progression_lazy = (world_pct / 94.0) * 100
    
    return {
        "total_val": portfolio_value,
        "performance": performance,
        "gap": gap,
        "world_pct": world_pct,
        "progression": progression_lazy,
        "prices": prices,
        "vals": vals
    }

# ----------------------------------------------------------------------
# INTERFACE
# ----------------------------------------------------------------------
if 'bonus_active' not in st.session_state:
    st.session_state.bonus_active = False

with st.sidebar:
    st.title("⚙️ Pilotage")
    bonus = st.toggle("🔮 Bonus Fortuneo (160€)", value=st.session_state.bonus_active)
    if bonus != st.session_state.bonus_active:
        st.session_state.bonus_active = bonus
        st.rerun()
    st.info(f"Analyse basée sur le PRM réel du document Historique.")

st.title("📊 Executive Portfolio Management System")
det = get_portfolio_details(st.session_state.bonus_active)

# Métriques
c1, c2, c3, c4 = st.columns(4)
c1.metric("Valeur Totale", f"{det['total_val']:,.0f} €")
c2.metric("Performance", f"{det['performance']:+.2f} %")
c3.metric("Gap vs World", f"{det['gap']:+.2f} %")
c4.metric("Progression Lazy", f"{det['progression']:.1f} %")

# Graphiques
st.subheader("📈 Suivi de Convergence")
hist = fetch_historical_data()
world_h = fetch_world_index()

if not hist.empty and not world_h.empty:
    # On aligne les dates
    combined = pd.concat([hist, world_h], axis=1).ffill().dropna()
    # Calcul valeur portf historique (base 100)
    portf_h = (combined[list(QUANTITIES.keys())] * list(QUANTITIES.values())).sum(axis=1)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=portf_h.index, y=(portf_h/portf_h.iloc[0]*100), name="Portefeuille", line=dict(color='#00E676', width=3)))
    fig.add_trace(go.Scatter(x=world_h.index, y=(world_h/world_h.iloc[0]*100), name="MSCI World", line=dict(color='#9AA0A6', width=2)))
    fig.update_layout(template="plotly_dark", paper_bgcolor='#0E1117', plot_bgcolor='#0E1117', margin=dict(l=0,r=0,t=30,b=0))
    st.plotly_chart(fig, use_container_width=True)

# Diagnostics Satellites (Exemple simplifié pour ANRJ)
st.subheader("🛰️ Analyse Decisionnelle")
col_anrj, col_aasi = st.columns(2)

with col_anrj:
    # Calcul Score ANRJ (Dynamique)
    anrj_price = det['prices'].get("ANRJ.PA", 0)
    # On récupère les SMA réelles
    sma200 = hist["ANRJ.PA"].rolling(200).mean().iloc[-1] if len(hist) > 200 else 758.0
    score = 75 if anrj_price > sma200 else 45
    
    st.markdown(f"**Hydrogen (ANRJ)** : {'✅ MAINTIEN' if score > 70 else '⚠️ VIGILANCE'}")
    st.progress(score/100)
    st.caption(f"Prix : {anrj_price:.2f}€ | SMA200 : {sma200:.2f}€")

with col_aasi:
    tsm_h, dxy_val = fetch_macro_data()
    tsm_last = tsm_h.iloc[-1] if not tsm_h.empty else 0
    tsm_sma50 = tsm_h.rolling(50).mean().iloc[-1] if len(tsm_h) > 50 else 0
    
    status_tsm = "🔴 TSMC < SMA50" if tsm_last < tsm_sma50 else "🟢 TSMC OK"
    st.markdown(f"**EM Asia (AASI)** : {status_tsm}")
    st.markdown(f"Dollar Index : `{dxy_val:.2f}` {'⚠️ (Pression)' if dxy_val > 102 else '✅ (Favorable)'}")

st.divider()
st.caption("Système Décisionnel V3 - Mode Institutionnel Actif")
