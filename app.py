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

# Rafraîchissement automatique toutes les 5 minutes
st_autorefresh(interval=300_000, key="autorefresh")

# ----------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------
DATE_ANCHOR = datetime(2026, 5, 8)
CAPITAL_INVESTI = 13796.71
WORLD_PERF_REF = 10.16  # performance du World au 08/05/2026 selon le document

QUANTITIES = {
    "DCAM.PA": 481,
    "MWRD.PA": 36.33,
    "ANRJ.PA": 4.77,
    "AASI.PA": 40.83,
    "CGLD.PA": 4.59,
}

# ----------------------------------------------------------------------
# FONCTIONS ROBUSTES DE DONNÉES
# ----------------------------------------------------------------------
def _safe_download(tickers, period="5d", start=None, end=None):
    """
    Télécharge les données en gérant le MultiIndex et les DataFrames vides.
    Retourne un DataFrame de prix 'Close' avec une seule colonne par ticker.
    """
    try:
        if start and end:
            data = yf.download(tickers, start=start, end=end, progress=False)
        else:
            data = yf.download(tickers, period=period, progress=False)
        if data.empty:
            return None
        # Gestion du MultiIndex (si plusieurs tickers)
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"].copy()
        else:
            close = data[["Close"]] if "Close" in data.columns else None
        if close is None or close.empty:
            return None
        # Remplir les valeurs manquantes (forward fill)
        close = close.ffill()
        return close
    except Exception:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live_prices():
    """Récupère les derniers cours de clôture disponibles."""
    tickers = ["DCAM.PA", "MWRD.PA", "ANRJ.PA", "AASI.PA", "CGLD.PA"]
    close = _safe_download(tickers, period="5d")
    if close is not None and not close.empty:
        # Prend la dernière valeur non-NaN pour chaque ticker
        prices = close.iloc[-1].to_dict()
        return prices
    # Fallback
    return {
        "DCAM.PA": 5.805, "MWRD.PA": 150.21,
        "ANRJ.PA": 762.50, "AASI.PA": 56.70, "CGLD.PA": 158.27
    }

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_historical_data():
    """Historique complet depuis le 17/09/2025."""
    tickers = list(QUANTITIES.keys())
    close = _safe_download(tickers, start="2025-09-17", end="2026-05-09")
    if close is not None:
        # S'assurer que tous les tickers sont présents
        for t in tickers:
            if t not in close.columns:
                close[t] = np.nan
        return close
    # Fallback minimal
    idx = pd.bdate_range("2025-09-17", "2026-05-08")
    return pd.DataFrame({t: np.linspace(100, 110, len(idx)) for t in tickers}, index=idx)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_world_index():
    """Historique du MSCI World (CW8.PA)."""
    close = _safe_download("CW8.PA", start="2025-09-17", end="2026-05-09")
    if close is not None:
        return close["CW8.PA"]
    idx = pd.bdate_range("2025-09-17", "2026-05-08")
    return pd.Series(np.linspace(100, 110, len(idx)), index=idx)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tsmc_sma():
    """Cours actuel de TSMC (TSM) et sa SMA50."""
    close = _safe_download("TSM", period="3mo")
    if close is not None and "TSM" in close.columns:
        tsm = close["TSM"]
        last = tsm.iloc[-1]
        sma50 = tsm.rolling(window=50).mean().iloc[-1]
        return (last, sma50 if not pd.isna(sma50) else None)
    return (None, None)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dxy():
    """Dernière valeur du Dollar Index (DX-Y.NYB)."""
    close = _safe_download("DX-Y.NYB", period="5d")
    if close is not None and "DX-Y.NYB" in close.columns:
        return close["DX-Y.NYB"].iloc[-1]
    return 99.0

# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------
if 'bonus_active' not in st.session_state:
    st.session_state.bonus_active = False

# ----------------------------------------------------------------------
# CALCUL DU PORTEFEUILLE DYNAMIQUE
# ----------------------------------------------------------------------
def get_portfolio_details(bonus=False):
    prices = fetch_live_prices()
    # Calcul des valeurs
    dcamm = QUANTITIES["DCAM.PA"] * prices.get("DCAM.PA", 0)
    mwrd = QUANTITIES["MWRD.PA"] * prices.get("MWRD.PA", 0)
    anrj = QUANTITIES["ANRJ.PA"] * prices.get("ANRJ.PA", 0)
    aasi = QUANTITIES["AASI.PA"] * prices.get("AASI.PA", 0)
    gold = QUANTITIES["CGLD.PA"] * prices.get("CGLD.PA", 0)
    
    world_val = dcamm + mwrd
    portfolio_val = world_val + anrj + aasi + gold
    
    if bonus:
        portfolio_val += 160.0
        world_val += 160.0  # le bonus est assimilé à du World
    
    capital = CAPITAL_INVESTI
    perf = (portfolio_val / capital - 1) * 100
    gap = perf - WORLD_PERF_REF
    
    total = portfolio_val
    world_pct = (world_val / total * 100) if total else 0
    gold_pct = (gold / total * 100) if total else 0
    
    target_world = 0.94
    progression = (world_pct / 100 / target_world) * 100 if target_world else 0
    
    return {
        "total_val": portfolio_val,
        "world_val": world_val,
        "gold_val": gold,
        "anrj_val": anrj,
        "aasi_val": aasi,
        "world_pct": world_pct,
        "gold_pct": gold_pct,
        "progression": progression,
        "sell_hydrogen": anrj,
        "sell_asia": aasi,
        "total_reinvest": anrj + aasi,
        "performance": perf,
        "gap": gap,
        "prices": prices,
    }

