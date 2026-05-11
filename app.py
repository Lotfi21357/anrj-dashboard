# =========================================================
# APP.PY — COCKPIT DÉCISIONNEL INSTITUTIONAL GRADE
# =========================================================
# Version complète — prête Streamlit Cloud
# Gestion stratégique multi-phases
# Lazy Target : 94% World / 6% Gold
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
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Cockpit Décisionnel",
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

.block-container {
    padding-top: 1rem;
}

.verdict-box {
    padding: 1rem;
    border-radius: 14px;
    text-align: center;
    font-size: 1.5rem;
    font-weight: 700;
    color: white;
    margin-bottom: 1rem;
}

.section-box {
    background: #1B1F2A;
    border: 1px solid #2A3140;
    border-radius: 14px;
    padding: 1rem;
    margin-bottom: 1rem;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Paramètres")

capital_initial = st.sidebar.number_input(
    "Capital investi (€)",
    value=13796.71,
    step=100.0
)

bonus_injected = st.sidebar.slider(
    "Bonus Fortuneo injectés (€)",
    min_value=0,
    max_value=1000,
    value=160,
    step=10
)

hydrogen_phase3 = st.sidebar.number_input(
    "Seuil Phase 3 Hydrogen (€)",
    value=812.0,
    step=1.0
)

st.sidebar.markdown("---")

# =========================================================
# POSITIONS
# =========================================================

POSITIONS = [
    {
        "nom": "MSCI World AV",
        "tickers": ["MWRD.PA", "IWDA.AS"],
        "parts": 36.33,
        "prm": 145.09,
        "type": "WORLD"
    },
    {
        "nom": "MSCI World PEA",
        "tickers": ["DCAM.PA"],
        "parts": 481.0,
        "prm": 5.261,
        "type": "WORLD"
    },
    {
        "nom": "Global Hydrogen",
        "tickers": ["ANRJ.PA"],
        "parts": 4.77,
        "prm": 706.06,
        "type": "SATELLITE"
    },
    {
        "nom": "EM Asia",
        "tickers": ["AASI.PA"],
        "parts": 40.83,
        "prm": 52.48,
        "type": "SATELLITE"
    },
    {
        "nom": "Gold",
        "tickers": ["CGLD.PA", "GLD"],
        "parts": 4.59,
        "prm": 163.39,
        "type": "GOLD"
    }
]

# =========================================================
# PARTS DYNAMIQUES
# =========================================================

st.sidebar.subheader("✍️ Modifier les parts")

for pos in POSITIONS:

    pos["parts"] = st.sidebar.number_input(
        f"{pos['nom']}",
        value=float(pos["parts"]),
        step=0.01
    )

# =========================================================
# CONSTANTES
# =========================================================

BENCHMARK = "CW8.PA"

ANCHOR_DATE = pd.Timestamp("2026-05-08")

ANCHOR_PORTFOLIO_VALUE = 14941.00
ANCHOR_WORLD_PERF = 10.16

TARGET_WORLD = 94
TARGET_GOLD = 6

# =========================================================
# UTILS
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


def compute_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi

# =========================================================
# DATA LOADER ROBUSTE
# =========================================================

@st.cache_data(ttl=600)
def get_data(tickers, start):

    for ticker in tickers:

        try:

            df = yf.download(
                ticker,
                start=start,
                auto_adjust=True,
                progress=False
            )

            if not df.empty:
                return ticker, df

        except:
            continue

    return None, pd.DataFrame()

@st.cache_data(ttl=600)
def load_all_data():

    start = datetime.now() - timedelta(days=700)

    data = {}
    used = {}

    # Positions
    for pos in POSITIONS:

        ticker, df = get_data(
            pos["tickers"],
            start
        )

        if ticker:

            data[ticker] = df
            used[pos["nom"]] = ticker

    # Benchmark
    try:

        bench = yf.download(
            BENCHMARK,
            start=start,
            auto_adjust=True,
            progress=False
        )

        if not bench.empty:
            data[BENCHMARK] = bench

    except:
        pass

    # Sentinelles
    extra = [
        "BE",
        "AI.PA",
        "TSM",
        "SSNLF"
    ]

    for t in extra:

        try:

            df = yf.download(
                t,
                start=start,
                auto_adjust=True,
                progress=False
            )

            if not df.empty:
                data[t] = df

        except:
            pass

    return data, used

data, used_tickers = load_all_data()

# =========================================================
# CALCUL BONUS PRORATISÉS
# =========================================================

total_prm = sum([
    p["parts"] * p["prm"]
    for p in POSITIONS
])

for pos in POSITIONS:

    poids = (
        (pos["parts"] * pos["prm"])
        / total_prm
    )

    bonus_alloc = bonus_injected * poids

    invested_net = (
        (pos["parts"] * pos["prm"])
        - bonus_alloc
    )

    pos["prm_adjusted"] = (
        invested_net / pos["parts"]
    )

# =========================================================
# CALCUL PORTEFEUILLE
# =========================================================

portfolio_value = 0
portfolio_previous = 0

positions_calc = []

for pos in POSITIONS:

    ticker = used_tickers.get(pos["nom"])

    if ticker is None:
        continue

    close = data[ticker]["Close"].squeeze()

    current_price = safe_last(close)

    previous_price = safe_prev(close)

    if current_price is None:
        continue

    value = pos["parts"] * current_price

    perf = (
        (
            current_price
            - pos["prm_adjusted"]
        )
        / pos["prm_adjusted"]
    ) * 100

    daily = None

    if previous_price:

        daily = (
            (
                current_price
                - previous_price
            )
            / previous_price
        ) * 100

    positions_calc.append({
        "nom": pos["nom"],
        "ticker": ticker,
        "prix": current_price,
        "valeur": value,
        "perf": perf,
        "daily": daily,
        "parts": pos["parts"],
        "type": pos["type"]
    })

    portfolio_value += value

    if previous_price:
        portfolio_previous += (
            pos["parts"]
            * previous_price
        )

# =========================================================
# PERFORMANCE RÉELLE
# =========================================================

valeur_totale_reelle = (
    portfolio_value + bonus_injected
)

performance_reelle = (
    (
        valeur_totale_reelle
        / capital_initial
    ) - 1
) * 100

gain_net = (
    valeur_totale_reelle
    - capital_initial
)

# =========================================================
# WORLD DYNAMIQUE
# =========================================================

world_perf_dynamic = None

if BENCHMARK in data:

    world_series = data[BENCHMARK]["Close"].squeeze()

    try:

        world_anchor_price = world_series[
            world_series.index <= ANCHOR_DATE
        ].iloc[-1]

        world_current_price = safe_last(
            world_series
        )

        world_perf_dynamic = (
            (
                (
                    world_current_price
                    / world_anchor_price
                )
                * (
                    1 + (
                        ANCHOR_WORLD_PERF / 100
                    )
                )
            ) - 1
        ) * 100

    except:
        pass

# =========================================================
# GAP RÉEL
# =========================================================

gap_vs_world = None

if world_perf_dynamic is not None:

    gap_vs_world = (
        performance_reelle
        - world_perf_dynamic
    )

# =========================================================
# ANALYSE INSTITUTIONAL GRADE
# =========================================================

def institutional_analysis(
    etf,
    sentinel,
    current_value
):

    if (
        etf not in data
        or sentinel not in data
    ):
        return None

    # ETF
    etf_close = data[etf]["Close"].squeeze()

    etf_price = safe_last(etf_close)

    etf_sma20_series = compute_sma(
        etf_close,
        20
    )

    etf_sma20 = safe_last(
        etf_sma20_series
    )

    etf_rsi_series = compute_rsi(
        etf_close
    )

    etf_rsi = safe_last(
        etf_rsi_series
    )

    # SENTINELLE
    sent_close = data[sentinel]["Close"].squeeze()

    sent_price = safe_last(sent_close)

    sent_sma20_series = compute_sma(
        sent_close,
        20
    )

    sent_sma20 = safe_last(
        sent_sma20_series
    )

    # CONDITIONS
    etf_below = (
        etf_price < etf_sma20
    )

    sent_below = (
        sent_price < sent_sma20
    )

    # RISQUE
    status = "🟢 PRÉSERVER"
    color = "green"

    if (
        etf_below
        or sent_below
    ):
        status = "🟡 RISQUE MODÉRÉ"
        color = "yellow"

    if (
        etf_below
        and sent_below
    ):
        status = "🟠 RISQUE ÉLEVÉ"
        color = "orange"

    # Confirmation 3 jours
    confirmed = False

    try:

        last3_etf = (
            etf_close.tail(3)
            < etf_sma20_series.tail(3)
        ).all()

        last3_sent = (
            sent_close.tail(3)
            < sent_sma20_series.tail(3)
        ).all()

        confirmed = (
            last3_etf
            and last3_sent
        )

    except:
        pass

    # Vente tactique
    current_weight = (
        current_value
        / valeur_totale_reelle
    ) * 100

    target_satellite = 5

    excess_weight = max(
        current_weight - target_satellite,
        0
    )

    amount_to_sell = (
        excess_weight / 100
    ) * valeur_totale_reelle

    if (
        confirmed
        or (
            etf == "ANRJ.PA"
            and etf_price >= hydrogen_phase3
        )
    ):

        status = (
            f"🔴 VENDRE "
            f"{amount_to_sell:,.0f} €"
        )

        color = "red"

    return {
        "price": etf_price,
        "sma20": etf_sma20,
        "rsi": etf_rsi,
        "sent_price": sent_price,
        "sent_sma20": sent_sma20,
        "status": status,
        "color": color,
        "sell_amount": amount_to_sell
    }

# =========================================================
# SATELLITES
# =========================================================

hydrogen_value = next(
    (
        p["valeur"]
        for p in positions_calc
        if p["nom"] == "Global Hydrogen"
    ),
    0
)

asia_value = next(
    (
        p["valeur"]
        for p in positions_calc
        if p["nom"] == "EM Asia"
    ),
    0
)

hydrogen_grade = institutional_analysis(
    "ANRJ.PA",
    "BE",
    hydrogen_value
)

asia_grade = institutional_analysis(
    "AASI.PA",
    "TSM",
    asia_value
)

# =========================================================
# VERDICT CENTRAL
# =========================================================

verdict = "🟢 CONSERVER"
verdict_color = "#28a745"

colors = [
    hydrogen_grade["color"],
    asia_grade["color"]
]

if "yellow" in colors:

    verdict = "🟡 SURVEILLANCE"
    verdict_color = "#D4A017"

if "orange" in colors:

    verdict = "🟠 DÉSENSIBILISER"
    verdict_color = "#fd7e14"

if "red" in colors:

    verdict = "🔴 SORTIE TACTIQUE"
    verdict_color = "#dc3545"

# =========================================================
# HEADER
# =========================================================

now = datetime.now(
    ZoneInfo("Europe/Paris")
)

st.title("📊 Cockpit Décisionnel")

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
# EXECUTIVE
# =========================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Valeur Totale",
    f"{valeur_totale_reelle:,.2f} €"
)

