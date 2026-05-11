Import streamlit as st
Import yfinance as yf
Import pandas as pd
Import numpy as np
From datetime import datetime, timedelta
From zoneinfo import ZoneInfo
Import warnings
Warnings.filterwarnings(« ignore »)

# ---------- CONFIGURATION ----------
St.set_page_config(page_title= »Cockpit Décisionnel », page_icon= »🛰️ », layout= »centered », initial_sidebar_state= »collapsed »)

St.markdown(« « « 
<style>
.stApp {max-width : 100% ; padding : 0.5rem ;}
.big-verdict {font-size :1.8rem !important ;font-weight :bold ;text-align :center ;padding :0.8rem ;border-radius :1rem ;margin :1rem 0 ;color :white ;}
.small-text {font-size :0.85rem ; color : #6c757d ;}
</style>
« « « , unsafe_allow_html=True)

# ---------- DONNÉES PORTEFEUILLE ----------
CAPITAL_INITIAL = 13796.71
DATE_DEBUT = datetime(2025, 9, 17)

POSITIONS = [
    {« nom » : « MSCI World AV »,  « tickers » : [« MWRD.PA », »MWRD.L », »IWDA.AS », »EUNL.DE »], « parts » : 36.33, « prm » : 145.09},
    {« nom » : « MSCI World PEA », « tickers » : [« DCAM.PA »],                              « parts » : 481,   « prm » : 5.261},
    {« nom » : « Global Hydrogen », »tickers » : [« ANRJ.PA »],                              « parts » : 4.77,  « prm » : 706.06},
    {« nom » : « EM Asia »,        « tickers » : [« AASI.PA »],                              « parts » : 40.83, « prm » : 52.48},
    {« nom » : « Or Physique »,    « tickers » : [« CGLD.PA », »GOLD.PA », »GLD »],             « parts » : 4.59,  « prm » : 163.39},
]
BENCHMARK_TICKER = « CW8.PA »
EXTRA_TICKERS = [« ^TNX », « DX-Y.NYB », « BZ=F », « BE », « NVDA », « ^SOX »]
SENTINELLES = {
    « TSMC » :         [« TSM », « 2330.TW »],
    « Samsung » :      [« SSNLF », « 005930.KS »],
    « SK Hynix » :     [« HXSCL », « 000660.KS »],
    « Air Liquide » :  [« AI.PA »],
    « Bloom Energy » : [« BE »],
}

# ---------- FONCTIONS UTILES ----------
Def to_float(val) :
    If val is None : return None
    If isinstance(val, (int, float, np.floating, np.integer)) : return float(val)
    If isinstance(val, pd.Series) : return float(val.iloc[0]) if not val.empty else None
    If isinstance(val, np.ndarray) : return float(val.flat[0]) if val.size > 0 else None
    Try : return float(val)
    Except : return None

Def safe_last(series) :
    If series is None : return None
    If isinstance(series, pd.DataFrame) : series = series.squeeze()
    If isinstance(series, pd.Series) :
        Valid = series.dropna()
        Return to_float(valid.iloc[-1]) if not valid.empty else None
    If isinstance(series, np.ndarray) :
        Valid = series[~np.isnan(series)]
        Return to_float(valid[-1]) if valid.size > 0 else None
    Return to_float(series)

Def safe_prev(series) :
    If series is None : return None
    If isinstance(series, pd.DataFrame) : series = series.squeeze()
    If isinstance(series, pd.Series) :
        Valid = series.dropna()
        Return to_float(valid.iloc[-2]) if len(valid) > 1 else safe_last(series)
    Return None

Def download_ticker(ticker, start) :
    Try :
        Df = yf.download(ticker, start=start, progress=False)
        If not df.empty :
            Return df
    Except :
        Pass
    Return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
Def load_all_data() :
    Start = datetime.now() – timedelta(days=500)
    Data = {}

    For pos in POSITIONS :
        For t in pos[« tickers »] :
            Df = download_ticker(t, start)
            If not df.empty :
                Data[t] = df
                Break

    For t in [BENCHMARK_TICKER] + EXTRA_TICKERS :
        If t not in data :
            Df = download_ticker(t, start)
            If not df.empty :
                Data[t] = df

    For name, tickers in SENTINELLES.items() :
        For t in tickers :
            If t not in data :
                Df = download_ticker(t, start)
                If not df.empty :
                    Data[t] = df
                    Break

    If « EURUSD=X » not in data :
        Eur = download_ticker(« EURUSD=X », start)
        If not eur.empty :
            Data[« EURUSD=X »] = eur

    Return data

Def compute_sma(series, window) :
    If series is None or len(series) < window : return None
    Return series.rolling(window=window).mean()

Def compute_rsi(series, period=14) :
    If series is None or len(series) < period+1 : return None
    Delta = series.diff()
    Gain = delta.clip(lower=0)
    Loss = -delta.clip(upper=0)
    Avg_gain = gain.rolling(window=period, min_periods=period).mean()
    Avg_loss = loss.rolling(window=period, min_periods=period).mean()
    Avg_loss.replace(0, np.nan, inplace=True)
    Rs = avg_gain / avg_loss
    Return 100 – (100 / (1 + rs))

# ---------- CHARGEMENT ----------
Data = load_all_data()
If not data :
    St.error(« Aucune donnée récupérée. »)
    St.stop()

Eur_usd_rate = safe_last(data[« EURUSD=X »][« Close »]) if « EURUSD=X » in data and not data[« EURUSD=X »].empty else None

Ticker_used = {}
Latest_prices = {}
Prev_prices = {}  # pour les variations journalières
For pos in POSITIONS :
    Used = None
    For t in pos[« tickers »] :
        If t in data and not data[t].empty :
            Used = t
            Break
    Ticker_used[pos[« nom »]] = used
    If used :
        Prix = safe_last(data[used][« Close »])
        If used == « GLD » and eur_usd_rate :
            Prix = prix / eur_usd_rate
        Latest_prices[used] = prix
        Prev_prices[used] = safe_prev(data[used][« Close »])
    Else :
        Latest_prices[pos[« nom »]] = None
        Prev_prices[pos[« nom »]] = None

# ---------- VALEUR DU PORTEFEUILLE ET PERFORMANCES JOURNALIÈRES ----------
Positions_calculees = []
Valeur_totale = 0.0
Valeur_veille = 0.0
For pos in POSITIONS :
    Ticker = ticker_used[pos[« nom »]]
    Prix = latest_prices.get(ticker)
    Prix_veille = prev_prices.get(ticker)
    If prix is None or np.isnan(prix) :
        Positions_calculees.append({« nom » : pos[« nom »], « prix » : None, « valeur » : 0.0, « perf » : None, « var_jour » : None})
    Else :
        Valeur = pos[« parts »] * prix
        Perf = (prix – pos[« prm »]) / pos[« prm »] * 100
        # variation journalière
        If prix_veille is not None and not np.isnan(prix_veille) and prix_veille != 0 :
            Var_jour = (prix – prix_veille) / prix_veille * 100
        Else :
            Var_jour = None
        Positions_calculees.append({« nom » : pos[« nom »], « prix » : prix, « valeur » : valeur, « perf » : perf, « var_jour » : var_jour})
        Valeur_totale += valeur
        If prix_veille is not None and not np.isnan(prix_veille) :
            Valeur_veille += pos[« parts »] * prix_veille
        Else :
            Valeur_veille += valeur  # fallback

Gain_net = valeur_totale – CAPITAL_INITIAL
Perf_totale = (gain_net / CAPITAL_INITIAL) * 100 if CAPITAL_INITIAL != 0 else 0

# Performance du jour
Perf_jour_euro = valeur_totale – valeur_veille
Perf_jour_pct = (perf_jour_euro / valeur_veille * 100) if valeur_veille != 0 else 0.0

# ---------- BENCHMARK CW8 ----------
Perf_world = None
Gap = None
Bench_price = None
Cw8_prev = None
If BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty :
    Cw8_series = data[BENCHMARK_TICKER][« Close »].squeeze()
    Bench_price = safe_last(cw8_series)
    Cw8_prev = safe_prev(cw8_series)
    If bench_price :
        Try :
            Start_val = cw8_series.loc[DATE_DEBUT.strftime(« %Y-%m-%d »)]
            Start_val = to_float(start_val.iloc[0]) if isinstance(start_val, pd.Series) else to_float(start_val)
        Except KeyError :
            Start_val = to_float(cw8_series.iloc[0])
        If start_val and start_val > 0 :
            Perf_world = (bench_price / start_val – 1) * 100
            Gap = perf_totale – perf_world

# Variation journalière du World et du GAP
Perf_world_jour = None
Gap_jour = None
If bench_price and cw8_prev and cw8_prev != 0 :
    Perf_world_jour = (bench_price – cw8_prev) / cw8_prev * 100
    If perf_jour_pct is not None :
        Gap_jour = perf_jour_pct – perf_world_jour

# ---------- PRIX DE RATTRAPAGE ----------
Prix_rattrapage = None
If gap is not None and gap < 0 and ticker_used.get(« Global Hydrogen ») :
    Valeur_cible = CAPITAL_INITIAL * (1 + perf_world/100)
    Diff = valeur_cible – valeur_totale
    Anrj_parts = None
    For pos in POSITIONS :
        If pos[« nom »] == « Global Hydrogen » :
            Anrj_parts = pos[« parts »]
            Break
    If anrj_parts and anrj_parts > 0 :
        Anrj_prix_actuel = safe_last(data[ticker_used[« Global Hydrogen »]][« Close »]) if ticker_used[« Global Hydrogen »] else None
        If anrj_prix_actuel :
            Nouveau_prix = anrj_prix_actuel + (diff / anrj_parts)
            Prix_rattrapage = nouveau_prix
Else :
    If gap is not None and gap >= 0 :
        Prix_rattrapage = « Objectif atteint »

# ---------- INDICATEURS HYDROGÈNE ----------
Anrj_series = None
If « ANRJ.PA » in data and not data[« ANRJ.PA »].empty :
    Anrj_series = data[« ANRJ.PA »][« Close »].squeeze()
Anrj_current = safe_last(anrj_series)
Anrj_sma20 = anrj_sma50 = anrj_rsi = anrj_ath30 = None
If anrj_series is not None and len(anrj_series) >= 20 :
    Anrj_sma20 = safe_last(compute_sma(anrj_series, 20))
    Anrj_sma50 = safe_last(compute_sma(anrj_series, 50))
    Anrj_rsi = safe_last(compute_rsi(anrj_series, 14))
    Ath30_series = anrj_series.rolling(30, min_periods=1).max()
    Anrj_ath30 = safe_last(ath30_series)

# ---------- INDICATEURS EM ASIA ----------
Aasi_series = None
If « AASI.PA » in data and not data[« AASI.PA »].empty :
    Aasi_series = data[« AASI.PA »][« Close »].squeeze()
Aasi_current = safe_last(aasi_series)
Aasi_sma20 = aasi_sma50 = None
If aasi_series is not None and len(aasi_series) >= 20 :
    Aasi_sma20 = safe_last(compute_sma(aasi_series, 20))
    Aasi_sma50 = safe_last(compute_sma(aasi_series, 50))

# ---------- SENTINELLES ----------
Sentinelle_info = {}
For name, tickers in SENTINELLES.items() :
    Prix = sma20 = None
    For t in tickers :
        If t in data and not data[t].empty :
            Ts = data[t][« Close »].squeeze()
            Prix = safe_last(ts)
            If len(ts) >= 20 :
                Sma20 = safe_last(compute_sma(ts, 20))
            Break
    Sentinelle_info[name] = {« prix » : prix, « sma20 » : sma20}

# ---------- MACRO ----------
Us10y = dxy = brent = None
If « ^TNX » in data :
    Raw = safe_last(data[« ^TNX »][« Close »].squeeze())
    Us10y = raw / 10 if raw and raw > 20 else raw
If « DX-Y.NYB » in data :
    Dxy = safe_last(data[« DX-Y.NYB »][« Close »].squeeze())
If « BZ=F » in data :
    Brent = safe_last(data[« BZ=F »][« Close »].squeeze())

Bloom_close = None
If « BE » in data and not data[« BE »].empty :
    Be_series = data[« BE »][« Close »].squeeze()
    Bloom_close = safe_last(be_series)

# ---------- RÈGLES DÉCISIONNELLES ----------
Def evaluate_hydrogen() :
    If anrj_current is None : return « ⚠️ ANRJ manquant », « gray »
    If anrj_current < 706.06 : return « 🚨 STOP-LOSS : COUPURE 50% VERS WORLD », « red »
    If anrj_current > 812 and anrj_rsi and anrj_rsi > 68 : return « 💰 TAKE PROFIT 30% », « green »
    If anrj_ath30 and anrj_current < anrj_ath30 * 0.95 : return « 🔶 ALLÉGEMENT PRÉVENTIF (Protection des gains, -5% ATH 30j) », « orange »
    If anrj_sma20 and anrj_current < anrj_sma20 : return « 🔶 SOUS SMA20 – ARBITRAGE VERS WORLD », « orange »
    If anrj_sma50 and anrj_current > anrj_sma50 : return « ✅ MAINTIEN HYDROGÈNE », « green »
    Return « ℹ️ SURVEILLANCE », « orange »

Def evaluate_em_asia() :
    If aasi_current is None : return « ⚠️ AASI manquant », « gray »
    If aasi_current > 60.35 :
        If aasi_series is not None :
            Highest = aasi_series.rolling(50, min_periods=1).max()
            Highest_val = safe_last(highest)
            If highest_val and aasi_current < highest_val * 0.92 : return « 🎯 TRAILING STOP -8% : ARBITRAGE 50% », « red »
            Else : return « 📈 TRAILING STOP ACTIF », « green »
    If aasi_sma20 and aasi_current < aasi_sma20 : return « 🔶 SOUS SMA20 – SURVEILLANCE RENFORCÉE », « orange »
    If aasi_sma50 and aasi_current > aasi_sma50 : return « ✅ MAINTIEN EM ASIA », « green »
    Return « ℹ️ SURVEILLANCE », « orange »

Def evaluate_sentinelles() :
    Alerts = []
    Tsmc = sentinelle_info.get(« TSMC »)
    If tsmc and tsmc[« prix »] and tsmc[« sma20 »] and tsmc[« prix »] < tsmc[« sma20 »] : alerts.append(« ⚠️ TSMC sous SMA20 »)
    Sam = sentinelle_info.get(« Samsung »)
    If sam and sam[« prix »] and sam[« sma20 »] and sam[« prix »] < sam[« sma20 »] : alerts.append(« ⚠️ Samsung sous SMA20 »)
    Al = sentinelle_info.get(« Air Liquide »)
    If al and al[« prix »] and al[« sma20 »] and al[« prix »] < al[« sma20 »] : alerts.append(« ⚠️ Air Liquide sous SMA20 »)
    If « BE » in data :
        Be_series = data[« BE »][« Close »].squeeze()
        If len(be_series) >= 3 :
            Be_latest = safe_last(be_series)
            Be_2d_ago = safe_last(be_series.iloc[ :-2]) if len(be_series) > 2 else None
            If be_latest and be_2d_ago and (be_latest / be_2d_ago – 1) < -0.03 : alerts.append(« ⚠️ Bloom Energy -3% en 48h »)
    If us10y and us10y > 4.60 : alerts.append(« ⚠️ US10Y > 4.60% »)
    If dxy and dxy > 102 : alerts.append(« ⚠️ DXY > 102 »)
    If alerts : return «  | « .join(alerts), « orange »
    Return « ✅ Sentinelles OK », « green »

Def decision_finale() :
    H_msg, h_col = evaluate_hydrogen()
    A_msg, a_col = evaluate_em_asia()
    S_msg, s_col = evaluate_sentinelles()
    If « red » in [h_col, a_col] :
        Msg = h_msg if h_col== »red » else a_msg
        Return f »🔴 ACTION REQUISE : {msg} », « red »
    If « orange » in [h_col, a_col, s_col] :
        Parties = []
        If h_col== »orange » : parties.append(h_msg)
        If a_col== »orange » : parties.append(a_msg)
        If s_col== »orange » : parties.append(s_msg)
        Return f »🟡 VIGILANCE : {‘ | ‘.join(parties)} », « orange »
    Return « 🟢 MAINTIEN GLOBAL », « green »

Decision_globale, decision_color = decision_finale()

# Score de risque satellite
Valeur_anrj = next((p[« valeur »] for p in positions_calculees if p[« nom »] == « Global Hydrogen »), 0)
Valeur_aasi = next((p[« valeur »] for p in positions_calculees if p[« nom »] == « EM Asia »), 0)
Poids_satellite = (valeur_anrj + valeur_aasi) / valeur_totale * 100 if valeur_totale > 0 else 0
Alerte_risque = poids_satellite > 45

# ---------- HEURE DE PARIS ----------
Now = datetime.now(ZoneInfo(« Europe/Paris »))

# ---------- INTERFACE ----------
St.title(« 🛰️ Cockpit Décisionnel »)
St.caption(f »Données du {now.strftime(‘%d/%m/%Y %H :%M’)} (heure de Paris) »)

# Section Executive
St.markdown(« ### 📊 Executive »)
Col1, col2, col3 = st.columns(3)
Col1.metric(« Valeur totale », f »{valeur_totale :,.2f}€ », delta=f »{perf_jour_euro :+,.2f}€ (auj.) »)
Col2.metric(« Gain net », f »{gain_net :+,.2f}€ »)
Col3.metric(« Performance », f »{perf_totale :+.2f}% », delta=f »{perf_jour_pct :+.2f}% (auj.) »)

If perf_world is not None :
    Col4, col5 = st.columns(2)
    Col4.metric(« Perf. World (CW8) », f »{perf_world :+.2f}% », delta=f »{perf_world_jour :+.2f}% (auj.) » if perf_world_jour is not None else None)
    Col5.metric(« GAP vs World », f »{gap :+.2f}% », delta=f »{gap_jour :+.2f}% (auj.) » if gap_jour is not None else None)

# Détail positions
St.markdown(« #### Positions »)
Cols = st.columns(len(positions_calculees))
For i, p in enumerate(positions_calculees) :
    With cols[i] :
        Prix_str = f »{p[‘prix’] :.2f}€ » if p[‘prix’] is not None else « N/A »
        Perf_str = f »{p[‘perf’] :+.2f}% » if p[‘perf’] is not None else « N/A »
        Var_jour_str = f »{p[‘var_jour’] :+.2f}% auj. » if p[‘var_jour’] is not None else « « 
        St.metric(label=p[‘nom’], value=prix_str, delta=perf_str)
        If var_jour_str :
            St.caption(var_jour_str)

# Feu tricolore
Bg = {« red » : »#dc3545 », »orange » : »#fd7e14 », »green » : »#28a745 »}[decision_color]
St.markdown(f »<div class=’big-verdict’ style=’background-color :{bg} ;’>{decision_globale}</div> », unsafe_allow_html=True)

# Score de risque
St.markdown(« #### ⚖️ Poids Satellites »)
Jauge = poids_satellite / 100
St.progress(min(jauge, 1.0))
St.write(f »ANRJ + EM Asia : **{poids_satellite :.1f}%** du portefeuille »)
If alerte_risque :
    St.warning(« ⚠️ Poids satellites > 45% – Exposition élevée aux thématiques »)

# Détails Hydrogène
St.subheader(« 🔎 Hydrogène (ANRJ) »)
If anrj_current :
    D1,d2,d3,d4 = st.columns(4)
    D1.metric(« ANRJ », f »{anrj_current :.2f}€ »)
    D2.metric(« SMA20 », f »{anrj_sma20 :.2f}€ » if anrj_sma20 else « N/A »)
    D3.metric(« ATH 30j », f »{anrj_ath30 :.2f}€ » if anrj_ath30 else « N/A »)
    D4.metric(« RSI », f »{anrj_rsi :.1f} » if anrj_rsi else « N/A »)
    St.caption(evaluate_hydrogen()[0])
Else :
    St.warning(« ANRJ indisponible »)

# Détails EM Asia
St.subheader(« 🌏 EM Asia (AASI) »)
If aasi_current :
    E1,e2 = st.columns(2)
    E1.metric(« AASI », f »{aasi_current :.2f}€ »)
    E2.metric(« SMA20 », f »{aasi_sma20 :.2f}€ » if aasi_sma20 else « N/A »)
    St.caption(evaluate_em_asia()[0])
Else :
    St.warning(« AASI indisponible »)

# Sentinelles
St.subheader(« 🛰️ Sentinelles »)
S_msg, s_col = evaluate_sentinelles()
St.caption(s_msg)
Sentinel_rows = []
For name, info in sentinelle_info.items() :
    Prix = info[« prix »]
    Sma20 = info[« sma20 »]
    Sentinel_rows.append({« Nom » : name, « Dernier » : f »{prix :.2f} » if prix else « N/A », « SMA20 » : f »{sma20 :.2f} » if sma20 else « N/A »})
If sentinel_rows :
    St.dataframe(pd.DataFrame(sentinel_rows), use_container_width=True, hide_index=True)

# Macro
St.subheader(« 🧭 Macro »)
M1,m2,m3,m4 = st.columns(4)
M1.metric(« US 10Y », f »{us10y :.2f}% » if us10y else « N/A »)
M2.metric(« DXY », f »{dxy :.2f} » if dxy else « N/A »)
M3.metric(« Brent », f »{brent :.2f}$ » if brent else « N/A »)
M4.metric(« Bloom Energy », f »{bloom_close :.2f}$ » if bloom_close else « N/A »)

# Graphique (conservé)
Def compute_historical_value() :
    Start_date = DATE_DEBUT
    Df_combined = None
    For pos in POSITIONS :
        T = ticker_used.get(pos[« nom »])
        If t and t in data :
            Ts = data[t][« Close »].squeeze()
            Ts = ts[ts.index >= start_date]
            If df_combined is None :
                Df_combined = pd.DataFrame(index=ts.index)
            Df_combined[t] = ts
    If df_combined is None or df_combined.empty : return None
    Df_combined = df_combined.ffill()
    Valeur_hist = pd.Series(0.0, index=df_combined.index)
    For pos in POSITIONS :
        T = ticker_used.get(pos[« nom »])
        If t and t in df_combined.columns :
            Prix_series = df_combined[t]
            If t == « GLD » and eur_usd_rate :
                Prix_series = prix_series / eur_usd_rate
            Valeur_hist += pos[« parts »] * prix_series
    Val_init = valeur_hist.iloc[0]
    Return (valeur_hist / val_init) * 100 if val_init != 0 else None

Port_hist = compute_historical_value()
Cw8_hist = None
If BENCHMARK_TICKER in data and not data[BENCHMARK_TICKER].empty :
    Cw8_series = data[BENCHMARK_TICKER][« Close »].squeeze()
    Try :
        Start_idx = cw8_series.index.get_loc(DATE_DEBUT, method=’ffill’)
        Cw8_from_start = cw8_series.iloc[start_idx :]
        If len(cw8_from_start) > 0 :
            Cw8_hist = (cw8_from_start / cw8_from_start.iloc[0]) * 100
    Except :
        Pass

St.subheader(« 📈 Performance Cumulée (base 100) »)
If port_hist is not None and cw8_hist is not None :
    Combined = pd.DataFrame({« Portefeuille » : port_hist, « MSCI World » : cw8_hist}).dropna()
    St.line_chart(combined)
Elif port_hist is not None :
    St.line_chart(port_hist)
Elif cw8_hist is not None :
    St.line_chart(cw8_hist)
Else :
    St.info(« Données insuffisantes pour le graphique. »)

St.markdown(« ---« )
St.caption(« Cockpit Décisionnel · Ne constitue pas un conseil en investissement »)