# ----------------------------------------------------------------------
# SCORING
# ----------------------------------------------------------------------
def _rolling_last(series, window):
    if len(series) < window:
        return None
    val = series.rolling(window).mean().iloc[-1]
    return val if not pd.isna(val) else None

def score_anrj(prices):
    cours = prices.get("ANRJ.PA", 0)
    hist = fetch_historical_data()
    sma50 = 722.0
    sma200 = 620.0
    if hist is not None and "ANRJ.PA" in hist.columns:
        s50 = _rolling_last(hist["ANRJ.PA"], 50)
        s200 = _rolling_last(hist["ANRJ.PA"], 200)
        if s50 is not None: sma50 = s50
        if s200 is not None: sma200 = s200

    # Indicateurs macro (simulés à partir du document)
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

def score_aasi(prices):
    cours = prices.get("AASI.PA", 0)
    hist = fetch_historical_data()
    sma50 = 54.20
    if hist is not None and "AASI.PA" in hist.columns:
        s50 = _rolling_last(hist["AASI.PA"], 50)
        if s50 is not None: sma50 = s50

    tsm_last, tsm_sma50 = fetch_tsmc_sma()
    tsm_ok = True
    if tsm_last is not None and tsm_sma50 is not None and tsm_last < tsm_sma50:
        tsm_ok = False

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

def verdict(score):
    if score >= 70: return "MAINTIEN", "#00E676"
    elif score >= 50: return "VIGILANCE", "#FF9800"
    else: return "ARBITRAGE", "#FF1744"

# ----------------------------------------------------------------------
# GRAPHIQUES
# ----------------------------------------------------------------------
def build_performance_chart():
    hist = fetch_historical_data()
    world = fetch_world_index()
    
    # Valeur quotidienne du portefeuille (quantités fixes * prix historiques)
    portf_val = pd.Series(0.0, index=hist.index)
    for ticker, qty in QUANTITIES.items():
        if ticker in hist.columns:
            portf_val += hist[ticker].fillna(method='ffill') * qty
    
    base_p = portf_val.iloc[0]
    base_w = world.iloc[0]
    perf_p = (portf_val / base_p - 1) * 100
    perf_w = (world / base_w - 1) * 100
    gap = perf_p - perf_w

    # Graphique de performance
    fig_perf = go.Figure()
    fig_perf.add_trace(go.Scatter(x=perf_w.index, y=perf_w.values,
                                  mode='lines', line=dict(width=2, color='#9AA0A6'),
                                  fill='tozeroy', fillcolor='rgba(200,200,200,0.05)',
                                  name='MSCI World'))
    fig_perf.add_trace(go.Scatter(x=perf_p.index, y=perf_p.values,
                                  mode='lines', line=dict(width=3, color='#00E676'),
                                  fill='tozeroy', fillcolor='rgba(0,230,118,0.12)',
                                  name='Portefeuille'))
    fig_perf.update_layout(template="plotly_dark", paper_bgcolor='#0E1117',
                           plot_bgcolor='#0E1117', font=dict(color='white'),
                           margin=dict(l=0, r=20, t=30, b=0),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02),
                           hovermode="x unified")
    fig_perf.update_xaxes(showgrid=False)
    fig_perf.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.05)')

    # Graphique du gap
    fig_gap = go.Figure()
    fig_gap.add_trace(go.Scatter(x=gap.index, y=gap.values,
                                 mode='lines', line=dict(width=2, color='#FFA500'),
                                 name='Écart vs World'))
    fig_gap.add_hline(y=0, line_dash="dot", line_color="white", opacity=0.5)
    fig_gap.update_layout(template="plotly_dark", paper_bgcolor='#0E1117',
                          plot_bgcolor='#0E1117', font=dict(color='white'),
                          margin=dict(l=0, r=20, t=30, b=0), height=300,
                          title="Convergence du Gap (cible 0%)")
    return fig_perf, fig_gap

