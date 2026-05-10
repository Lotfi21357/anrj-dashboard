import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(
    page_title="ANRJ Décisionnel",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.stApp {max-width: 100%;}
.big-verdict {font-size:2rem!important;font-weight:bold;text-align:center;padding:0.8rem;border-radius:1rem;margin:1rem 0;}
.question-box {background-color:#e9ecef;padding:0.5rem 1rem;border-radius:0.5rem;margin:0.3rem 0;font-size:0.9rem;}
.green {color:#28a745;}
.red {color:#dc3545;}
</style>
""", unsafe_allow_html=True)

st.title("⚡ Dashboard Décisionnel ANRJ")
st.caption("Contrôle quotidien 2 min · Données en temps réel")

@st.cache_data(ttl=600, show_spinner=False)
def load_data():
    tickers = {
        "ANRJ": "ANRJ.PA",
        "Bloom Energy": "BE",
        "MSCI World": "EUNL.DE",
        "US10Y": "^TNX",
        "Brent": "BZ=F"
    }
    today = datetime.now()
    start_hist = today - timedelta(days=365)
    data = {}
    try:
        anrj = yf.download(tickers["ANRJ"], start=start_hist, progress=False)
        be = yf.download(tickers["Bloom Energy"], start=start_hist, progress=False)
        world = yf.download(tickers["MSCI World"], start=start_hist, progress=False)
        tnx = yf.download(tickers["US10Y"], start=start_hist, progress=False)
        brent = yf.download(tickers["Brent"], start=start_hist, progress=False)

        def get_last_close(df):
            if df is None or df.empty:
                return None
            return float(df["Close"].iloc[-1])

        def get_prev_close(df):
            if df is None or df.empty:
                return None
            if len(df) < 2:
                return get_last_close(df)
            return float(df["Close"].iloc[-2])

        anrj_last = get_last_close(anrj)
        anrj_prev = get_prev_close(anrj)
        be_last = get_last_close(be)
        be_prev = get_prev_close(be)
        world_last = get_last_close(world)
        world_prev = get_prev_close(world)

        if tnx.empty or brent.empty:
            return None
        tnx_last = float(tnx["Close"].iloc[-1]) / 10
        brent_last = get_last_close(brent)
        brent_prev = get_prev_close(brent)

        if any(v is None for v in [anrj_last, be_last, world_last, tnx_last, brent_last]):
            return None

        data["ANRJ"] = {"close": anrj_last, "prev_close": anrj_prev, "history": anrj}
        data["BE"] = {"close": be_last, "prev_close": be_prev, "history": be}
        data["World"] = {"close": world_last, "prev_close": world_prev, "history": world}
        data["US10Y"] = {"value": tnx_last}
        data["Brent"] = {"close": brent_last, "prev_close": brent_prev}
        return data
    except Exception as e:
        st.error(f"Erreur : {e}")
        return None

data = load_data()
if data is None:
    st.stop()

def compute_sma(series, window):
    return series.rolling(window=window).mean()

anrj_hist = data["ANRJ"]["history"]
anrj_hist["SMA50"] = compute_sma(anrj_hist["Close"], 50)
anrj_hist["SMA200"] = compute_sma(anrj_hist["Close"], 200)
current_sma50 = float(anrj_hist["SMA50"].iloc[-1])
current_sma200 = float(anrj_hist["SMA200"].iloc[-1])
anrj_close = data["ANRJ"]["close"]

be_hist = data["BE"]["history"]
be_hist["SMA50"] = compute_sma(be_hist["Close"], 50)
be_sma50 = float(be_hist["SMA50"].iloc[-1])
be_close = data["BE"]["close"]

def get_4w_returns(hist):
    if len(hist) >= 21:
        return (float(hist["Close"].iloc[-1]) / float(hist["Close"].iloc[-21]) - 1)
    return None

anrj_4w = get_4w_returns(anrj_hist)
world_hist = data["World"]["history"]
world_4w = get_4w_returns(world_hist)

def last_n_days_under_sma(hist, n_days=5):
    if len(hist) < n_days or "SMA50" not in hist.columns:
        return False
    last_days = hist.iloc[-n_days:]
    if last_days["SMA50"].isna().any():
        return False
    return all(last_days["Close"] < last_days["SMA50"])

under_sma50_5d = last_n_days_under_sma(anrj_hist)

be_high_52w = float(be_hist["High"].rolling(window=252).max().iloc[-2]) if len(be_hist) >= 252 else float(be_hist["High"].max())
be_new_high = be_close > be_high_52w

anrj_delta = anrj_close - data["ANRJ"]["prev_close"]
anrj_delta_pct = (anrj_delta / data["ANRJ"]["prev_close"]) * 100
be_delta = be_close - data["BE"]["prev_close"]
be_delta_pct = (be_delta / data["BE"]["prev_close"]) * 100
brent_close = data["Brent"]["close"]
brent_prev = data["Brent"]["prev_close"]
brent_delta = brent_close - brent_prev
us10y = data["US10Y"]["value"]

questions = [
    {
        "q": f"1. ANRJ au-dessus de SMA200 ({current_sma200:.2f}€) ?",
        "condition": anrj_close > current_sma200,
        "true_emoji": "✅", "false_emoji": "⚠️",
        "true_text": "Zone sûre", "false_text": "Vigilance"
    },
    {
        "q": f"2. ANRJ au-dessus de SMA50 ({current_sma50:.2f}€) ?",
        "condition": anrj_close > current_sma50,
        "true_emoji": "✅", "false_emoji": "🚨",
        "true_text": "Tendance intacte", "false_text": "Signal de réduction"
    },
    {
        "q": "3. Bloom Energy stable ou en hausse ?",
        "condition": be_close >= data["BE"]["prev_close"],
        "true_emoji": "✅", "false_emoji": "⚠️",
        "true_text": "Moteur actif", "false_text": "Surveiller fondamentaux"
    },
    {
        "q": "4. US 10Y sous 4,60% ?",
        "condition": us10y < 4.60,
        "true_emoji": "✅", "false_emoji": "🚨",
        "true_text": "Taux acceptables", "false_text": "Mode défensif"
    },
    {
        "q": "5. World ne surperforme pas depuis > 4 semaines ?",
        "condition": anrj_4w is not None and world_4w is not None and anrj_4w >= world_4w,
        "true_emoji": "✅", "false_emoji": "⚠️",
        "true_text": "Leadership intact", "false_text": "Réévaluer la position"
    }
]

score = sum(1 for q in questions if q["condition"])
if score == 5:
    verdict_phrase = "🟢 MAINTIEN TOTAL"
    verdict_color = "#d4edda"
elif score >= 3:
    verdict_phrase = "🟡 SURVEILLANCE"
    verdict_color = "#fff3cd"
else:
    verdict_phrase = "🔴 ALERTE – Conditions dégradées"
    verdict_color = "#f8d7da"

def determine_action():
    if anrj_close < 706:
        return "🚨 STOP-LOSS 50% : Arbitrer 50% vers MSCI World immédiatement."
    be_peak = float(be_hist["High"].rolling(window=252).max().iloc[-2]) if len(be_hist) >= 252 else float(be_hist["High"].max())
    bloom_drop = (be_close / be_peak - 1) if be_peak > 0 else 0
    conditions_crise = [
        be_close < be_peak * 0.75,
        us10y > 5.00,
        brent_close < 80,
        bloom_drop < -0.25,
        anrj_close < current_sma200
    ]
    if all(conditions_crise):
        return "🔴 PROTOCOLE CRISE TOTALE : Réduire Hydrogen à 10% max. Arbitrage massif vers World."
    if under_sma50_5d:
        return "🔻 RÉDUCTION 25% : Arbitrer 25% Hydrogen → MSCI World."
    if us10y > 4.60 and be_delta_pct < -2:
        return "🛡️ MODE DÉFENSIF : Réduire 15%, stopper renforcement."
    if anrj_close > 812:
        return "💰 TAKE-PROFIT 30% : Arbitrer 30% Hydrogen → World."
    if anrj_4w is not None and world_4w is not None and world_4w > anrj_4w and anrj_close < current_sma50:
        return "📉 RÉDUCTION PROGRESSIVE : Réduire 15% → World. Réévaluer dans 2 sem."
    if brent_close > 105 and be_delta_pct > 2:
        return "🟢 MAINTIEN OFFENSIF : Conditions idéales."
    if 752 <= anrj_close <= 758:
        return "⚠️ VIGILANCE RENFORCÉE : Stopper renforcement."
    if anrj_close > current_sma50 and anrj_4w is not None and world_4w is not None and anrj_4w >= world_4w:
        return "✅ MAINTIEN : Tendance intacte."
    if be_new_high:
        return "🌟 CONSERVER : Bloom au plus haut, attendre 812€."
    return "ℹ️ SURVEILLANCE : Aucun signal fort."

action_reco = determine_action()

st.markdown(f"""
<div class="big-verdict" style="background-color:{verdict_color};">
{verdict_phrase}
</div>
""", unsafe_allow_html=True)

st.subheader("🚦 Action recommandée")
st.success(action_reco)

st.subheader("📊 Indicateurs clés")
col1, col2 = st.columns(2)
with col1:
    st.metric("ANRJ", f"{anrj_close:.2f}€", delta=f"{anrj_delta:+.2f}€ ({anrj_delta_pct:+.1f}%)")
    st.metric("Bloom Energy", f"{be_close:.2f}$", delta=f"{be_delta:+.2f}$ ({be_delta_pct:+.1f}%)")
with col2:
    st.metric("SMA50 ANRJ", f"{current_sma50:.2f}€")
    st.metric("SMA200 ANRJ", f"{current_sma200:.2f}€")

col3, col4 = st.columns(2)
with col3:
    st.metric("Brent", f"{brent_close:.2f}$", delta=f"{brent_delta:+.2f}$")
with col4:
    st.metric("US 10Y", f"{us10y:.2f}%")

st.subheader("❓ Contrôle quotidien")
for q in questions:
    emoji = q["true_emoji"] if q["condition"] else q["false_emoji"]
    text = q["true_text"] if q["condition"] else q["false_text"]
    st.markdown(f"""
    <div class="question-box">
    {emoji} <strong>{q['q']}</strong><br>
    <span class="{'green' if q['condition'] else 'red'}">{text}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.caption(f"Score du jour : {score}/5 · Données en temps réel")
st.caption("Document strictement personnel · Ne constitue pas un conseil en investissement")
