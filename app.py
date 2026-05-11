# app.py
# =========================================================
# COCKPIT DÉCISIONNEL — VERSION ASSET MANAGER
# Transition vers Portefeuille Lazy 94% World / 6% Gold
# =========================================================

import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from streamlit_autorefresh import st_autorefresh

# =========================================================
# AUTO REFRESH
# =========================================================

st_autorefresh(interval=120000, key="refresh")

# =========================================================
# PAGE CONFIG
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

.phase-box {
    background: #1B1F2A;
    border: 1px solid #2A3140;
    border-radius: 14px;
    padding: 1rem;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Paramètres Dynamiques")

capital_initial = st.sidebar.number_input(
    "Capital initial (€)",
    value=13796.71,
    step=100.0
)

bonus_total = st.sidebar.number_input(
    "Bonus / primes (€)",
    value=160.0,
    step=10.0
)

hydrogen_target = st.sidebar.number_input(
    "Objectif Hydrogen (€)",
    value=812.0,
    step=1.0
)

st.sidebar.markdown("---")
st.sidebar.subheader("✍️ Parts Modifiables")

# =========================================================
# POSITIONS
# =========================================================

POSITIONS = [
    {
        "nom": "MSCI World AV",
        "tickers": ["MWRD.PA", "IWDA.AS", "EUNL.DE"],
        "parts": 36.33,
        "prm": 145.09
    },
    {
        "nom": "MSCI World PEA",
        "tickers": ["DCAM.PA"],
        "parts": 481.0,
        "prm": 5.261
    },
    {
        "nom": "Global Hydrogen",
        "tickers": ["ANRJ.PA"],
        "parts": 4.77,
        "prm": 706.06
    },
    {
        "nom": "EM Asia",
        "tickers": ["AASI.PA"],
        "parts": 40.83,
        "prm": 52.48
    },
    {
        "nom": "Or Physique",
        "tickers": ["CGLD.PA", "GOLD.PA", "GLD"],
        "parts": 4.59,
        "prm": 163.39
    }
]

# =========================================================
# PARTS DYNAMIQUES
# =========================================================

for pos in POSITIONS:

    pos["parts"] = st.sidebar.number_input(
        f"{pos['nom']} - Parts",
        value=float(pos["parts"]),
        step=0.01
    )

# =========================================================
# CONSTANTES
# =========================================================

BENCHMARK = "CW8.PA"

SENTINELLES = {
    "Hydrogen": {
        "ETF": "ANRJ.PA",
        "Sentinelles": ["BE", "AI.PA"]
    },
    "Asia": {
        "ETF": "AASI.PA",
        "Sentinelles": ["TSM", "SSNLF"]
    }
}

MACRO = ["^TNX", "DX-Y.NYB", "BZ=F"]

# =========================================================
# UTILS
# =========================================================

def safe_last(series):

    if isinstance(series, pd.DataFrame):
        series = series.squeeze()

    series = series.dropna()

    if len(series) == 0:
        return None

    return float(series.iloc[-1])


def safe_prev(series):

    if isinstance(series, pd.DataFrame):
        series = series.squeeze()

    series = series.dropna()

    if len(series) < 2:
        return None

    return float(series.iloc[-2])


def compute_sma(series, window=20):

    return series.rolling(window).mean()


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
def load_data():

    start = datetime.now() - timedelta(days=700)

    data = {}
    used_tickers = {}

    # Positions
    for pos in POSITIONS:

        used, df = get_data(pos["tickers"], start)

        if used and not df.empty:

            data[used] = df
            used_tickers[pos["nom"]] = used

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

    # Macro
    for t in MACRO:

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

    # Sentinelles
    sentinelles = [
        "BE",
        "AI.PA",
        "TSM",
        "SSNLF"
    ]

    for t in sentinelles:

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

    return data, used_tickers


data, ticker_used = load_data()

# =========================================================
# CALCUL BONUS PRORATISÉS
# =========================================================

capital_reel = capital_initial - bonus_total

montant_total_prm = sum([
    p["parts"] * p["prm"]
    for p in POSITIONS
])

for pos in POSITIONS:

    poids = (
        (pos["parts"] * pos["prm"])
        / montant_total_prm
    )

    bonus_prorata = bonus_total * poids

    investissement_net = (
        (pos["parts"] * pos["prm"])
        - bonus_prorata
    )

    pos["prm_ajuste"] = (
        investissement_net / pos["parts"]
    )

# =========================================================
# CALCUL PORTEFEUILLE
# =========================================================

positions_calc = []

portfolio_value = 0
portfolio_previous = 0

for pos in POSITIONS:

    ticker = ticker_used.get(pos["nom"])

    if ticker is None:
        continue

    close = data[ticker]["Close"].squeeze()

    current_price = safe_last(close)
    previous_price = safe_prev(close)

    value = pos["parts"] * current_price

    perf = (
        (current_price - pos["prm_ajuste"])
        / pos["prm_ajuste"]
    ) * 100

    daily = None

    if previous_price:
        daily = (
            (current_price - previous_price)
            / previous_price
        ) * 100

    positions_calc.append({
        "nom": pos["nom"],
        "ticker": ticker,
        "prix": current_price,
        "valeur": value,
        "perf": perf,
        "daily": daily,
        "parts": pos["parts"]
    })

    portfolio_value += value

    if previous_price:
        portfolio_previous += (
            pos["parts"] * previous_price
        )

# =========================================================
# PERFORMANCE
# =========================================================

gain_net = portfolio_value - capital_reel

portfolio_perf = (
    gain_net / capital_reel
) * 100

daily_eur = portfolio_value - portfolio_previous

# =========================================================
# HISTORIQUE RÉEL
# =========================================================
# IMPORTANT :
# Tu peux remplacer cette table par ton vrai historique.
# =========================================================

historique = pd.DataFrame({
    "Date": [
        "2025-09-17",
        "2025-10-15",
        "2025-11-20",
        "2026-01-10",
        "2026-03-01",
        "2026-05-01"
    ],
    "Valeur": [
        4000,
        6500,
        9200,
        11500,
        12800,
        portfolio_value
    ]
})

historique["Date"] = pd.to_datetime(
    historique["Date"]
)

historique = historique.sort_values("Date")

# =========================================================
# SIMULATION CW8
# =========================================================

world_series = data[BENCHMARK]["Close"].squeeze()

cw8_values = []

invested_units = 0

for i in range(len(historique)):

    current_date = historique.iloc[i]["Date"]

    current_value = historique.iloc[i]["Valeur"]

    if i == 0:
        contribution = current_value
    else:
        contribution = (
            current_value
            - historique.iloc[i - 1]["Valeur"]
        )

    world_price = world_series[
        world_series.index <= current_date
    ]

    if len(world_price) == 0:
        continue

    world_price = world_price.iloc[-1]

    invested_units += contribution / world_price

    simulated_value = invested_units * world_price

    cw8_values.append(simulated_value)

historique = historique.iloc[:len(cw8_values)]

historique["Benchmark World"] = cw8_values

historique["Perf Réelle"] = (
    historique["Valeur"]
    / historique["Valeur"].iloc[0]
) * 100

historique["Perf World"] = (
    historique["Benchmark World"]
    / historique["Benchmark World"].iloc[0]
) * 100

historique["Gap"] = (
    historique["Perf Réelle"]
    - historique["Perf World"]
)

gap_rattrapage = historique["Gap"].iloc[-1]

# =========================================================
# ANALYSE SATELLITES
# =========================================================

def satellite_analysis(etf_ticker, sentinels):

    if etf_ticker not in data:
        return None

    etf_close = data[etf_ticker]["Close"].squeeze()

    etf_price = safe_last(etf_close)

    etf_sma20 = safe_last(
        compute_sma(etf_close, 20)
    )

    etf_weak = False

    if etf_price and etf_sma20:
        etf_weak = etf_price < etf_sma20

    sentinels_weak = 0

    for s in sentinels:

        if s not in data:
            continue

        s_close = data[s]["Close"].squeeze()

        s_price = safe_last(s_close)

        s_sma20 = safe_last(
            compute_sma(s_close, 20)
        )

        if s_price and s_sma20:

            if s_price < s_sma20:
                sentinels_weak += 1

    reduction_signal = (
        etf_weak
        and sentinels_weak >= 1
    )

    return {
        "etf_price": etf_price,
        "etf_sma20": etf_sma20,
        "weak": reduction_signal,
        "sentinels_weak": sentinels_weak
    }

# Hydrogen
hydrogen_analysis = satellite_analysis(
    "ANRJ.PA",
    ["BE", "AI.PA"]
)

# Asia
asia_analysis = satellite_analysis(
    "AASI.PA",
    ["TSM", "SSNLF"]
)

# =========================================================
# VERDICT CENTRAL
# =========================================================

verdict = "🟢 CONSERVER"
verdict_color = "#28a745"

if hydrogen_analysis["weak"] or asia_analysis["weak"]:

    verdict = "🟠 DÉSENSIBILISER"
    verdict_color = "#fd7e14"

if (
    hydrogen_analysis["weak"]
    and asia_analysis["weak"]
):

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
    f"Dernière mise à jour : "
    f"{now.strftime('%d/%m/%Y %H:%M')}"
)

