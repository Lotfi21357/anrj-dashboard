import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ---------- CONFIGURATION ----------
st.set_page_config(
    page_title="Core & Satellite Décisionnel",
    page_icon="🛰️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Style mobile-friendly
st.markdown("""
<style>
.stApp {max-width: 100%; padding: 0.5rem;}
.big-number {font-size: 2.5rem; font-weight: bold; text-align: center;}
.big-verdict {font-size: 1.8rem !important; font-weight: bold; text-align: center;
    padding: 0.8rem; border-radius: 1rem; margin: 1rem 0; color: white;}
.metric-box {background: #f8f9fa; padding: 0.5rem; border-radius: 0.5rem; margin: 0.2rem;}
.orange {color: #fd7e14;}
.green {color: #28a745;}
.red {color: #dc3545;}
</style>
""", unsafe_allow_html=True)

# ---------- DONNÉES DU PORTEFEUILLE (fixes) ----------
CAPITAL_INITIAL = 13796.71   # €  (somme des PRM poche)
DATE_DEBUT = datetime(2025, 9, 17)
POSITIONS = {
    "MSCI World AV":  {"ticker": "MWRD.L",  "parts": 36.33, "prm": 145.09},
    "MSCI World PEA": {"ticker": "DCAM.PA", "parts": 481,   "prm": 5.261},
    "Global Hydrogen": {"ticker": "ANRJ.PA", "parts": 4.77, "prm": 706.06},
    "EM Asia":         {"ticker": "AASI.PA", "parts": 40.83, "prm": 52.48},
    "Or Physique":     {"ticker": "CGLD.PA", "parts": 4.59, "prm": 163.39},
}
BENCHMARK_TICKER = "CW8.PA"

# ---------- FONCTIONS DE CONVERSION ROBUSTES ----------
def to_float(val):
    """Convertit n'importe quelle valeur en float scalaire."""
    if val is None:
        return None
    if isinstance(val, (int, float, np.floating, np.integer)):
        return float(val)
    if isinstance(val, pd.Series):
        if val.empty:
            return None
        return float(val.iloc[0])
    if isinstance(val, np.ndarray):
        if val.size == 0:
            return None
        return float(val.flat[0])
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_last(series):
    """Dernière valeur d'une série ou d'un array, convertie en float."""
    if series is None:
        return None
    if isinstance(series, pd.DataFrame):
        if series.empty:
            return None
        series = series.squeeze()
    if isinstance(series, pd.Series):
        if series.empty:
            return None
        return to_float(series.iloc[-1])
    if isinstance(series, np.ndarray):
        if series.size == 0:
            return None
        return to_float(series.flat[-1])
    return to_float(series)

def safe_prev(series):
    """Avant-dernière valeur d'une série."""
    if series is None:
        return None
    if isinstance(series, pd.DataFrame):
        if series.empty or len(series) < 2:
            return None
        series = series.squeeze()
    if isinstance(series, pd.Series):
        if len(series) < 2:
            return safe_last(series)
        return to_float(series.iloc[-2])
    return None

# ---------- CHARGEMENT DES DONNÉES ----------
@st.cache_data(ttl=600, show_spinner=False)
def load_all_data():
    tickers_portfolio = [v["ticker"] for v in POSITIONS.values()]
    tickers_extra = [BENCHMARK_TICKER, "^TNX", "DX-Y.NYB", "BZ=F", "BE", "NVDA", "^SOX"]
    all_tickers = list(set(tickers_portfolio + tickers_extra))
    
    today = datetime.now()
    start = today - timedelta(days=400)
    
    try:
        # Téléchargement groupé
        df = yf.download(all_tickers, start=start, progress=False)
        
        data = {}
        # Si un seul ticker, df n'a pas de MultiIndex
        if len(all_tickers) == 1:
            ticker = all_tickers[0]
            data[ticker] = df.copy()
        else:
            # MultiIndex : niveau 0 = ticker, niveau 1 = champ
            for t in all_tickers:
                if t in df.columns.levels[0]:
                    tmp = df[t].copy()
                    # Remplir les éventuels NaN avec forward fill
                    tmp.ffill(inplace=True)
                    data[t] = tmp
                else:
                    # ticker non trouvé
                    data[t] = pd.DataFrame()
        return data
    except Exception as e:
        st.error(f"Erreur chargement données : {e}")
        return None

def compute_sma(series, window):
    if series is None or len(series) < window:
        return None
    return series.rolling(window=window).mean()

def compute_rsi(series, period=14):
    if series is None or len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    # Éviter division par zéro
    avg_loss.replace(0, np.nan, inplace=True)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ---------- EXÉCUTION ----------
data = load_all_data()
if data is None:
    st.stop()

# Extraire les dernières valeurs
latest_prices = {}
for t, df in data.items():
    if df.empty or "Close" not in df.columns:
        latest_prices[t] = None
    else:
        latest_prices[t] = safe_last(df["Close"])

# Vérification des tickers essentiels
essential = [v["ticker"] for v in POSITIONS.values()]
missing = [t for t in essential if latest_prices.get(t) is None]
if missing:
    st.error(f"Données manquantes pour : {missing}. Vérifiez les tickers.")
    st.stop()

# ---------- CALCUL VALEUR DU PORTEFEUILLE ----------
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
benchmark_price = latest_prices.get(BENCHMARK_TICKER)
if benchmark_price is not None and BENCHMARK_TICKER in data:
    cw8_df = data[BENCHMARK_TICKER]
    if not cw8_df.empty and "Close" in cw8_df.columns:
        cw8_series = cw8_df["Close"].squeeze()
        # Chercher le prix le plus proche du 17/09/2025
        try:
            cw8_start_val = cw8_series.loc[DATE_DEBUT.strftime("%Y-%m-%d")]
            if isinstance(cw8_start_val, pd.Series):
                cw8_start_val = to_float(cw8_start_val.iloc[0])
            else:
                cw8_start_val = to_float(cw8_start_val)
        except KeyError:
            # Utiliser la première valeur disponible
            cw8_start_val = to_float(cw8_series.iloc[0])
        if cw8_start_val is not None and cw8_start_val > 0:
            perf_world = (benchmark_price / cw8_start_val - 1) * 100
            gap = perf_totale - perf_world
        else:
            perf_world = None
            gap = None
    else:
        perf_world = None
        gap = None
else:
    perf_world = None
    gap = None

# ---------- INDICATEURS HYDROGEN (ANRJ) ----------
anrj_series = None
anrj_current = None
if "ANRJ.PA" in data and not data["ANRJ.PA"].empty:
    anrj_series = data["ANRJ.PA"]["Close"].squeeze()
    anrj_current = safe_last(anrj_series)

if anrj_series is not None and len(anrj_series) > 50:
    anrj_sma20 = compute_sma(anrj_series, 20)
    anrj_sma50 = compute_sma(anrj_series, 50)
    anrj_sma200 = compute_sma(anrj_series, 200)
    anrj_rsi = compute_rsi(anrj_series, 14)
    anrj_sma50_now = safe_last(anrj_sma50) if anrj_sma50 is not None else None
    anrj_sma200_now = safe_last(anrj_sma200) if anrj_sma200 is not None else None
    anrj_rsi_now = safe_last(anrj_rsi) if anrj_rsi is not None else None
else:
    anrj_sma50_now = None
    anrj_sma200_now = None
    anrj_rsi_now = None

# ---------- INDICATEURS EM Asia (AASI) ----------
aasi_series = None
aasi_current = None
if "AASI.PA" in data and not data["AASI.PA"].empty:
    aasi_series = data["AASI.PA"]["Close"].squeeze()
    aasi_current = safe_last(aasi_series)

if aasi_series is not None and len(aasi_series) > 50:
    aasi_sma50 = compute_sma(aasi_series, 50)
    aasi_sma100 = compute_sma(aasi_series, 100)
    aasi_sma50_now = safe_last(aasi_sma50) if aasi_sma50 is not None else None
else:
    aasi_sma50_now = None

# Ratio Force Relative AASI / CW8
ratio_current = None
ratio_avg20_now = None
if aasi_series is not None and BENCHMARK_TICKER in data:
    cw8_series = data[BENCHMARK_TICKER]["Close"].squeeze() if not data[BENCHMARK_TICKER].empty else None
    if cw8_series is not None and len(cw8_series) > 20:
        ratio = aasi_series / cw8_series
        ratio_avg20 = ratio.rolling(20).mean()
        ratio_current = safe_last(ratio)
        ratio_avg20_now = safe_last(ratio_avg20)

# ---------- MACRO ----------
us10y = None
if "^TNX" in data and not data["^TNX"].empty:
    tnx_close = data["^TNX"]["Close"].squeeze()
    tnx_val = safe_last(tnx_close)
    if tnx_val is not None:
        us10y = tnx_val / 10  # ^TNX est *10

dxy = None
if "DX-Y.NYB" in data and not data["DX-Y.NYB"].empty:
    dxy = safe_last(data["DX-Y.NYB"]["Close"].squeeze())

brent = None
if "BZ=F" in data and not data["BZ=F"].empty:
    brent = safe_last(data["BZ=F"]["Close"].squeeze())

# Proxys
bloom_close = None
bloom_prev = None
if "BE" in data and not data["BE"].empty:
    be_series = data["BE"]["Close"].squeeze()
    bloom_close = safe_last(be_series)
    bloom_prev = safe_prev(be_series)

nvidia_close = None
if "NVDA" in data and not data["NVDA"].empty:
    nvidia_close = safe_last(data["NVDA"]["Close"].squeeze())

sox_close = None
if "^SOX" in data and not data["^SOX"].empty:
    sox_close = safe_last(data["^SOX"]["Close"].squeeze())

# ---------- MOTEUR DE RÈGLES ----------
def evaluate_hydrogen():
    if anrj_current is None:
        return "⚠️ Données ANRJ manquantes", "gray"
    # Stop-loss
    if anrj_current < 706.06:
        return "🚨 STOP-LOSS 50% : COUPURE 50% VERS WORLD", "red"
    # Take profit
    if anrj_current > 812 and anrj_rsi_now is not None and anrj_rsi_now > 68:
        return "💰 TAKE PROFIT : ARBITRAGE 30% VERS WORLD", "green"
    # Tendance cassée (5 jours sous SMA50)
    if anrj_sma50_now is not None and anrj_current < anrj_sma50_now:
        if anrj_series is not None and len(anrj_series) >= 5 and anrj_sma50 is not None:
            last5 = anrj_series[-5:]
            last5_sma = anrj_sma50[-5:]
            if len(last5_sma) == 5 and all(v < s for v, s in zip(last5, last5_sma) if pd.notna(s)):
                return "🔻 RÉDUCTION 25% : PASSÉ SOUS SMA50 (5j)", "red"
    # Macro défensif
    conditions_defensif = False
    if us10y is not None and us10y > 4.60:
        conditions_defensif = True
    if brent is not None and brent < 90:
        conditions_defensif = True
    if bloom_close is not None and bloom_prev is not None and bloom_prev != 0:
        if (bloom_close / bloom_prev - 1) < -0.15:
            conditions_defensif = True
    if conditions_defensif:
        return "🛡️ MODE DÉFENSIF - RÉDUCTION 15%", "orange"
    # Maintien
    if anrj_sma50_now is not None and anrj_current > anrj_sma50_now:
        return "✅ MAINTIEN HYDROGÈNE - Tendance intacte", "green"
    return "ℹ️ SURVEILLANCE HYDROGÈNE", "orange"

def evaluate_em_asia():
    if aasi_current is None:
        return "⚠️ Données AASI manquantes", "gray"
    # Take profit / trailing stop
    if aasi_current > 60.35:
        if aasi_series is not None:
            highest = aasi_series.rolling(50, min_periods=1).max()
            highest_val = safe_last(highest)
            if highest_val is not None and aasi_current < highest_val * 0.92:
                return "🎯 TRAILING STOP DÉCLENCHÉ : -8% depuis +haut, ARBITRAGE 50%", "red"
            else:
                return "📈 TRAILING STOP ACTIF (seuil à -8% du +haut)", "green"
    # Momentum cassé
    if ratio_avg20_now is not None and ratio_current is not None and ratio_current < ratio_avg20_now:
        return "📉 MOMENTUM CASSÉ : ARBITRAGE 50% VERS WORLD", "red"
    # Nvidia sous SMA50
    if nvidia_close is not None and "NVDA" in data and not data["NVDA"].empty:
        nvda_series = data["NVDA"]["Close"].squeeze()
        if len(nvda_series) >= 50:
            nvda_sma50 = compute_sma(nvda_series, 50)
            nvda_sma50_now = safe_last(nvda_sma50)
            if nvda_sma50_now is not None and nvidia_close < nvda_sma50_now:
                return "📉 NVIDIA SOUS SMA50 → ARBITRAGE 50% EM ASIA", "red"
    # Macro EM Asia
    if us10y is not None and us10y > 4.60 and dxy is not None and dxy > 102:
        return "🌍 ALERTE MACRO - COUPURE EM ASIA", "red"
    # Maintien
    if aasi_sma50_now is not None and aasi_current > aasi_sma50_now:
        return "✅ MAINTIEN EM ASIA - Tendance intacte", "green"
    return "ℹ️ SURVEILLANCE EM ASIA", "orange"

def global_decision():
    hydro_msg, hydro_color = evaluate_hydrogen()
    asia_msg, asia_color = evaluate_em_asia()
    if "red" in [hydro_color, asia_color]:
        msg = hydro_msg if hydro_color == "red" else asia_msg
        return f"🔴 ACTION REQUISE : {msg}", "red"
    if "orange" in [hydro_color, asia_color]:
        msg = hydro_msg if hydro_color == "orange" else asia_msg
        return f"🟡 VIGILANCE : {msg}", "orange"
    return "🟢 MAINTIEN GLOBAL - Aucune action immédiate", "green"

decision_globale, decision_color = global_decision()

# ---------- INTERFACE ----------
st.title("🛰️ Core & Satellite Décisionnel")
st.caption(f"Données au {datetime.now().strftime('%d/%m/%Y %H:%M')} · Mobile-friendly")

# Section Executive
st.markdown("### 📈 Performance Globale")
col1, col2, col3 = st.columns(3)
col1.metric("Valeur totale", f"{valeur_totale:,.2f} €")
col2.metric("Gain net", f"{gain_net:+,.2f} €")
col3.metric("Performance", f"{perf_totale:+.2f} %")

if perf_world is not None:
    col4, col5 = st.columns(2)
    col4.metric("Perf. World (CW8)", f"{perf_world:+.2f} %")
    col5.metric("GAP vs World", f"{gap:+.2f} %", delta=f"{gap:+.2f} %")

# Détail des lignes
st.markdown("#### Détail des positions")
cols = st.columns(len(perf_par_ligne))
for i, (nom, infos) in enumerate(perf_par_ligne.items()):
    with cols[i]:
        st.metric(label=nom, value=f"{infos['prix']:.2f} €", delta=f"{infos['perf']:+.2f} %")

# Feu tricolore
st.markdown("---")
bg = "#dc3545" if decision_color == "red" else "#fd7e14" if decision_color == "orange" else "#28a745"
st.markdown(f"""
<div class="big-verdict" style="background-color: {bg};">
    {decision_globale}
</div>
""", unsafe_allow_html=True)

# Détails Hydrogène
st.subheader("🔎 Détails Hydrogène (ANRJ)")
if anrj_current:
    d1, d2, d3 = st.columns(3)
    d1.metric("ANRJ", f"{anrj_current:.2f} €")
    d2.metric("SMA50", f"{anrj_sma50_now:.2f} €" if anrj_sma50_now else "N/A")
    d3.metric("RSI", f"{anrj_rsi_now:.1f}" if anrj_rsi_now else "N/A")
    st.caption(evaluate_hydrogen()[0])
else:
    st.warning("ANRJ non disponible")

# Détails EM Asia
st.subheader("🌏 Détails EM Asia (AASI)")
if aasi_current:
    e1, e2 = st.columns(2)
    e1.metric("AASI", f"{aasi_current:.2f} €")
    e2.metric("SMA50", f"{aasi_sma50_now:.2f} €" if aasi_sma50_now else "N/A")
    if ratio_current:
        e3, e4 = st.columns(2)
        e3.metric("Ratio AASI/CW8", f"{ratio_current:.4f}")
        e4.metric("Ratio moy. 20j", f"{ratio_avg20_now:.4f}" if ratio_avg20_now else "N/A")
    st.caption(evaluate_em_asia()[0])
else:
    st.warning("AASI non disponible")

# Indicateurs Macro
st.subheader("🧭 Indicateurs Macro")
m1, m2, m3, m4 = st.columns(4)
m1.metric("US 10Y", f"{us10y:.2f} %" if us10y is not None else "N/A")
m2.metric("DXY", f"{dxy:.2f}" if dxy is not None else "N/A")
m3.metric("Brent", f"{brent:.2f} $" if brent is not None else "N/A")
m4.metric("Bloom Energy", f"{bloom_close:.2f} $" if bloom_close is not None else "N/A")

st.markdown("---")
st.caption("Système décisionnel Core & Satellite · Ne constitue pas un conseil en investissement")