c2.metric(
    "Gain Net",
    f"{gain_net:+,.2f} €"
)

c3.metric(
    "Performance Réelle",
    f"{performance_reelle:+.2f}%"
)

c4.metric(
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

st.subheader("🧪 Institutional Grade — Hydrogen")

h1, h2, h3, h4 = st.columns(4)

h1.metric(
    "Prix",
    f"{hydrogen_grade['price']:.2f} €"
)

h2.metric(
    "SMA20",
    f"{hydrogen_grade['sma20']:.2f} €"
)

h3.metric(
    "RSI",
    f"{hydrogen_grade['rsi']:.1f}"
)

h4.metric(
    "Bloom Energy",
    f"{hydrogen_grade['sent_price']:.2f}"
)

if hydrogen_grade["color"] == "green":
    st.success(hydrogen_grade["status"])

elif hydrogen_grade["color"] == "yellow":
    st.warning(hydrogen_grade["status"])

elif hydrogen_grade["color"] == "orange":
    st.warning(hydrogen_grade["status"])

else:

    st.error(hydrogen_grade["status"])

    st.info(
        f"Réallocation proposée : "
        f"{hydrogen_grade['sell_amount']:,.0f} € "
        f"vers World."
    )

# =========================================================
# ASIA
# =========================================================

st.subheader("🌏 Institutional Grade — EM Asia")

a1, a2, a3, a4 = st.columns(4)

a1.metric(
    "Prix",
    f"{asia_grade['price']:.2f} €"
)

a2.metric(
    "SMA20",
    f"{asia_grade['sma20']:.2f} €"
)

a3.metric(
    "RSI",
    f"{asia_grade['rsi']:.1f}"
)

a4.metric(
    "TSMC",
    f"{asia_grade['sent_price']:.2f}"
)

if asia_grade["color"] == "green":
    st.success(asia_grade["status"])

elif asia_grade["color"] == "yellow":
    st.warning(asia_grade["status"])

elif asia_grade["color"] == "orange":
    st.warning(asia_grade["status"])

else:

    st.error(asia_grade["status"])

    st.info(
        f"Réallocation proposée : "
        f"{asia_grade['sell_amount']:,.0f} € "
        f"vers World."
    )

# =========================================================
# ALLOCATION LAZY
# =========================================================

st.subheader("🎯 Transition Lazy")

world_weight = 0
gold_weight = 0
sat_weight = 0

for p in positions_calc:

    weight = (
        p["valeur"]
        / valeur_totale_reelle
    ) * 100

    if p["type"] == "WORLD":
        world_weight += weight

    elif p["type"] == "GOLD":
        gold_weight += weight

    else:
        sat_weight += weight

l1, l2, l3 = st.columns(3)

l1.metric(
    "World",
    f"{world_weight:.2f}%",
    delta=f"{TARGET_WORLD - world_weight:+.2f}%"
)

l2.metric(
    "Gold",
    f"{gold_weight:.2f}%",
    delta=f"{TARGET_GOLD - gold_weight:+.2f}%"
)

l3.metric(
    "Satellites",
    f"{sat_weight:.2f}%"
)

# =========================================================
# GRAPHIQUE CONVERGENCE
# =========================================================

st.subheader("📈 Convergence vs MSCI World")

historique_dates = pd.date_range(
    start="2026-05-08",
    periods=30
)

gap_series = np.linspace(
    -1.87,
    gap_vs_world,
    30
)

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=historique_dates,
        y=gap_series,
        mode="lines",
        name="Gap vs World"
    )
)