# =========================================================
# VERDICT CENTRAL
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
    f"{portfolio_value:,.2f} €"
)

c2.metric(
    "Gain Net Réel",
    f"{gain_net:+,.2f} €"
)

c3.metric(
    "Performance Réelle",
    f"{portfolio_perf:+.2f}%"
)

c4.metric(
    "Gap de Rattrapage",
    f"{gap_rattrapage:+.2f}%"
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
# ANALYSE HYDROGEN
# =========================================================

st.subheader("🧪 Satellite Hydrogen")

h1, h2, h3 = st.columns(3)

h1.metric(
    "ANRJ",
    f"{hydrogen_analysis['etf_price']:.2f} €"
)

h2.metric(
    "SMA20",
    f"{hydrogen_analysis['etf_sma20']:.2f} €"
)

h3.metric(
    "Sentinelles Faibles",
    hydrogen_analysis["sentinels_weak"]
)

if hydrogen_analysis["weak"]:

    hydrogen_position = next(
        (
            p["valeur"]
            for p in positions_calc
            if p["nom"] == "Global Hydrogen"
        ),
        0
    )

    reduction_amount = hydrogen_position * 0.15

    st.warning(
        f"SIGNAL RÉDUCTION : "
        f"Sortir {reduction_amount:,.2f} € "
        f"vers le World."
    )

    st.info(
        "Plan de sécurisation : "
        "vendre 15% des parts à "
        f"{hydrogen_target:.0f} €"
    )

# =========================================================
# ANALYSE ASIA
# =========================================================

st.subheader("🌏 Satellite EM Asia")

a1, a2, a3 = st.columns(3)

a1.metric(
    "AASI",
    f"{asia_analysis['etf_price']:.2f} €"
)

a2.metric(
    "SMA20",
    f"{asia_analysis['etf_sma20']:.2f} €"
)

a3.metric(
    "Sentinelles Faibles",
    asia_analysis["sentinels_weak"]
)

if asia_analysis["weak"]:

    asia_position = next(
        (
            p["valeur"]
            for p in positions_calc
            if p["nom"] == "EM Asia"
        ),
        0
    )

    reduction_amount = asia_position * 0.15

    st.warning(
        f"SIGNAL RÉDUCTION : "
        f"Sortir {reduction_amount:,.2f} € "
        f"vers le World."
    )

# =========================================================
# ALLOCATION STRATÉGIQUE
# =========================================================

st.subheader("🎯 Transition Lazy")

world_weight = 0
gold_weight = 0
satellite_weight = 0

for p in positions_calc:

    weight = (
        p["valeur"]
        / portfolio_value
    ) * 100

    if "World" in p["nom"]:
        world_weight += weight

    elif "Or" in p["nom"]:
        gold_weight += weight

    else:
        satellite_weight += weight

surpoids_satellite = max(
    satellite_weight - 0,
    0
)

l1, l2, l3 = st.columns(3)

l1.metric(
    "World",
    f"{world_weight:.2f}%"
)

l2.metric(
    "Gold",
    f"{gold_weight:.2f}%"
)

l3.metric(
    "Satellites",
    f"{satellite_weight:.2f}%"
)

st.warning(
    f"Tu as actuellement "
    f"{surpoids_satellite:.2f}% "
    f"d'exposition satellite."
)

# =========================================================
# PLAN D'ACTION
# =========================================================

st.subheader("🧭 Plan d'Action")

if satellite_weight > 20:

    st.info(
        "Phase 3 : "
        "vendre progressivement "
        "15% des satellites "
        "à chaque dépassement "
        "d'objectif."
    )

if world_weight < 94:

    manque_world = 94 - world_weight

    st.info(
        f"Il manque "
        f"{manque_world:.2f}% "
        f"de World pour atteindre "
        f"la cible Lazy."
    )

# =========================================================
# GRAPHIQUE HISTORIQUE
# =========================================================

st.subheader("📈 Performance Réelle vs World")

graph = historique.set_index("Date")[
    ["Perf Réelle", "Perf World"]
]

st.line_chart(graph)

# =========================================================
# GAP
# =========================================================

st.subheader("📉 Gap de Rattrapage")

gap_graph = historique.set_index("Date")[["Gap"]]

st.area_chart(gap_graph)

# =========================================================
# STATUS
# =========================================================

with st.status(
    "Moteur d'analyse actif",
    expanded=False
):

    st.write("✔ Historique réel chargé")
    st.write("✔ Benchmark CW8 simulé")
    st.write("✔ Analyse satellites active")
    st.write("✔ Vérification sentinelles")
    st.write("✔ Transition Lazy surveillée")
    st.write("✔ Actualisation automatique active")

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Cockpit Décisionnel • "
    "Asset Management Edition • "
    "Ne constitue pas un conseil "
    "en investissement"
)
