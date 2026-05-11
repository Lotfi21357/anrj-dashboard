# =========================================================
# APP.PY — HYBRID COCKPIT
# Institutional Grade Portfolio Dashboard
# =========================================================

import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

from streamlit_autorefresh import st_autorefresh

# =========================================================
# AUTO REFRESH
# =========================================================

st_autorefresh(interval=120000, key="refresh")

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Hybrid Cockpit",
    page_icon="📊",
    layout="wide"
)

# =========================================================
# STYLE
# =========================================================

st.markdown("""
<style>

.stApp {
    background-color: #0E1117;
    color: white;
}

.verdict-box {
    padding: 1rem;
    border-radius: 16px;
    text-align: center;
    font-size: 1.5rem;
    font-weight: 700;
    color: white;
    margin-bottom: 1rem;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Paramètres")

capital_investi = st.sidebar.number_input(
    "Capital investi (€)",
    value=13796.71,
    step=100.0
)

bonus_fortuneo = st.sidebar.slider(
    "Bonus Fortuneo (€)",
    min_value=0,
    max_value=1000,
    value=160,
    step=10
)

hydrogen_alert = st.sidebar.number_input(
    "Seuil Hydrogen Phase 3 (€)",
    value=812.0,
    step=1.0
)

# =========================================================
# POSITIONS FIXES
# =========================================================

POSITIONS = [
    {
        "nom": "World PEA",
        "ticker": "DCAM.PA",
        "parts": 481.0,
        "prm": 5.261,
        "type": "WORLD"
    },
    {
        "nom": "Hydrogen",
        "ticker": "ANRJ.PA",
        "parts": 4.77,
        "prm": 706.06,
        "type": "SATELLITE"
    },
    {
        "nom": "EM Asia",
        "ticker": "AASI.PA",
        "parts": 40.83,
        "prm": 52.48,
        "type": "SATELLITE"
    },
    {
        "nom": "World AV",
        "ticker": "MWRD.PA",
        "parts": 36.33,
        "prm": 145.09,
        "type": "WORLD"
    },
    {
        "nom": "Gold",
        "ticker": "CGLD.PA",
        "parts": 4.59,
        "prm": 163.39,
        "type": "GOLD"
    }
]

# =========================================================
# CONSTANTES
# =========================================================

BENCHMARK = "CW8.PA"

ANCHOR_DATE = pd.Timestamp("2026-05-08")

INITIAL_GAP = -1.87

TARGET_WORLD = 94
TARGET_GOLD = 6

# =========================================================
# HELPERS
# =========================================================

def safe_last(series):

    try:
        return float(series.dropna().iloc[-1])
    except:
        return None


def safe_prev(series):

    try:
        return float(series.dropna().iloc[-2])
    except:
        return None


def compute_sma(series, window=20):

    return series.rolling(window).mean()

# =========================================================
# DATA LOADER
# =========================================================

@st.cache_data(ttl=600)
def load_data():

    start = datetime.now() - timedelta(days=365)

    tickers = [
        "DCAM.PA",
        "ANRJ.PA",
        "AASI.PA",
        "MWRD.PA",
        "CGLD.PA",
        "CW8.PA",
        "TSM",
        "SSNLF",
        "BE"
    ]

    data = {}

    for ticker in tickers:

        try:

            df = yf.download(
                ticker,
                start=start,
                auto_adjust=True,
                progress=False
            )

            if not df.empty:
                data[ticker] = df

        except:
            pass

    return data

data = load_data()

# =========================================================
# CALCUL PORTEFEUILLE
# =========================================================

positions_calc = []

valeur_totale = 0

for pos in POSITIONS:

    ticker = pos["ticker"]

    if ticker not in data:
        continue

    close = data[ticker]["Close"].squeeze()

    current_price = safe_last(close)

    previous_price = safe_prev(close)

    if current_price is None:
        continue

    valeur = pos["parts"] * current_price

    perf = (
        (
            current_price - pos["prm"]
        ) / pos["prm"]
    ) * 100

    variation = None

    if previous_price:

        variation = (
            (
                current_price
                - previous_price
            ) / previous_price
        ) * 100

    positions_calc.append({
        "nom": pos["nom"],
        "ticker": ticker,
        "prix": current_price,
        "valeur": valeur,
        "perf": perf,
        "variation": variation,
        "type": pos["type"]
    })

    valeur_totale += valeur

# =========================================================
# CAPITAL AJUSTÉ BONUS
# =========================================================

capital_ajuste = (
    capital_investi
    - bonus_fortuneo
)

gain_reel = (
    valeur_totale
    - capital_ajuste
)

performance_portefeuille = (
    (
        valeur_totale
        / capital_ajuste
    ) - 1
) * 100

# =========================================================
# GAP VS WORLD
# =========================================================

gap_vs_world = None

if BENCHMARK in data:

    world_close = data[
        BENCHMARK
    ]["Close"].squeeze()

    try:

        world_anchor = world_close[
            world_close.index <= ANCHOR_DATE
        ].iloc[-1]

        world_current = safe_last(
            world_close
        )

        world_perf_since_anchor = (
            (
                world_current
                / world_anchor
            ) - 1
        ) * 100

        benchmark_reference = (
            world_perf_since_anchor
            + abs(INITIAL_GAP)
        )

        gap_vs_world = (
            performance_portefeuille
            - benchmark_reference
        )

    except:
        gap_vs_world = None

# =========================================================
# ANALYSE SATELLITE
# =========================================================

def analyze_satellite(
    etf,
    sentinel,
    position_value
):

    if (
        etf not in data
        or sentinel not in data
    ):
        return None

    etf_close = data[
        etf
    ]["Close"].squeeze()

    etf_price = safe_last(
        etf_close
    )

    etf_sma20 = safe_last(
        compute_sma(etf_close, 20)
    )

    sentinel_close = data[
        sentinel
    ]["Close"].squeeze()

    sentinel_price = safe_last(
        sentinel_close
    )

    sentinel_sma20 = safe_last(
        compute_sma(sentinel_close, 20)
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = "🟢 PRÉSERVER"
    color = "green"

    if etf_price < etf_sma20:

        status = "🟡 RISQUE MODÉRÉ"
        color = "orange"

    if (
        etf_price < etf_sma20
        and sentinel_price < sentinel_sma20
    ):

        # Objectif Lazy 5%
        current_weight = (
            position_value
            / valeur_totale
        ) * 100

        excess_weight = max(
            current_weight - 5,
            0
        )

        sell_amount = (
            excess_weight / 100
        ) * valeur_totale

        status = (
            f"🔴 VENDRE "
            f"{sell_amount:,.0f} €"
        )

        color = "red"

    return {
        "price": etf_price,
        "sma20": etf_sma20,
        "sentinel": sentinel_price,
        "sentinel_sma20": sentinel_sma20,
        "status": status,
        "color": color
    }

# =========================================================
# ANALYSE HYDROGEN
# =========================================================

hydrogen_value = next(
    (
        p["valeur"]
        for p in positions_calc
        if p["ticker"] == "ANRJ.PA"
    ),
    0
)

hydrogen = analyze_satellite(
    "ANRJ.PA",
    "BE",
    hydrogen_value
)

# =========================================================
# ANALYSE ASIA
# =========================================================

asia_value = next(
    (
        p["valeur"]
        for p in positions_calc
        if p["ticker"] == "AASI.PA"
    ),
    0
)

asia = analyze_satellite(
    "AASI.PA",
    "TSM",
    asia_value
)

# =========================================================
# VERDICT GLOBAL
# =========================================================

verdict = "🟢 CONSERVER"
verdict_color = "#28a745"

colors = [
    hydrogen["color"],
    asia["color"]
]

if "orange" in colors:

    verdict = "🟡 SURVEILLANCE"
    verdict_color = "#D4A017"

if "red" in colors:

    verdict = "🔴 DÉSENSIBILISER"
    verdict_color = "#dc3545"

# =========================================================
# HEADER
# =========================================================

now = datetime.now(
    ZoneInfo("Europe/Paris")
)

st.title("📊 Hybrid Cockpit")

st.caption(
    f"Mise à jour : "
    f"{now.strftime('%d/%m/%Y %H:%M')}"
)

# =========================================================
# VERDICT
# =========================================================

st.markdown(f"""
<div class="verdict-box"
style="background:{verdict_color}">
{verdict}
</div>
""", unsafe_allow_html=True)

# =========================================================
# KPIs
# =========================================================

k1, k2, k3 = st.columns(3)

k1.metric(
    "Valeur Totale",
    f"{valeur_totale:,.2f} €"
)

k2.metric(
    "Gain Réel",
    f"{gain_reel:+,.2f} €"
)

k3.metric(
    "Gap vs World",
    f"{gap_vs_world:+.2f}%"
)

# =========================================================
# POSITIONS
# =========================================================

st.subheader("📦 Positions")

cols = st.columns(len(positions_calc))

for i, p in enumerate(positions_calc):

    with cols[i]:

        st.metric(
            p["nom"],
            f"{p['prix']:.2f} €",
            delta=f"{p['perf']:+.2f}%"
        )

# =========================================================
# HYDROGEN
# =========================================================

st.subheader("🧪 Diagnostic Hydrogen")

h1, h2, h3 = st.columns(3)

h1.metric(
    "Prix",
    f"{hydrogen['price']:.2f} €"
)

h2.metric(
    "SMA20",
    f"{hydrogen['sma20']:.2f} €"
)

h3.metric(
    "Bloom Energy",
    f"{hydrogen['sentinel']:.2f} €"
)

if hydrogen["color"] == "green":
    st.success(hydrogen["status"])

elif hydrogen["color"] == "orange":
    st.warning(hydrogen["status"])

else:

    st.error(hydrogen["status"])

    st.info(
        "Vendre une partie "
        "pour renforcer World."
    )

# Hydrogen > 812€
if hydrogen["price"] >= hydrogen_alert:

    st.error(
        "Hydrogen > 812€ : "
        "Phase 3 atteinte."
    )

# =========================================================
# ASIA
# =========================================================

st.subheader("🌏 Diagnostic EM Asia")

a1, a2, a3 = st.columns(3)

a1.metric(
    "Prix",
    f"{asia['price']:.2f} €"
)

a2.metric(
    "SMA20",
    f"{asia['sma20']:.2f} €"
)

a3.metric(
    "TSMC",
    f"{asia['sentinel']:.2f} €"
)

if asia["color"] == "green":
    st.success(asia["status"])

elif asia["color"] == "orange":
    st.warning(asia["status"])

else:

    st.error(asia["status"])

    st.info(
        "Réduire EM Asia "
        "et renforcer World."
    )

# =========================================================
# ALLOCATION
# =========================================================

st.subheader("🎯 Allocation actuelle vs cible Lazy")

world_value = sum([
    p["valeur"]
    for p in positions_calc
    if p["type"] == "WORLD"
])

gold_value = sum([
    p["valeur"]
    for p in positions_calc
    if p["type"] == "GOLD"
])

satellite_value = sum([
    p["valeur"]
    for p in positions_calc
    if p["type"] == "SATELLITE"
])

current_alloc = [
    world_value,
    gold_value,
    satellite_value
]

fig = go.Figure()

fig.add_trace(
    go.Pie(
        labels=[
            "World",
            "Gold",
            "Satellites"
        ],
        values=current_alloc,
        hole=0.45
    )
)

fig.update_layout(
    template="plotly_dark",
    height=500
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =========================================================
# CIBLE
# =========================================================

cw = (
    world_value
    / valeur_totale
) * 100

cg = (
    gold_value
    / valeur_totale
) * 100

cs = (
    satellite_value
    / valeur_totale
) * 100

t1, t2, t3 = st.columns(3)

t1.metric(
    "World",
    f"{cw:.2f}%",
    delta=f"{TARGET_WORLD - cw:+.2f}%"
)

t2.metric(
    "Gold",
    f"{cg:.2f}%",
    delta=f"{TARGET_GOLD - cg:+.2f}%"
)

t3.metric(
    "Satellites",
    f"{cs:.2f}%"
)

# =========================================================
# SENTINELLES
# =========================================================

st.subheader("📡 Sentinelles")

sentinelles = []

for ticker in [
    "TSM",
    "SSNLF",
    "BE"
]:

    if ticker not in data:
        continue

    close = data[ticker]["Close"].squeeze()

    last_price = safe_last(close)
    prev_price = safe_prev(close)

    variation = None

    if prev_price:

        variation = (
            (
                last_price
                - prev_price
            ) / prev_price
        ) * 100

    sentinelles.append({
        "Ticker": ticker,
        "Cours": round(last_price, 2),
        "Variation 24h (%)": round(variation, 2)
    })

sent_df = pd.DataFrame(
    sentinelles
)

st.dataframe(
    sent_df,
    use_container_width=True
)

# =========================================================
# STATUS
# =========================================================

with st.status(
    "Moteur Quant actif",
    expanded=False
):

    st.write("✔ Calcul PRM réel")
    st.write("✔ Gap vs World corrigé")
    st.write("✔ SMA20 satellites")
    st.write("✔ Sentinelles actives")
    st.write("✔ Allocation Lazy surveillée")
    st.write("✔ Bonus Fortuneo intégré")
    st.write("✔ Auto refresh actif")

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Hybrid Cockpit • "
    "Institutional Grade Dashboard • "
    "Outil d'aide à la décision"
)