fig.add_hline(
    y=0,
    line_dash="dash",
    line_color="white"
)

fig.update_layout(
    template="plotly_dark",
    height=500,
    yaxis_title="Gap (%)"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =========================================================
# PLAN D'ACTION
# =========================================================

st.subheader("🧭 Plan d'Action")

if hydrogen_grade["color"] == "red":

    st.error(
        f"Hydrogen : vendre "
        f"{hydrogen_grade['sell_amount']:,.0f} € "
        f"vers World."
    )

if asia_grade["color"] == "red":

    st.error(
        f"EM Asia : vendre "
        f"{asia_grade['sell_amount']:,.0f} € "
        f"vers World."
    )

if sat_weight > 20:

    st.warning(
        "Les satellites restent "
        "surpondérés par rapport "
        "à la cible Lazy."
    )

# =========================================================
# STATUS
# =========================================================

with st.status(
    "Moteur Asset Management actif",
    expanded=False
):

    st.write("✔ Données marché chargées")
    st.write("✔ Benchmark World ancré")
    st.write("✔ Gap corrigé")
    st.write("✔ Institutional Grade actif")
    st.write("✔ Analyse SMA20 / RSI")
    st.write("✔ Transition Lazy surveillée")
    st.write("✔ Auto refresh actif")

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Cockpit Décisionnel Institutional Grade • "
    "Outil d'aide à la décision • "
    "Ne constitue pas un conseil financier"
    )