# ----------------------------------------------------------------------
# INTERFACE
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("<h2 style='color:#00E676;'>⚙️ Pilotage</h2>", unsafe_allow_html=True)
    st.markdown("---")
    bonus_toggle = st.toggle("🔮 Activer Bonus Fortuneo (160 €)", value=st.session_state.bonus_active)
    if bonus_toggle != st.session_state.bonus_active:
        st.session_state.bonus_active = bonus_toggle
        st.rerun()
    st.markdown("---")
    st.caption(f"Données au {DATE_ANCHOR.strftime('%d/%m/%Y')}")
    st.caption("Système décisionnel v3 · ANRJ")

st.markdown("<h1 style='color:#FFFFFF;'>📊 Executive Portfolio Management System</h1>", unsafe_allow_html=True)
st.markdown("---")

details = get_portfolio_details(bonus=st.session_state.bonus_active)
prices = details['prices']

# 1. KPIs
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Valeur Totale", f"{details['total_val']:,.0f} €")
with c2:
    st.metric("Performance Réelle", f"{details['performance']:+.2f} %")
with c3:
    st.metric("Écart vs MSCI World", f"{details['gap']:+.2f} %")
with c4:
    st.metric("Progression Lazy", f"{details['progression']:.1f} %")

# 2. Graphiques
fig_perf, fig_gap = build_performance_chart()
st.subheader("📈 Performance Cumulée")
st.plotly_chart(fig_perf, use_container_width=True)
st.plotly_chart(fig_gap, use_container_width=True)

# 3. Satellites
st.subheader("🛰️ Diagnostic Satellites")
ca, cb = st.columns(2)

with ca:
    sc_anrj = score_anrj(prices)
    v_anrj, col_anrj = verdict(sc_anrj)
    st.markdown(f"### ⚗️ Hydrogen (ANRJ) : {v_anrj}")
    fig_g = go.Figure(go.Indicator(
        mode="gauge+number", value=sc_anrj,
        title={'text': "Score", 'font': {'color': 'white'}},
        gauge={'axis': {'range': [0,100]}, 'bar': {'color': col_anrj},
               'steps': [{'range': [0,50], 'color':'rgba(255,0,0,0.2)'},
                         {'range': [50,70], 'color':'rgba(255,165,0,0.2)'},
                         {'range': [70,100], 'color':'rgba(0,255,0,0.2)'}],
               'threshold': {'line': {'color': "white", 'width':2}, 'value':70}}
    ))
    fig_g.update_layout(paper_bgcolor='#0E1117', font={'color': "white"}, margin=dict(l=20,r=20,t=30,b=20))
    st.plotly_chart(fig_g, use_container_width=True)
    st.write(f"Cours : {prices.get('ANRJ.PA', 'N/A')} €")

with cb:
    sc_aasi = score_aasi(prices)
    v_aasi, col_aasi = verdict(sc_aasi)
    st.markdown(f"### 🌏 EM Asia (AASI) : {v_aasi}")
    fig_g2 = go.Figure(go.Indicator(
        mode="gauge+number", value=sc_aasi,
        title={'text': "Score", 'font': {'color': 'white'}},
        gauge={'axis': {'range': [0,100]}, 'bar': {'color': col_aasi},
               'steps': [{'range': [0,50], 'color':'rgba(255,0,0,0.2)'},
                         {'range': [50,70], 'color':'rgba(255,165,0,0.2)'},
                         {'range': [70,100], 'color':'rgba(0,255,0,0.2)'}],
               'threshold': {'line': {'color': "white", 'width':2}, 'value':70}}
    ))
    fig_g2.update_layout(paper_bgcolor='#0E1117', font={'color': "white"}, margin=dict(l=20,r=20,t=30,b=20))
    st.plotly_chart(fig_g2, use_container_width=True)
    tsm_last, tsm_sma = fetch_tsmc_sma()
    dxy = fetch_dxy()
    st.write(f"Cours : {prices.get('AASI.PA', 'N/A')} € | TSMC : {tsm_last} (SMA50:{tsm_sma}) | DXY : {dxy}")

# 4. Transition Lazy
st.markdown("---")
st.subheader("🎯 Transition vers Portefeuille Lazy")
cl, cr = st.columns([1,2])
with cl:
    st.metric("Allocation World", f"{details['world_pct']:.1f} %", delta="Cible 94%")
    st.progress(min(details['progression']/100, 1.0))
with cr:
    st.markdown(f"""
    **Arbitrages nécessaires :**  
    - 💧 Vendre Hydrogène : **{details['sell_hydrogen']:,.0f} €**  
    - 🌏 Vendre EM Asia : **{details['sell_asia']:,.0f} €**  
    - ♻️ Réinvestir total : **{details['total_reinvest']:,.0f} €** → MSCI World
    """)

st.markdown("---")
st.caption("Document strictement personnel · v3 · EPMS")
