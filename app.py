import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="Core & Satellite Décisionnel", page_icon="🛰️", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp {max-width: 100%; padding: 0.5rem;}
.big-verdict {font-size:1.8rem!important;font-weight:bold;text-align:center;padding:0.8rem;border-radius:1rem;margin:1rem 0;color:white;}
.metric-box {background:#f8f9fa;padding:0.5rem;border-radius:0.5rem;margin:0.2rem;}
</style>
""", unsafe_allow_html=True)

# ---------- DONNÉES PORTEFEUILLE ----------
CAPITAL_INITIAL = 13796.71
DATE_DEBUT = datetime(2025, 9, 17)
POSITIONS = {
    "MSCI World AV":  {"ticker": "MWRD.L",  "parts": 36.33, "prm": 145.09},
    "MSCI World PEA": {"ticker": "DCAM.PA", "parts": 481,   "prm": 5.261},
    "Global Hydrogen": {"ticker": "ANRJ.PA", "parts": 4.77, "prm": 706.06},
    "EM Asia":         {"ticker": "AASI.PA", "parts": 40.83, "prm": 52.48},
    "Or Physique":     {"ticker": "CGLD.PA", "parts": 4.59, "prm": 163.39},
}
BENCHMARK_TICKER = "CW8.PA"
EXTRA_TICKERS = ["^TNX", "DX-Y.NYB", "BZ=F", "BE", "NVDA", "^SOX"]

# ---------- FONCTIONS ROBUSTES ----------
def to_float(val):
    if val is None: return None
    if isinstance(val, (int, float, np.floating, np.integer)): return float(val)
    if isinstance(val, pd.Series): return float(val.iloc[0]) if not val.empty else None
    if isinstance(val, np.ndarray): return float(val.flat[0]) if val.size > 0 else None
    try: return float(val)
    except: return None

def safe_last(series):
    if series is None: return None
    if isinstance(series, pd.DataFrame): series = series.squeeze()
    if isinstance(series, pd.Series): return to_float(series.iloc[-1]) if not series.empty else None
    if isinstance(series, np.ndarray): return to_float(series.flat[-1]) if series.size > 0 else None
    return to_float(series)

def safe_prev(series):
    if series is None: return None
    if isinstance(series, pd.DataFrame): series = series.squeeze()
    if isinstance(series, pd.Series): return to_float(series.iloc[-2]) if len(series) > 1 else safe_last(series)
    return None

@st.cache_data(ttl=600, show_spinner=False)
def load_all_data():
    portfolio_tickers = [v["ticker"] for v in POSITIONS.values()]
    all_tickers = list(set(portfolio_tickers + [BENCHMARK_TICKER] + EXTRA_TICKERS))
    start = datetime.now() - timedelta(days=400)
    data = {}

    # Tenter un téléchargement groupé
    try:
        df = yf.download(all_tickers, start=start, progress=False, group_by='ticker')
    except Exception:
        df = pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        for t in all_tickers:
            if t in df.columns.levels[0]:
                tmp = df[t].copy()
                if not tmp.empty:
                    data[t] = tmp
    elif not df.empty:
        # Un seul ticker téléchargé
        if len(all_tickers) == 1:
            t = all_tickers[0]
            data[t] = df
        else:
            # Échec probable -> on passe en individuel
            pass

    # Pour les tickers manquants, essayer individuellement
    for t in all_tickers:
        if t not in data or data[t].empty:
            try:
                single = yf.download(t, start=start, progress=False)
                if not single.empty:
                    data[t] = single
            except Exception:
                pass

    return data

def compute_sma(series, window):
    if series is None or len(series) < window: return None
    return series.rolling(window=window).mean()

def compute_rsi(series, period=14):
    if series is None or len(series) < period+1: return None
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    avg_loss.replace(0, np.nan, inplace=True)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ---------- CHARGEMENT ----------
data = load_all_data()
if data is None or all(df.empty for df in data.values()):
    st.error("Impossible de récupérer les données. Vérifiez votre connexion internet.")
    st.stop()

# Extraire prix de clôture
latest_prices = {}
for t, df in data.items():
    if not df.empty and "Close" in df.columns:
        latest_prices[t] = safe_last(df["Close"])
    else:
        latest_prices[t] = None

# Vérifier les tickers essentiels
essential = [v["ticker"] for v in POSITIONS.values()]
missing = [t for t in essential if latest_prices.get(t) is None]
if missing:
    st.error(f"Données manquantes pour : {missing}. Vérifiez les tickers ou l'état du marché.")
    st.stop()

# ---------- VALEUR DU PORTEFEUILLE ----------
valeur_totale = 0.0
perf_par_ligne = {}
for nom, pos in POSITIONS.items():
    prix = latest_prices[pos["ticker"]]
    valeur = pos["parts"] * prix
    valeur_totale += valeur
    perf_ligne = (prix - pos["prm"]) / pos["prm"] * 100
    perf_par_ligne[nom] = {"valeur": valeur, "prix": prix, "perf": perf_ligne}

gain_net = valeur_totale - CAPITAL_INITIAL
perf_totale = (gain_net / CAPITAL_INITIAL) * 100

# ---------- BENCHMARK CW8 ----------
perf_world = gain = None
bench_price = latest_prices.get(BENCHMARK_TICKER)
if bench_price and BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty:
    cw8_series = data[BENCHMARK_TICKER]["Close"].squeeze()
    try:
        start_val = cw8_series.loc[DATE_DEBUT.strftime("%Y-%m-%d")]
        start_val = to_float(start_val.iloc[0]) if isinstance(start_val, pd.Series) else to_float(start_val)
    except KeyError:
        start_val = to_float(cw8_series.iloc[0])
    if start_val and start_val > 0:
        perf_world = (bench_price / start_val - 1) * 100
        gain = perf_totale - perf_world

# ---------- INDICATEURS HYDROGÈNE ----------
anrj_series = None
if "ANRJ.PA" in data and not data["ANRJ.PA"].empty:
    anrj_series = data["ANRJ.PA"]["Close"].squeeze()
anrj_current = safe_last(anrj_series)
anrj_sma50_now = anrj_sma200_now = anrj_rsi_now = None
if anrj_series is not None and len(anrj_series) > 50:
    anrj_sma50 = compute_sma(anrj_series, 50)
    anrj_sma200 = compute_sma(anrj_series, 200)
    anrj_rsi = compute_rsi(anrj_series, 14)
    anrj_sma50_now = safe_last(anrj_sma50)
    anrj_sma200_now = safe_last(anrj_sma200)
    anrj_rsi_now = safe_last(anrj_rsi)

# ---------- INDICATEURS EM ASIA ----------
aasi_series = None
if "AASI.PA" in data and not data["AASI.PA"].empty:
    aasi_series = data["AASI.PA"]["Close"].squeeze()
aasi_current = safe_last(aasi_series)
aasi_sma50_now = None
ratio_current = ratio_avg20_now = None
if aasi_series is not None and len(aasi_series) > 50:
    aasi_sma50 = compute_sma(aasi_series, 50)
    aasi_sma50_now = safe_last(aasi_sma50)
    if BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty:
        cw8_series = data[BENCHMARK_TICKER]["Close"].squeeze()
        if cw8_series is not None and len(cw8_series) > 20:
            ratio = aasi_series / cw8_series
            ratio_avg20 = ratio.rolling(20).mean()
            ratio_current = safe_last(ratio)
            ratio_avg20_now = safe_last(ratio_avg20)

# ---------- MACRO ----------
us10y = dxy = brent = None
if "^TNX" in data: 
    tmp = safe_last(data["^TNX"]["Close"].squeeze())
    if tmp: us10y = tmp / 10
if "DX-Y.NYB" in data: dxy = safe_last(data["DX-Y.NYB"]["Close"].squeeze())
if "BZ=F" in data: brent = safe_last(data["BZ=F"]["Close"].squeeze())

bloom_close = bloom_prev = nvidia_close = sox_close = None
if "BE" in data and not data["BE"].empty:
    be_s = data["BE"]["Close"].squeeze()
    bloom_close = safe_last(be_s)
    bloom_prev = safe_prev(be_s)
if "NVDA" in data and not data["NVDA"].empty:
    nvidia_close = safe_last(data["NVDA"]["Close"].squeeze())
if "^SOX" in data and not data["^SOX"].empty:
    sox_close = safe_last(data["^SOX"]["Close"].squeeze())

# ---------- RÈGLES ----------
def evaluate_hydrogen():
    if anrj_current is None: return "⚠️ Données ANRJ manquantes", "gray"
    if anrj_current < 706.06: return "🚨 STOP-LOSS 50% : COUPURE 50% VERS WORLD", "red"
    if anrj_current > 812 and anrj_rsi_now and anrj_rsi_now > 68: return "💰 TAKE PROFIT : ARBITRAGE 30% VERS WORLD", "green"
    if anrj_sma50_now and anrj_current < anrj_sma50_now:
        if anrj_series is not None and len(anrj_series) >= 5 and anrj_sma50 is not None:
            last5 = anrj_series[-5:]
            last5_sma = anrj_sma50[-5:]
            if len(last5_sma)==5 and all(v < s for v,s in zip(last5,last5_sma) if pd.notna(s)):
                return "🔻 RÉDUCTION 25% : PASSÉ SOUS SMA50 (5j)", "red"
    conditions_def = (us10y and us10y > 4.60) or (brent and brent < 90) or (bloom_close and bloom_prev and bloom_prev!=0 and (bloom_close/bloom_prev-1) < -0.15)
    if conditions_def: return "🛡️ MODE DÉFENSIF - RÉDUCTION 15%", "orange"
    if anrj_sma50_now and anrj_current > anrj_sma50_now: return "✅ MAINTIEN HYDROGÈNE - Tendance intacte", "green"
    return "ℹ️ SURVEILLANCE HYDROGÈNE", "orange"

def evaluate_em_asia():
    if aasi_current is None: return "⚠️ Données AASI manquantes", "gray"
    if aasi_current > 60.35:
        if aasi_series is not None:
            highest = aasi_series.rolling(50, min_periods=1).max()
            highest_val = safe_last(highest)
            if highest_val and aasi_current < highest_val * 0.92: return "🎯 TRAILING STOP DÉCLENCHÉ : -8% depuis +haut, ARBITRAGE 50%", "red"
            else: return "📈 TRAILING STOP ACTIF (seuil à -8% du +haut)", "green"
    if ratio_avg20_now and ratio_current and ratio_current < ratio_avg20_now: return "📉 MOMENTUM CASSÉ : ARBITRAGE 50% VERS WORLD", "red"
    if nvidia_close and "NVDA" in data and not data["NVDA"].empty:
        nvda_s = data["NVDA"]["Close"].squeeze()
        if len(nvda_s) >= 50:
            nvda_sma50 = compute_sma(nvda_s, 50)
            nvda_sma50_now = safe_last(nvda_sma50)
            if nvda_sma50_now and nvidia_close < nvda_sma50_now: return "📉 NVIDIA SOUS SMA50 → ARBITRAGE 50% EM ASIA", "red"
    if us10y and us10y > 4.60 and dxy and dxy > 102: return "🌍 ALERTE MACRO - COUPURE EM ASIA", "red"
    if aasi_sma50_now and aasi_current > aasi_sma50_now: return "✅ MAINTIEN EM ASIA - Tendance intacte", "green"
    return "ℹ️ SURVEILLANCE EM ASIA", "orange"

def global_decision():
    h_msg, h_col = evaluate_hydrogen()
    a_msg, a_col = evaluate_em_asia()
    if "red" in [h_col, a_col]:
        msg = h_msg if h_col=="red" else a_msg
        return f"🔴 ACTION REQUISE : {msg}", "red"
    if "orange" in [h_col, a_col]:
        msg = h_msg if h_col=="orange" else a_msg
        return f"🟡 VIGILANCE : {msg}", "orange"
    return "🟢 MAINTIEN GLOBAL - Aucune action immédiate", "green"

decision_globale, decision_color = global_decision()

# ---------- INTERFACE ----------
st.title("🛰️ Core & Satellite Décisionnel")
st.caption(f"Données au {datetime.now().strftime('%d/%m/%Y %H:%M')} · Mobile")

st.markdown("### 📈 Performance Globale")
c1,c2,c3=st.columns(3)
c1.metric("Valeur totale",f"{valeur_totale:,.2f}€")
c2.metric("Gain net",f"{gain_net:+,.2f}€")
c3.metric("Performance",f"{perf_totale:+.2f}%")
if perf_world is not None:
    c4,c5=st.columns(2)
    c4.metric("Perf. World (CW8)",f"{perf_world:+.2f}%")
    c5.metric("GAP vs World",f"{gap:+.2f}%",delta=f"{gap:+.2f}%")

st.markdown("#### Détail des positions")
cols = st.columns(len(perf_par_ligne))
for i,(nom,infos) in enumerate(perf_par_ligne.items()):
    with cols[i]:
        st.metric(label=nom,value=f"{infos['prix']:.2f}€",delta=f"{infos['perf']:+.2f}%")

bg={"red":"#dc3545","orange":"#fd7e14","green":"#28a745"}.get(decision_color,"#6c757d")
st.markdown(f"<div class='big-verdict' style='background-color:{bg};'>{decision_globale}</div>",unsafe_allow_html=True)

st.subheader("🔎 Détails Hydrogène (ANRJ)")
if anrj_current:
    d1,d2,d3=st.columns(3)
    d1.metric("ANRJ",f"{anrj_current:.2f}€")
    d2.metric("SMA50",f"{anrj_sma50_now:.2f}€" if anrj_sma50_now else "N/A")
    d3.metric("RSI",f"{anrj_rsi_now:.1f}" if anrj_rsi_now else "N/A")
    st.caption(evaluate_hydrogen()[0])
else: st.warning("ANRJ indisponible")

st.subheader("🌏 Détails EM Asia (AASI)")
if aasi_current:
    e1,e2=st.columns(2)
    e1.metric("AASI",f"{aasi_current:.2f}€")
    e2.metric("SMA50",f"{aasi_sma50_now:.2f}€" if aasi_sma50_now else "N/A")
    if ratio_current:
        e3,e4=st.columns(2)
        e3.metric("Ratio AASI/CW8",f"{ratio_current:.4f}")
        e4.metric("Ratio moy. 20j",f"{ratio_avg20_now:.4f}" if ratio_avg20_now else "N/A")
    st.caption(evaluate_em_asia()[0])
else: st.warning("AASI indisponible")

st.subheader("🧭 Indicateurs Macro")
m1,m2,m3,m4=st.columns(4)
m1.metric("US 10Y",f"{us10y:.2f}%" if us10y else "N/A")
m2.metric("DXY",f"{dxy:.2f}" if dxy else "N/A")
m3.metric("Brent",f"{brent:.2f}$" if brent else "N/A")
m4.metric("Bloom Energy",f"{bloom_close:.2f}$" if bloom_close else "N/A")

st.markdown("---")
st.caption("Système décisionnel Core & Satellite · Ne constitue pas un conseil en investissement")
