import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import warnings
warnings.filterwarnings("ignore")

# ---------- CONFIGURATION ----------
st.set_page_config(page_title="Cockpit Décisionnel", page_icon="🛰️", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp {max-width: 100%; padding: 0.5rem;}
.big-verdict {font-size:1.8rem!important;font-weight:bold;text-align:center;padding:0.8rem;border-radius:1rem;margin:1rem 0;color:white;}
.small-text {font-size:0.85rem; color: #6c757d;}
</style>
""", unsafe_allow_html=True)

# ---------- DONNÉES PORTEFEUILLE ----------
CAPITAL_INITIAL = 13796.71
DATE_DEBUT = datetime(2025, 9, 17)

POSITIONS = [
    {"nom": "MSCI World AV",  "tickers": ["MWRD.PA","MWRD.L","IWDA.AS","EUNL.DE"], "parts": 36.33, "prm": 145.09},
    {"nom": "MSCI World PEA", "tickers": ["DCAM.PA"],                              "parts": 481,   "prm": 5.261},
    {"nom": "Global Hydrogen","tickers": ["ANRJ.PA"],                              "parts": 4.77,  "prm": 706.06},
    {"nom": "EM Asia",        "tickers": ["AASI.PA"],                              "parts": 40.83, "prm": 52.48},
    {"nom": "Or Physique",    "tickers": ["CGLD.PA","GOLD.PA","GLD"],             "parts": 4.59,  "prm": 163.39},
]
BENCHMARK_TICKER = "CW8.PA"
EXTRA_TICKERS = ["^TNX", "DX-Y.NYB", "BZ=F", "BE", "NVDA", "^SOX"]
SENTINELLES = {
    "TSMC":         ["TSM", "2330.TW"],
    "Samsung":      ["SSNLF", "005930.KS"],
    "SK Hynix":     ["HXSCL", "000660.KS"],
    "Air Liquide":  ["AI.PA"],
    "Bloom Energy": ["BE"],
}

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
    start = datetime.now() - timedelta(days=500)
    data = {}

    for pos in POSITIONS:
        for t in pos["tickers"]:
            df = download_ticker(t, start)
            if not df.empty:
                data[t] = df
                break

    for t in [BENCHMARK_TICKER] + EXTRA_TICKERS:
        if t not in data:
            df = download_ticker(t, start)
            if not df.empty:
                data[t] = df

    for name, tickers in SENTINELLES.items():
        for t in tickers:
            if t not in data:
                df = download_ticker(t, start)
                if not df.empty:
                    data[t] = df
                    break

    if "EURUSD=X" not in data:
        eur = download_ticker("EURUSD=X", start)
        if not eur.empty:
            data["EURUSD=X"] = eur

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
    st.error("Aucune donnée récupérée.")
    st.stop()

eur_usd_rate = safe_last(data["EURUSD=X"]["Close"]) if "EURUSD=X" in data and not data["EURUSD=X"].empty else None

ticker_used = {}
latest_prices = {}
prev_prices = {}  # pour les variations journalières
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
        prev_prices[used] = safe_prev(data[used]["Close"])
    else:
        latest_prices[pos["nom"]] = None
        prev_prices[pos["nom"]] = None

# ---------- VALEUR DU PORTEFEUILLE ET PERFORMANCES JOURNALIÈRES ----------
positions_calculees = []
valeur_totale = 0.0
valeur_veille = 0.0
for pos in POSITIONS:
    ticker = ticker_used[pos["nom"]]
    prix = latest_prices.get(ticker)
    prix_veille = prev_prices.get(ticker)
    if prix is None or np.isnan(prix):
        positions_calculees.append({"nom": pos["nom"], "prix": None, "valeur": 0.0, "perf": None, "var_jour": None})
    else:
        valeur = pos["parts"] * prix
        perf = (prix - pos["prm"]) / pos["prm"] * 100
        # variation journalière
        if prix_veille is not None and not np.isnan(prix_veille) and prix_veille != 0:
            var_jour = (prix - prix_veille) / prix_veille * 100
        else:
            var_jour = None
        positions_calculees.append({"nom": pos["nom"], "prix": prix, "valeur": valeur, "perf": perf, "var_jour": var_jour})
        valeur_totale += valeur
        if prix_veille is not None and not np.isnan(prix_veille):
            valeur_veille += pos["parts"] * prix_veille
        else:
            valeur_veille += valeur  # fallback

gain_net = valeur_totale - CAPITAL_INITIAL
perf_totale = (gain_net / CAPITAL_INITIAL) * 100 if CAPITAL_INITIAL != 0 else 0

# Performance du jour
perf_jour_euro = valeur_totale - valeur_veille
perf_jour_pct = (perf_jour_euro / valeur_veille * 100) if valeur_veille != 0 else 0.0

# ---------- BENCHMARK CW8 ----------
perf_world = None
gap = None
bench_price = None
cw8_prev = None
if BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty:
    cw8_series = data[BENCHMARK_TICKER]["Close"].squeeze()
    bench_price = safe_last(cw8_series)
    cw8_prev = safe_prev(cw8_series)
    if bench_price:
        try:
            start_val = cw8_series.loc[DATE_DEBUT.strftime("%Y-%m-%d")]
            start_val = to_float(start_val.iloc[0]) if isinstance(start_val, pd.Series) else to_float(start_val)
        except KeyError:
            start_val = to_float(cw8_series.iloc[0])
        if start_val and start_val > 0:
            perf_world = (bench_price / start_val - 1) * 100
            gap = perf_totale - perf_world

# Variation journalière du World et du GAP
perf_world_jour = None
gap_jour = None
if bench_price and cw8_prev and cw8_prev != 0:
    perf_world_jour = (bench_price - cw8_prev) / cw8_prev * 100
    if perf_jour_pct is not None:
        gap_jour = perf_jour_pct - perf_world_jour

# ---------- PRIX DE RATTRAPAGE ----------
prix_rattrapage = None
if gap is not None and gap < 0 and ticker_used.get("Global Hydrogen"):
    valeur_cible = CAPITAL_INITIAL * (1 + perf_world/100)
    diff = valeur_cible - valeur_totale
    anrj_parts = None
    for pos in POSITIONS:
        if pos["nom"] == "Global Hydrogen":
            anrj_parts = pos["parts"]
            break
    if anrj_parts and anrj_parts > 0:
        anrj_prix_actuel = safe_last(data[ticker_used["Global Hydrogen"]]["Close"]) if ticker_used["Global Hydrogen"] else None
        if anrj_prix_actuel:
            nouveau_prix = anrj_prix_actuel + (diff / anrj_parts)
            prix_rattrapage = nouveau_prix
else:
    if gap is not None and gap >= 0:
        prix_rattrapage = "Objectif atteint"

# ---------- INDICATEURS HYDROGÈNE ----------
anrj_series = None
if "ANRJ.PA" in data and not data["ANRJ.PA"].empty:
    anrj_series = data["ANRJ.PA"]["Close"].squeeze()
anrj_current = safe_last(anrj_series)
anrj_sma20 = anrj_sma50 = anrj_rsi = anrj_ath30 = None
if anrj_series is not None and len(anrj_series) >= 20:
    anrj_sma20 = safe_last(compute_sma(anrj_series, 20))
    anrj_sma50 = safe_last(compute_sma(anrj_series, 50))
    anrj_rsi = safe_last(compute_rsi(anrj_series, 14))
    ath30_series = anrj_series.rolling(30, min_periods=1).max()
    anrj_ath30 = safe_last(ath30_series)

# ---------- INDICATEURS EM ASIA ----------
aasi_series = None
if "AASI.PA" in data and not data["AASI.PA"].empty:
    aasi_series = data["AASI.PA"]["Close"].squeeze()
aasi_current = safe_last(aasi_series)
aasi_sma20 = aasi_sma50 = None
if aasi_series is not None and len(aasi_series) >= 20:
    aasi_sma20 = safe_last(compute_sma(aasi_series, 20))
    aasi_sma50 = safe_last(compute_sma(aasi_series, 50))

# ---------- SENTINELLES ----------
sentinelle_info = {}
for name, tickers in SENTINELLES.items():
    prix = sma20 = None
    for t in tickers:
        if t in data and not data[t].empty:
            ts = data[t]["Close"].squeeze()
            prix = safe_last(ts)
            if len(ts) >= 20:
                sma20 = safe_last(compute_sma(ts, 20))
            break
    sentinelle_info[name] = {"prix": prix, "sma20": sma20}

# ---------- MACRO ----------
us10y = dxy = brent = None
if "^TNX" in data:
    raw = safe_last(data["^TNX"]["Close"].squeeze())
    us10y = raw / 10 if raw and raw > 20 else raw
if "DX-Y.NYB" in data:
    dxy = safe_last(data["DX-Y.NYB"]["Close"].squeeze())
if "BZ=F" in data:
    brent = safe_last(data["BZ=F"]["Close"].squeeze())

bloom_close = None
if "BE" in data and not data["BE"].empty:
    be_series = data["BE"]["Close"].squeeze()
    bloom_close = safe_last(be_series)

# ---------- RÈGLES DÉCISIONNELLES ----------
def evaluate_hydrogen():
    if anrj_current is None: return "⚠️ ANRJ manquant", "gray"
    if anrj_current < 706.06: return "🚨 STOP-LOSS : COUPURE 50% VERS WORLD", "red"
    if anrj_current > 812 and anrj_rsi and anrj_rsi > 68: return "💰 TAKE PROFIT 30%", "green"
    if anrj_ath30 and anrj_current < anrj_ath30 * 0.95: return "🔶 ALLÉGEMENT PRÉVENTIF (Protection des gains, -5% ATH 30j)", "orange"
    if anrj_sma20 and anrj_current < anrj_sma20: return "🔶 SOUS SMA20 – ARBITRAGE VERS WORLD", "orange"
    if anrj_sma50 and anrj_current > anrj_sma50: return "✅ MAINTIEN HYDROGÈNE", "green"
    return "ℹ️ SURVEILLANCE", "orange"

def evaluate_em_asia():
    if aasi_current is None: return "⚠️ AASI manquant", "gray"
    if aasi_current > 60.35:
        if aasi_series is not None:
            highest = aasi_series.rolling(50, min_periods=1).max()
            highest_val = safe_last(highest)
            if highest_val and aasi_current < highest_val * 0.92: return "🎯 TRAILING STOP -8% : ARBITRAGE 50%", "red"
            else: return "📈 TRAILING STOP ACTIF", "green"
    if aasi_sma20 and aasi_current < aasi_sma20: return "🔶 SOUS SMA20 – SURVEILLANCE RENFORCÉE", "orange"
    if aasi_sma50 and aasi_current > aasi_sma50: return "✅ MAINTIEN EM ASIA", "green"
    return "ℹ️ SURVEILLANCE", "orange"

def evaluate_sentinelles():
    alerts = []
    tsmc = sentinelle_info.get("TSMC")
    if tsmc and tsmc["prix"] and tsmc["sma20"] and tsmc["prix"] < tsmc["sma20"]: alerts.append("⚠️ TSMC sous SMA20")
    sam = sentinelle_info.get("Samsung")
    if sam and sam["prix"] and sam["sma20"] and sam["prix"] < sam["sma20"]: alerts.append("⚠️ Samsung sous SMA20")
    al = sentinelle_info.get("Air Liquide")
    if al and al["prix"] and al["sma20"] and al["prix"] < al["sma20"]: alerts.append("⚠️ Air Liquide sous SMA20")
    if "BE" in data:
        be_series = data["BE"]["Close"].squeeze()
        if len(be_series) >= 3:
            be_latest = safe_last(be_series)
            be_2d_ago = safe_last(be_series.iloc[:-2]) if len(be_series) > 2 else None
            if be_latest and be_2d_ago and (be_latest / be_2d_ago - 1) < -0.03: alerts.append("⚠️ Bloom Energy -3% en 48h")
    if us10y and us10y > 4.60: alerts.append("⚠️ US10Y > 4.60%")
    if dxy and dxy > 102: alerts.append("⚠️ DXY > 102")
    if alerts: return " | ".join(alerts), "orange"
    return "✅ Sentinelles OK", "green"

def decision_finale():
    h_msg, h_col = evaluate_hydrogen()
    a_msg, a_col = evaluate_em_asia()
    s_msg, s_col = evaluate_sentinelles()
    if "red" in [h_col, a_col]:
        msg = h_msg if h_col=="red" else a_msg
        return f"🔴 ACTION REQUISE : {msg}", "red"
    if "orange" in [h_col, a_col, s_col]:
        parties = []
        if h_col=="orange": parties.append(h_msg)
        if a_col=="orange": parties.append(a_msg)
        if s_col=="orange": parties.append(s_msg)
        return f"🟡 VIGILANCE : {' | '.join(parties)}", "orange"
    return "🟢 MAINTIEN GLOBAL", "green"

decision_globale, decision_color = decision_finale()

# Score de risque satellite
valeur_anrj = next((p["valeur"] for p in positions_calculees if p["nom"] == "Global Hydrogen"), 0)
valeur_aasi = next((p["valeur"] for p in positions_calculees if p["nom"] == "EM Asia"), 0)
poids_satellite = (valeur_anrj + valeur_aasi) / valeur_totale * 100 if valeur_totale > 0 else 0
alerte_risque = poids_satellite > 45

# ---------- HEURE DE PARIS ----------
now = datetime.now(ZoneInfo("Europe/Paris"))

# ---------- INTERFACE ----------
st.title("🛰️ Cockpit Décisionnel")
st.caption(f"Données du {now.strftime('%d/%m/%Y %H:%M')} (heure de Paris)")

# Section Executive
st.markdown("### 📊 Executive")
col1, col2, col3 = st.columns(3)
col1.metric("Valeur totale", f"{valeur_totale:,.2f}€", delta=f"{perf_jour_euro:+,.2f}€ (auj.)")
col2.metric("Gain net", f"{gain_net:+,.2f}€")
col3.metric("Performance", f"{perf_totale:+.2f}%", delta=f"{perf_jour_pct:+.2f}% (auj.)")

if perf_world is not None:
    col4, col5 = st.columns(2)
    col4.metric("Perf. World (CW8)", f"{perf_world:+.2f}%", delta=f"{perf_world_jour:+.2f}% (auj.)" if perf_world_jour is not None else None)
    col5.metric("GAP vs World", f"{gap:+.2f}%", delta=f"{gap_jour:+.2f}% (auj.)" if gap_jour is not None else None)

# Détail positions
st.markdown("#### Positions")
cols = st.columns(len(positions_calculees))
for i, p in enumerate(positions_calculees):
    with cols[i]:
        prix_str = f"{p['prix']:.2f}€" if p['prix'] is not None else "N/A"
        perf_str = f"{p['perf']:+.2f}%" if p['perf'] is not None else "N/A"
        var_jour_str = f"{p['var_jour']:+.2f}% auj." if p['var_jour'] is not None else ""
        st.metric(label=p['nom'], value=prix_str, delta=perf_str)
        if var_jour_str:
            st.caption(var_jour_str)

# Feu tricolore
bg = {"red":"#dc3545","orange":"#fd7e14","green":"#28a745"}[decision_color]
st.markdown(f"<div class='big-verdict' style='background-color:{bg};'>{decision_globale}</div>", unsafe_allow_html=True)

# Score de risque
st.markdown("#### ⚖️ Poids Satellites")
jauge = poids_satellite / 100
st.progress(min(jauge, 1.0))
st.write(f"ANRJ + EM Asia : **{poids_satellite:.1f}%** du portefeuille")
if alerte_risque:
    st.warning("⚠️ Poids satellites > 45% – Exposition élevée aux thématiques")

# Détails Hydrogène
st.subheader("🔎 Hydrogène (ANRJ)")
if anrj_current:
    d1,d2,d3,d4 = st.columns(4)
    d1.metric("ANRJ", f"{anrj_current:.2f}€")
    d2.metric("SMA20", f"{anrj_sma20:.2f}€" if anrj_sma20 else "N/A")
    d3.metric("ATH 30j", f"{anrj_ath30:.2f}€" if anrj_ath30 else "N/A")
    d4.metric("RSI", f"{anrj_rsi:.1f}" if anrj_rsi else "N/A")
    st.caption(evaluate_hydrogen()[0])
else:
    st.warning("ANRJ indisponible")

# Détails EM Asia
st.subheader("🌏 EM Asia (AASI)")
if aasi_current:
    e1,e2 = st.columns(2)
    e1.metric("AASI", f"{aasi_current:.2f}€")
    e2.metric("SMA20", f"{aasi_sma20:.2f}€" if aasi_sma20 else "N/A")
    st.caption(evaluate_em_asia()[0])
else:
    st.warning("AASI indisponible")

# Sentinelles
st.subheader("🛰️ Sentinelles")
s_msg, s_col = evaluate_sentinelles()
st.caption(s_msg)
sentinel_rows = []
for name, info in sentinelle_info.items():
    prix = info["prix"]
    sma20 = info["sma20"]
    sentinel_rows.append({"Nom": name, "Dernier": f"{prix:.2f}" if prix else "N/A", "SMA20": f"{sma20:.2f}" if sma20 else "N/A"})
if sentinel_rows:
    st.dataframe(pd.DataFrame(sentinel_rows), use_container_width=True, hide_index=True)

# Macro
st.subheader("🧭 Macro")
m1,m2,m3,m4 = st.columns(4)
m1.metric("US 10Y", f"{us10y:.2f}%" if us10y else "N/A")
m2.metric("DXY", f"{dxy:.2f}" if dxy else "N/A")
m3.metric("Brent", f"{brent:.2f}$" if brent else "N/A")
m4.metric("Bloom Energy", f"{bloom_close:.2f}$" if bloom_close else "N/A")

# Graphique (conservé)
def compute_historical_value():
    start_date = DATE_DEBUT
    df_combined = None
    for pos in POSITIONS:
        t = ticker_used.get(pos["nom"])
        if t and t in data:
            ts = data[t]["Close"].squeeze()
            ts = ts[ts.index >= start_date]
            if df_combined is None:
                df_combined = pd.DataFrame(index=ts.index)
            df_combined[t] = ts
    if df_combined is None or df_combined.empty: return None
    df_combined = df_combined.ffill()
    valeur_hist = pd.Series(0.0, index=df_combined.index)
    for pos in POSITIONS:
        t = ticker_used.get(pos["nom"])
        if t and t in df_combined.columns:
            prix_series = df_combined[t]
            if t == "GLD" and eur_usd_rate:
                prix_series = prix_series / eur_usd_rate
            valeur_hist += pos["parts"] * prix_series
    val_init = valeur_hist.iloc[0]
    return (valeur_hist / val_init) * 100 if val_init != 0 else None

port_hist = compute_historical_value()
cw8_hist = None
if BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty:
    cw8_series = data[BENCHMARK_TICKER]["Close"].squeeze()
    try:
        start_idx = cw8_series.index.get_loc(DATE_DEBUT, method='ffill')
        cw8_from_start = cw8_series.iloc[start_idx:]
        if len(cw8_from_start) > 0:
            cw8_hist = (cw8_from_start / cw8_from_start.iloc[0]) * 100
    except:
        pass

st.subheader("📈 Performance Cumulée (base 100)")
if port_hist is not None and cw8_hist is not None:
    combined = pd.DataFrame({"Portefeuille": port_hist, "MSCI World": cw8_hist}).dropna()
    st.line_chart(combined)
elif port_hist is not None:
    st.line_chart(port_hist)
elif cw8_hist is not None:
    st.line_chart(cw8_hist)
else:
    st.info("Données insuffisantes pour le graphique.")

st.markdown("---")
st.caption("Cockpit Décisionnel · Ne constitue pas un conseil en investissement")
