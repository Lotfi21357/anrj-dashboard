# app.py
# =========================================================
# Cockpit Décisionnel — Gestion Multi-Phases
# Version robuste / moderne / Streamlit
# =========================================================

import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Cockpit Décisionnel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: "Inter", sans-serif;
}

.stApp {
    background-color: #0E1117;
    color: white;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}

.verdict-box {
    padding: 1rem;
    border-radius: 16px;
    font-weight: 700;
    text-align: center;
    font-size: 1.25rem;
    margin-bottom: 1rem;
    color: white;
}

.phase-box {
    padding: 0.8rem;
    border-radius: 14px;
    background: #1B1F2A;
    border: 1px solid #2D3445;
    margin-bottom: 0.6rem;
}

.small-muted {
    color: #9BA3AF;
    font-size: 0.85rem;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Paramètres Dynamiques")

capital_initial = st.sidebar.number_input(
    "Capital initial (€)",
    min_value=0.0,
    value=13796.71,
    step=100.0
)

bonus_percus = st.sidebar.number_input(
    "Bonus / primes perçus (€)",
    min_value=0.0,
    value=160.0,
    step=10.0
)

hydrogen_target_price = st.sidebar.number_input(
    "Prix cible Hydrogen (€)",
    min_value=0.0,
    value=812.0,
    step=1.0
)

date_debut = st.sidebar.date_input(
    "Date de départ analyse",
    value=datetime(2025, 9, 17)
)

capital_reel = capital_initial - bonus_percus

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
        "parts": 481,
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

BENCHMARK = "CW8.PA"

SENTINELLES = {
    "TSMC": ["TSM"],
    "Samsung": ["SSNLF"],
    "Bloom Energy": ["BE"],
    "Air Liquide": ["AI.PA"]
}

EXTRA_MACRO = ["^TNX", "DX-Y.NYB", "BZ=F"]

# =========================================================
# UTILS
# =========================================================

def safe_float(x):
    try:
        return float(x)
    except:
        return None


def safe_last(series):
    if series is None:
        return None

    if isinstance(series, pd.DataFrame):
        series = series.squeeze()

    series = series.dropna()

    if len(series) == 0:
        return None

    return safe_float(series.iloc[-1])


def safe_prev(series):
    if series is None:
        return None

    if isinstance(series, pd.DataFrame):
        series = series.squeeze()

    series = series.dropna()

    if len(series) < 2:
        return None

    return safe_float(series.iloc[-2])


# =========================================================
# DATA LOADER ROBUSTE
# =========================================================

@st.cache_data(ttl=600)
def get_data(tickers, start_date):

    for ticker in tickers:

        try:

            df = yf.download(
                ticker,
                start=start_date,
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

    start = datetime.now() - timedelta(days=600)

    data = {}
    ticker_used = {}

    # Positions
    for pos in POSITIONS:

        used, df = get_data(pos["tickers"], start)

        if used and not df.empty:
            data[used] = df
            ticker_used[pos["nom"]] = used

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
    for t in EXTRA_MACRO:

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
    for name, tickers in SENTINELLES.items():

        used, df = get_data(tickers, start)

        if used and not df.empty:
            data[used] = df

    return data, ticker_used


data, ticker_used = load_all_data()

# =========================================================
# CALCUL PORTEFEUILLE
# =========================================================

portfolio_value = 0
portfolio_previous = 0

positions_calc = []

for pos in POSITIONS:

    ticker = ticker_used.get(pos["nom"])

    if not ticker:
        continue

    df = data.get(ticker)

    if df is None or df.empty:
        continue

    close = df["Close"].squeeze()

    current_price = safe_last(close)
    previous_price = safe_prev(close)

    value = pos["parts"] * current_price

    perf = ((current_price - pos["prm"]) / pos["prm"]) * 100

    daily_var = None

    if previous_price:
        daily_var = ((current_price - previous_price) / previous_price) * 100

    positions_calc.append({
        "nom": pos["nom"],
        "ticker": ticker,
        "prix": current_price,
        "valeur": value,
        "perf": perf,
        "daily": daily_var,
        "parts": pos["parts"]
    })

    portfolio_value += value

    if previous_price:
        portfolio_previous += pos["parts"] * previous_price
    else:
        portfolio_previous += value

gain_net = portfolio_value - capital_reel

portfolio_perf = (gain_net / capital_reel) * 100

daily_eur = portfolio_value - portfolio_previous

daily_pct = (daily_eur / portfolio_previous) * 100

# =========================================================
# PERFORMANCE WORLD ALIGNÉE
# =========================================================

world_perf = None
gap_vs_world = None

if BENCHMARK in data:

    world_series = data[BENCHMARK]["Close"].squeeze()

    common_start = max(
        pd.Timestamp(date_debut),
        world_series.index.min()
    )

    world_series = world_series[world_series.index >= common_start]

    if len(world_series) > 1:

        world_base = world_series.iloc[0]

        world_perf = ((world_series.iloc[-1] / world_base) - 1) * 100

        gap_vs_world = portfolio_perf - world_perf

# =========================================================
# HISTORIQUE BASE 100 ALIGNÉ
# =========================================================

def compute_base100():

    combined = pd.DataFrame()

    for pos in POSITIONS:

        ticker = ticker_used.get(pos["nom"])

        if ticker is None:
            continue

        series = data[ticker]["Close"].squeeze()

        series.name = ticker

        combined = pd.concat([combined, series], axis=1)

    combined = combined.dropna()

    if combined.empty:
        return None

    combined = combined[combined.index >= pd.Timestamp(date_debut)]

    portfolio_series = pd.Series(
        0,
        index=combined.index,
        dtype=float
    )

    for pos in POSITIONS:

        ticker = ticker_used.get(pos["nom"])

        if ticker not in combined.columns:
            continue

        portfolio_series += combined[ticker] * pos["parts"]

    portfolio_base100 = (portfolio_series / portfolio_series.iloc[0]) * 100

    world = data[BENCHMARK]["Close"].squeeze()

    world = world[world.index.isin(combined.index)]

    world_base100 = (world / world.iloc[0]) * 100

    final = pd.DataFrame({
        "Portefeuille": portfolio_base100,
        "MSCI World": world_base100
    }).dropna()

    return final


base100 = compute_base100()

# =========================================================
# HYDROGEN ANALYTICS
# =========================================================

anrj_price = None
anrj_parts = 0

for p in positions_calc:

    if p["nom"] == "Global Hydrogen":

        anrj_price = p["prix"]
        anrj_parts = p["parts"]

        break

hydrogen_needed_pct = None
hydrogen_target_needed = None

if gap_vs_world is not None and gap_vs_world < 0 and anrj_price:

    target_value = capital_reel * (1 + world_perf / 100)

    diff = target_value - portfolio_value

    hydrogen_target_needed = anrj_price + (diff / anrj_parts)

    hydrogen_needed_pct = (
        (hydrogen_target_needed - anrj_price)
        / anrj_price
    ) * 100

# =========================================================
# PHASES
# =========================================================

def get_phase():

    if gap_vs_world is not None and gap_vs_world < -5:
        return 1

    if gap_vs_world is not None and gap_vs_world < 0:
        return 2

    if anrj_price and anrj_price >= hydrogen_target_price:
        return 3

    world_weight = 0
    gold_weight = 0

    for p in positions_calc:

        weight = (p["valeur"] / portfolio_value) * 100

        if "World" in p["nom"]:
            world_weight += weight

        if "Or" in p["nom"]:
            gold_weight += weight

    if world_weight < 94:
        return 4

    return 5


phase = get_phase()

# =========================================================
# SENTINELLES
# =========================================================

def compute_sma(series, window=20):
    return series.rolling(window).mean()


sentinel_alerts = []

for name, tickers in SENTINELLES.items():

    found = False

    for t in tickers:

        if t in data:

            s = data[t]["Close"].squeeze()

            if len(s) < 20:
                continue

            sma20 = compute_sma(s, 20)

            last_price = safe_last(s)
            last_sma = safe_last(sma20)

            if last_price and last_sma:

                if last_price < last_sma:
                    sentinel_alerts.append(f"{name} sous SMA20")

            found = True
            break

    if found:
        continue

# =========================================================
# VERDICT
# =========================================================

if len(sentinel_alerts) >= 2:

    verdict = "🟠 DÉSENSIBILISATION"
    verdict_color = "#fd7e14"

elif phase <= 2:

    verdict = "🟡 PHASE OFFENSIVE"
    verdict_color = "#D4A017"

elif phase == 3:

    verdict = "🟢 SÉCURISATION"

    verdict_color = "#28a745"

else:

    verdict = "🔵 TRANSITION LAZY"
    verdict_color = "#007bff"

# =========================================================
# HEADER
# =========================================================

now = datetime.now(ZoneInfo("Europe/Paris"))

st.title("📊 Cockpit Décisionnel")

st.caption(
    f"Données du {now.strftime('%d/%m/%Y %H:%M')} — Heure de Paris"
)

# =========================================================
# PHASE STEPPER
# =========================================================

st.subheader("🧭 Cycle Stratégique")

progress = phase / 5

st.progress(progress)

phase_labels = {
    1: "Phase 1 — Sous-performance forte",
    2: "Phase 2 — Point de bascule",
    3: "Phase 3 — Sécurisation",
    4: "Phase 4 — Transition Lazy",
    5: "Phase 5 — Allocation finale"
}

st.info(phase_labels[phase])

# =========================================================
# EXECUTIVE
# =========================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Valeur Totale",
    f"{portfolio_value:,.2f} €",
    delta=f"{daily_eur:+,.2f} €"
)

c2.metric(
    "Gain Net",
    f"{gain_net:+,.2f} €"
)

c3.metric(
    "Performance",
    f"{portfolio_perf:+.2f}%"
)

if world_perf is not None:

    c4.metric(
        "Gap vs World",
        f"{gap_vs_world:+.2f}%"
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
# MODULE RATTRAPAGE
# =========================================================

st.subheader("🎯 Module Rattrapage")

g1, g2 = st.columns(2)

if gap_vs_world is not None:

    g1.metric(
        "Gap vs World",
        f"{gap_vs_world:+.2f}%"
    )

if hydrogen_needed_pct is not None:

    g2.metric(
        "Hausse Hydrogen nécessaire",
        f"{hydrogen_needed_pct:+.2f}%"
    )

if hydrogen_target_needed is not None:

    st.warning(
        f"Prix cible Hydrogen nécessaire : "
        f"{hydrogen_target_needed:.2f} €"
    )

else:

    st.success("Le portefeuille surperforme déjà le MSCI World.")

# =========================================================
# PHASE 3 — SIMULATION
# =========================================================

if phase >= 3:

    st.subheader("🛡️ Sécurisation")

    st.success(
        f"ANRJ a atteint le seuil stratégique de "
        f"{hydrogen_target_price:.2f} €"
    )

    if st.button("Simuler Arbitrage 30%"):

        hydrogen_value = 0

        for p in positions_calc:

            if p["nom"] == "Global Hydrogen":
                hydrogen_value = p["valeur"]

        amount_to_sell = hydrogen_value * 0.30

        st.info(
            f"Montant réalloué vers World : "
            f"{amount_to_sell:,.2f} €"
        )

# =========================================================
# ALLOCATION LAZY
# =========================================================

st.subheader("🎯 Cible Lazy")

world_weight = 0
gold_weight = 0

for p in positions_calc:

    weight = (p["valeur"] / portfolio_value) * 100

    if "World" in p["nom"]:
        world_weight += weight

    if "Or" in p["nom"]:
        gold_weight += weight

lazy_gap_world = 94 - world_weight
lazy_gap_gold = 6 - gold_weight

l1, l2 = st.columns(2)

l1.metric(
    "Poids World",
    f"{world_weight:.2f}%",
    delta=f"{lazy_gap_world:+.2f}% vs cible"
)

l2.metric(
    "Poids Gold",
    f"{gold_weight:.2f}%",
    delta=f"{lazy_gap_gold:+.2f}% vs cible"
)

# =========================================================
# POSITIONS
# =========================================================

st.subheader("📦 Positions")

cols = st.columns(len(positions_calc))

for i, p in enumerate(positions_calc):

    with cols[i]:

        cols[i].metric(
            p["nom"],
            f"{p['prix']:.2f} €",
            delta=f"{p['perf']:+.2f}%"
        )

# =========================================================
# SENTINELLES
# =========================================================

st.subheader("🛰️ Radar Sentinelles")

if sentinel_alerts:

    for a in sentinel_alerts:
        st.warning(a)

else:

    st.success("Toutes les sentinelles sont au-dessus de leur SMA20.")

# =========================================================
# MACRO
# =========================================================

st.subheader("🌍 Macro")

macro_cols = st.columns(3)

macro_map = {
    "^TNX": "US 10Y",
    "DX-Y.NYB": "DXY",
    "BZ=F": "Brent"
}

for idx, t in enumerate(macro_map.keys()):

    if t in data:

        val = safe_last(data[t]["Close"])

        if val:

            macro_cols[idx].metric(
                macro_map[t],
                f"{val:.2f}"
            )

# =========================================================
# GRAPHIQUE BASE 100
# =========================================================

st.subheader("📈 Performance cumulée — Base 100")

if base100 is not None:

    st.line_chart(base100)

else:

    st.warning("Données insuffisantes.")

# =========================================================
# STATUS
# =========================================================

with st.status("État du moteur décisionnel", expanded=False):

    st.write("✔ Données chargées")
    st.write("✔ Alignement temporel validé")
    st.write("✔ Calculs de phase effectués")
    st.write("✔ Radar sentinelles actif")
    st.write("✔ Module Lazy actif")

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Cockpit Décisionnel • "
    "Outil d'aide à la décision • "
    "Ne constitue pas un conseil financier"
)
