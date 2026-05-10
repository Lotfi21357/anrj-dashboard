import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ---------- CONFIGURATION ----------
st.set_page_config(page_title="Core & Satellite Décisionnel", page_icon="🛰️", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp {max-width: 100%; padding: 0.5rem;}
.big-verdict {font-size:1.8rem!important;font-weight:bold;text-align:center;padding:0.8rem;border-radius:1rem;margin:1rem 0;color:white;}
</style>
""", unsafe_allow_html=True)

# ---------- DONNÉES PORTEFEUILLE ----------
CAPITAL_INITIAL = 13796.71
DATE_DEBUT = datetime(2025, 9, 17)

POSITIONS = [
    {"nom": "MSCI World AV",  "tickers": ["MWRD.PA","MWRD.L","IWDA.AS","EUNL.DE"], "parts": 36.33, "prm": 145.09},
    {"nom": "MSCI World PEA", "tickers": ["DCAM.PA"],                              "parts": 481,   "prm": 5.261},
    {"nom": "Global Hydrogen","tickers": ["ANRJ.PA"],                              "parts": 4.77, "prm": 706.06},
    {"nom": "EM Asia",        "tickers": ["AASI.PA"],                              "parts": 40.83, "prm": 52.48},
    {"nom": "Or Physique",    "tickers": ["CGLD.PA","GOLD.PA","GLD"],             "parts": 4.59, "prm": 163.39},
]
BENCHMARK_TICKER = "CW8.PA"
EXTRA_TICKERS = ["^TNX", "DX-Y.NYB", "BZ=F", "BE", "NVDA", "^SOX"]
SENTINELLES = {
    "TSMC":       ["TSM", "2330.TW"],
    "Samsung":    ["SSNLF", "005930.KS"],
    "SK Hynix":   ["HXSCL", "000660.KS"],
    "Air Liquide":["AI.PA"],
    "Bloom Energy":["BE"],  # déjà récupéré, mais on le garde ici pour la logique sentinelle
}
SENTINELLE_TICKERS = list(set(sum(SENTINELLES.values(), [])))  # tous les tickers sentinelles possibles

# ---------- FONCTIONS UTILES ----------
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
    if isinstance(series, pd.Series):
        valid = series.dropna()
        return to_float(valid.iloc[-1]) if not valid.empty else None
    if isinstance(series, np.ndarray):
        valid = series[~np.isnan(series)]
        return to_float(valid[-1]) if valid.size > 0 else None
    return to_float(series)

def safe_prev(series):
    if series is None: return None
    if isinstance(series, pd.DataFrame): series = series.squeeze()
    if isinstance(series, pd.Series):
        valid = series.dropna()
        return to_float(valid.iloc[-2]) if len(valid) > 1 else safe_last(series)
    return None

def download_ticker(ticker, start):
    try:
        df = yf.download(ticker, start=start, progress=False)
        if not df.empty:
            return df
    except:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def load_all_data():
    start = datetime.now() - timedelta(days=500)  # plus large pour SMA200
    data = {}

    # 1. Positions (avec fallback)
    for pos in POSITIONS:
        for t in pos["tickers"]:
            df = download_ticker(t, start)
            if not df.empty:
                data[t] = df
                break

    # 2. Benchmark et extra
    for t in [BENCHMARK_TICKER] + EXTRA_TICKERS:
        if t not in data:
            df = download_ticker(t, start)
            if not df.empty:
                data[t] = df

    # 3. Sentinelles (avec fallback)
    for name, tickers in SENTINELLES.items():
        for t in tickers:
            if t not in data:
                df = download_ticker(t, start)
                if not df.empty:
                    data[t] = df
                    break

    # 4. Taux de change EUR/USD pour conversion éventuelle (si GLD utilisé)
    if "EURUSD=X" not in data:
        eur_usd = download_ticker("EURUSD=X", start)
        if not eur_usd.empty:
            data["EURUSD=X"] = eur_usd

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
if not data:
    st.error("Aucune donnée récupérée. Vérifiez votre connexion.")
    st.stop()

# Taux de change EUR/USD
eur_usd_rate = safe_last(data["EURUSD=X"]["Close"]) if "EURUSD=X" in data and not data["EURUSD=X"].empty else None

# Mapping ticker utilisé pour chaque ligne
ticker_used = {}
latest_prices = {}
for pos in POSITIONS:
    used = None
    for t in pos["tickers"]:
        if t in data and not data[t].empty:
            used = t
            break
    ticker_used[pos["nom"]] = used
    if used:
        prix = safe_last(data[used]["Close"])
        if used == "GLD" and eur_usd_rate:
            prix = prix / eur_usd_rate
        latest_prices[used] = prix
    else:
        latest_prices[pos["nom"]] = None

# ---------- VALEUR DU PORTEFEUILLE ----------
positions_calculees = []
valeur_totale = 0.0
for pos in POSITIONS:
    ticker = ticker_used[pos["nom"]]
    prix = latest_prices.get(ticker)
    if prix is None or np.isnan(prix):
        positions_calculees.append({"nom": pos["nom"], "prix": None, "valeur": 0.0, "perf": None})
    else:
        valeur = pos["parts"] * prix
        perf = (prix - pos["prm"]) / pos["prm"] * 100
        positions_calculees.append({"nom": pos["nom"], "prix": prix, "valeur": valeur, "perf": perf})
        valeur_totale += valeur

gain_net = valeur_totale - CAPITAL_INITIAL
perf_totale = (gain_net / CAPITAL_INITIAL) * 100 if CAPITAL_INITIAL != 0 else 0

# ---------- BENCHMARK CW8 ----------
perf_world = None
gap = None
bench_price = None
if BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty:
    cw8_series = data[BENCHMARK_TICKER]["Close"].squeeze()
    bench_price = safe_last(cw8_series)
    if bench_price:
        try:
            start_val = cw8_series.loc[DATE_DEBUT.strftime("%Y-%m-%d")]
            start_val = to_float(start_val.iloc[0]) if isinstance(start_val, pd.Series) else to_float(start_val)
        except KeyError:
            start_val = to_float(cw8_series.iloc[0])
        if start_val and start_val > 0:
            perf_world = (bench_price / start_val - 1) * 100
            gap = perf_totale - perf_world

# ---------- PRIX DE RATTRAPAGE ----------
prix_rattrapage = None
if gap is not None and gap < 0 and ticker_used.get("Global Hydrogen"):
    # Cible : performance = perf_world => valeur cible = CAPITAL_INITIAL * (1 + perf_world/100)
    valeur_cible = CAPITAL_INITIAL * (1 + perf_world/100)
    diff = valeur_cible - valeur_totale
    parts_anrj = None
    for pos in POSITIONS:
        if pos["nom"] == "Global Hydrogen":
            parts_anrj = pos["parts"]
            break
    if parts_anrj and parts_anrj > 0:
        anrj_prix_actuel = safe_last(data[ticker_used["Global Hydrogen"]]["Close"]) if ticker_used["Global Hydrogen"] else None
        if anrj_prix_actuel:
            nouveau_prix = anrj_prix_actuel + (diff / parts_anrj)
            prix_rattrapage = nouveau_prix
else:
    if gap is not None and gap >= 0:
        prix_rattrapage = "Objectif atteint"

# ---------- INDICATEURS HYDROGÈNE ----------
anrj_series = None
if "ANRJ.PA" in data and not data["ANRJ.PA"].empty:
    anrj_series = data["ANRJ.PA"]["Close"].squeeze()
anrj_current = safe_last(anrj_series)
anrj_sma20_now = anrj_sma50_now = anrj_sma200_now = anrj_rsi_now = None
anrj_ath30 = None
if anrj_series is not None and len(anrj_series) >= 20:
    anrj_sma20 = compute_sma(anrj_series, 20)
    anrj_sma50 = compute_sma(anrj_series, 50)
    anrj_sma200 = compute_sma(anrj_series, 200)
    anrj_rsi = compute_rsi(anrj_series, 14)
    anrj_sma20_now = safe_last(anrj_sma20)
    anrj_sma50_now = safe_last(anrj_sma50)
    anrj_sma200_now = safe_last(anrj_sma200)
    anrj_rsi_now = safe_last(anrj_rsi)
    # ATH 30 jours
    ath30_series = anrj_series.rolling(30, min_periods=1).max()
    anrj_ath30 = safe_last(ath30_series)

# ---------- INDICATEURS EM ASIA ----------
aasi_series = None
if "AASI.PA" in data and not data["AASI.PA"].empty:
    aasi_series = data["AASI.PA"]["Close"].squeeze()
aasi_current = safe_last(aasi_series)
aasi_sma20_now = aasi_sma50_now = None
ratio_current = ratio_avg20_now = None
if aasi_series is not None and len(aasi_series) >= 20:
    aasi_sma20 = compute_sma(aasi_series, 20)
    aasi_sma50 = compute_sma(aasi_series, 50)
    aasi_sma20_now = safe_last(aasi_sma20)
    aasi_sma50_now = safe_last(aasi_sma50)
    if BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty:
        cw8_s = data[BENCHMARK_TICKER]["Close"].squeeze()
        if cw8_s is not None and len(cw8_s) >= 20:
            ratio = aasi_series / cw8_s
            ratio_avg20 = ratio.rolling(20).mean()
            ratio_current = safe_last(ratio)
            ratio_avg20_now = safe_last(ratio_avg20)

# ---------- MACRO ----------
us10y = dxy = brent = None
if "^TNX" in data:
    tnx_val = safe_last(data["^TNX"]["Close"].squeeze())
    if tnx_val is not None:
        us10y = tnx_val / 10 if tnx_val > 20 else tnx_val
if "DX-Y.NYB" in data:
    dxy = safe_last(data["DX-Y.NYB"]["Close"].squeeze())
if "BZ=F" in data:
    brent = safe_last(data["BZ=F"]["Close"].squeeze())

bloom_close = bloom_prev = nvidia_close = sox_close = None
if "BE" in data and not data["BE"].empty:
    be_s = data["BE"]["Close"].squeeze()
    bloom_close = safe_last(be_s)
    bloom_prev = safe_prev(be_s)
if "NVDA" in data and not data["NVDA"].empty:
    nvidia_close = safe_last(data["NVDA"]["Close"].squeeze())
if "^SOX" in data and not data["^SOX"].empty:
    sox_close = safe_last(data["^SOX"]["Close"].squeeze())

# ---------- SENTINELLES ----------
sentinelle_data = {}
for name, tickers in SENTINELLES.items():
    prix = None
    sma20 = None
    for t in tickers:
        if t in data and not data[t].empty:
            prix_series = data[t]["Close"].squeeze()
            prix = safe_last(prix_series)
            if len(prix_series) >= 20:
                sma20_series = compute_sma(prix_series, 20)
                sma20 = safe_last(sma20_series)
            break
    sentinelle_data[name] = {"prix": prix, "sma20": sma20}

# ---------- RÈGLES DE SORTIE ----------
def evaluate_hydrogen():
    if anrj_current is None:
        return "⚠️ Données ANRJ manquantes", "gray"
    # Stop-loss absolu
    if anrj_current < 706.06:
        return "🚨 STOP-LOSS 50% : COUPURE 50% VERS WORLD", "red"
    # Take profit
    if anrj_current > 812 and anrj_rsi_now and anrj_rsi_now > 68:
        return "💰 TAKE PROFIT : ARBITRAGE 30% VERS WORLD", "green"
    # Trailing stop -5% depuis ATH 30j
    if anrj_ath30 and anrj_current < anrj_ath30 * 0.95:
        return "🔶 ALLÉGEMENT PRÉVENTIF (Protection des gains, -5% ATH 30j)", "orange"
    # Sous SMA20
    if anrj_sma20_now and anrj_current < anrj_sma20_now:
        return "🔶 ARBITRAGE VERS WORLD (sous SMA20)", "orange"
    # Règle macro défensif
    conditions_def = False
    if us10y is not None and us10y > 4.60: conditions_def = True
    if brent is not None and brent < 90: conditions_def = True
    if bloom_close and bloom_prev and bloom_prev != 0 and (bloom_close/bloom_prev - 1) < -0.15: conditions_def = True
    if conditions_def:
        return "🛡️ MODE DÉFENSIF - RÉDUCTION 15%", "orange"
    # sinon maintien si au-dessus SMA50 (ancienne règle de confort)
    if anrj_sma50_now and anrj_current > anrj_sma50_now:
        return "✅ MAINTIEN HYDROGÈNE - Tendance intacte", "green"
    return "ℹ️ SURVEILLANCE HYDROGÈNE", "orange"

def evaluate_em_asia():
    if aasi_current is None:
        return "⚠️ Données AASI manquantes", "gray"
    # TP avec trailing stop si > 60.35
    if aasi_current > 60.35:
        if aasi_series is not None:
            highest = aasi_series.rolling(50, min_periods=1).max()
            highest_val = safe_last(highest)
            if highest_val and aasi_current < highest_val * 0.92:
                return "🎯 TRAILING STOP : -8% depuis +haut, ARBITRAGE 50%", "red"
            else:
                return "📈 TRAILING STOP ACTIF (seuil -8% du +haut)", "green"
    # Momentum cassé
    if ratio_avg20_now and ratio_current and ratio_current < ratio_avg20_now:
        return "📉 MOMENTUM CASSÉ : ARBITRAGE 50% VERS WORLD", "red"
    # Nvidia sous SMA50
    if nvidia_close and "NVDA" in data:
        nvda_s = data["NVDA"]["Close"].squeeze()
        if len(nvda_s) >= 50:
            nvda_sma50 = compute_sma(nvda_s, 50)
            nvda_sma50_now = safe_last(nvda_sma50)
            if nvda_sma50_now and nvidia_close < nvda_sma50_now:
                return "📉 NVIDIA SOUS SMA50 → ARBITRAGE 50% EM ASIA", "red"
    # Macro
    if us10y and us10y > 4.60 and dxy and dxy > 102:
        return "🌍 ALERTE MACRO - COUPURE EM ASIA", "red"
    # Maintien
    if aasi_sma50_now and aasi_current > aasi_sma50_now:
        return "✅ MAINTIEN EM ASIA - Tendance intacte", "green"
    return "ℹ️ SURVEILLANCE EM ASIA", "orange"

def evaluate_sentinelles():
    alerts = []
    # Vérifier sentinelles Asie
    for name in ["TSMC", "Samsung"]:
        info = sentinelle_data.get(name)
        if info and info["prix"] and info["sma20"]:
            if info["prix"] < info["sma20"]:
                alerts.append(f"⚠️ {name} sous SMA20")
    # Air Liquide sous SMA20 ?
    info_al = sentinelle_data.get("Air Liquide")
    if info_al and info_al["prix"] and info_al["sma20"]:
        if info_al["prix"] < info_al["sma20"]:
            alerts.append(f"⚠️ Air Liquide sous SMA20")
    # Macro sentinelles
    if us10y and us10y > 4.60:
        alerts.append("⚠️ US10Y > 4.60%")
    if dxy and dxy > 102:
        alerts.append("⚠️ DXY > 102")
    if alerts:
        return " ; ".join(alerts), "orange"
    else:
        return "✅ Sentinelles OK", "green"

# Décision globale
def global_decision():
    h_msg, h_col = evaluate_hydrogen()
    a_msg, a_col = evaluate_em_asia()
    s_msg, s_col = evaluate_sentinelles()
    messages = []
    if h_col == "red" or a_col == "red":
        messages.append("🔴 " + (h_msg if h_col=="red" else a_msg))
    if h_col == "orange" or a_col == "orange" or s_col == "orange":
        orange_msgs = []
        if h_col=="orange": orange_msgs.append(h_msg)
        if a_col=="orange": orange_msgs.append(a_msg)
        if s_col=="orange": orange_msgs.append(s_msg)
        messages.append("🟡 " + " | ".join(orange_msgs))
    if not messages:
        messages.append("🟢 " + s_msg)
    return "\n".join(messages), "red" if any(c in ["red"] for c in [h_col,a_col]) else "orange" if any(c=="orange" for c in [h_col,a_col,s_col]) else "green"

decision_globale, decision_color = global_decision()

# ---------- PRÉPARATION DU GRAPHIQUE COMPARATIF ----------
def compute_historical_value(data, positions, ticker_used):
    """Calcule la valeur quotidienne du portefeuille depuis DATE_DEBUT."""
    # Trouver la date de début commune
    start_date = DATE_DEBUT
    # Récupérer les historiques de chaque ticker utilisé
    df_combined = None
    for pos in positions:
        t = ticker_used.get(pos["nom"])
        if t and t in data:
            ts = data[t]["Close"].squeeze()
            ts = ts[ts.index >= start_date]
            if df_combined is None:
                df_combined = pd.DataFrame(index=ts.index)
            df_combined[t] = ts
    if df_combined is None or df_combined.empty:
        return None
    # Forward fill weekend
    df_combined = df_combined.ffill()
    # Calculer la valeur totale
    valeur_hist = pd.Series(0.0, index=df_combined.index)
    for pos in positions:
        t = ticker_used.get(pos["nom"])
        if t and t in df_combined.columns:
            # conversion éventuelle
            prix_series = df_combined[t]
            if t == "GLD" and eur_usd_rate:
                prix_series = prix_series / eur_usd_rate
            valeur_hist += pos["parts"] * prix_series
    # Valeur initiale
    val_init = valeur_hist.iloc[0]
    if val_init == 0:
        return None
    valeur_norm = valeur_hist / val_init * 100
    return valeur_norm

valeur_hist_port = None
valeur_hist_cw8 = None
if BENCHMARK_TICKER in data:
    cw8_hist = data[BENCHMARK_TICKER]["Close"].squeeze()
    if not cw8_hist.empty:
        try:
            start_idx = cw8_hist.index.get_loc(DATE_DEBUT, method='ffill')
            cw8_from_start = cw8_hist.iloc[start_idx:]
            if len(cw8_from_start) > 0:
                valeur_hist_cw8 = cw8_from_start / cw8_from_start.iloc[0] * 100
        except:
            pass

valeur_hist_port = compute_historical_value(data, POSITIONS, ticker_used)

# ---------- INTERFACE ----------
st.title("🛰️ Core & Satellite Décisionnel")
st.caption(f"Données du {datetime.now().strftime('%d/%m/%Y %H:%M')} (dernières clôtures)")

st.markdown("### 📈 Performance Globale")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Valeur totale", f"{valeur_totale:,.2f}€")
col2.metric("Gain net", f"{gain_net:+,.2f}€")
col3.metric("Performance", f"{perf_totale:+.2f}%")
col4.metric("Perf. World (CW8)", f"{perf_world:+.2f}%" if perf_world else "N/A")

col5, col6 = st.columns(2)
if gap is not None:
    col5.metric("Écart vs World", f"{gap:+.2f}%")
else:
    col5.metric("Écart vs World", "N/A")
if prix_rattrapage:
    if isinstance(prix_rattrapage, str):
        col6.metric("Prix ANRJ rattrapage", prix_rattrapage)
    else:
        col6.metric("Prix ANRJ pour rattraper", f"{prix_rattrapage:.2f}€")
else:
    col6.metric("Prix ANRJ rattrapage", "Calcul impossible")

st.markdown("#### Détail des positions")
cols = st.columns(len(positions_calculees))
for i, p in enumerate(positions_calculees):
    with cols[i]:
        prix_str = f"{p['prix']:.2f}€" if p['prix'] is not None else "N/A"
        perf_str = f"{p['perf']:+.2f}%" if p['perf'] is not None else "N/A"
        st.metric(label=p['nom'], value=prix_str, delta=perf_str)

# Feu tricolore
bg = {"red":"#dc3545","orange":"#fd7e14","green":"#28a745"}.get(decision_color, "#6c757d")
st.markdown(f"<div class='big-verdict' style='background-color:{bg};'>{decision_globale}</div>", unsafe_allow_html=True)

st.subheader("🔎 Détails Hydrogène (ANRJ)")
if anrj_current:
    d1,d2,d3,d4 = st.columns(4)
    d1.metric("ANRJ", f"{anrj_current:.2f}€")
    d2.metric("SMA20", f"{anrj_sma20_now:.2f}€" if anrj_sma20_now else "N/A")
    d3.metric("ATH 30j", f"{anrj_ath30:.2f}€" if anrj_ath30 else "N/A")
    d4.metric("RSI", f"{anrj_rsi_now:.1f}" if anrj_rsi_now else "N/A")
    st.caption(evaluate_hydrogen()[0])
else:
    st.warning("ANRJ indisponible")

st.subheader("🌏 Détails EM Asia (AASI)")
if aasi_current:
    e1,e2,e3 = st.columns(3)
    e1.metric("AASI", f"{aasi_current:.2f}€")
    e2.metric("SMA20", f"{aasi_sma20_now:.2f}€" if aasi_sma20_now else "N/A")
    e3.metric("Ratio AASI/CW8", f"{ratio_current:.4f}" if ratio_current else "N/A")
    st.caption(evaluate_em_asia()[0])
else:
    st.warning("AASI indisponible")

st.subheader("🛰️ Sentinelles")
sentinelle_msg, sentinelle_col = evaluate_sentinelles()
st.caption(sentinelle_msg)
colS = st.columns(len(sentinelle_data))
for i, (name, info) in enumerate(sentinelle_data.items()):
    with colS[i]:
        prix = info["prix"]
        prix_str = f"{prix:.2f}" if prix else "N/A"
        sma20_str = f"{info['sma20']:.2f}" if info["sma20"] else "N/A"
        st.metric(label=name, value=prix_str, delta=sma20_str if info["sma20"] else None)

st.subheader("🧭 Indicateurs Macro")
m1,m2,m3,m4 = st.columns(4)
m1.metric("US 10Y", f"{us10y:.2f}%" if us10y is not None else "N/A")
m2.metric("DXY", f"{dxy:.2f}" if dxy else "N/A")
m3.metric("Brent", f"{brent:.2f}$" if brent else "N/A")
m4.metric("Bloom Energy", f"{bloom_close:.2f}$" if bloom_close else "N/A")

# Graphique comparatif
st.subheader("📊 Performance cumulée (base 100)")
if valeur_hist_port is not None and valeur_hist_cw8 is not None:
    df_chart = pd.DataFrame({
        "Portefeuille": valeur_hist_port,
        "MSCI World (CW8)": valeur_hist_cw8
    }).dropna()
    st.line_chart(df_chart)
elif valeur_hist_port is not None:
    st.line_chart(valeur_hist_port)
elif valeur_hist_cw8 is not None:
    st.line_chart(valeur_hist_cw8)
else:
    st.info("Données insuffisantes pour le graphique comparatif.")

st.markdown("---")
st.caption("Système décisionnel Core & Satellite · Ne constitue pas un conseil en investissement")
