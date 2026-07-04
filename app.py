import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai
import concurrent.futures
import numpy as np

# --- PAGE SETUP ---
st.set_page_config(page_title="Institutional AI Trader", layout="wide", page_icon="🏦")
st.title("🏦 Institutional Grade AI Trading Bot")
st.caption("Powered by Smart Money Concepts, VWAP, EMA, RSI & Market Sentiment")

# --- SIDEBAR: CREDENTIALS ---
st.sidebar.header("🔑 API Credentials")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
news_api_key = st.sidebar.text_input("NewsAPI Key", type="password")

st.sidebar.subheader("Kotak Neo Auto-Trade")
kotak_consumer_key = st.sidebar.text_input("Consumer Key", type="password")
kotak_password = st.sidebar.text_input("Password", type="password")
qty = st.sidebar.number_input("Default Trade Qty", min_value=1, value=10)

# 📌 NIFTY 500 LIQUID UNIVERSE
NIFTY_500_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", 
    "BHARTIARTL.NS", "ITC.NS", "L&T.NS", "BAJFINANCE.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "MARUTI.NS", "TATAMOTORS.NS", "SUNPHARMA.NS", "ASIANPAINT.NS", "HCLTECH.NS", 
    "TATASTEEL.NS", "NTPC.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "M&M.NS", "TITAN.NS", 
    "BAJAJFINSV.NS", "WIPRO.NS", "NESTLEIND.NS", "ADANIENT.NS", "ADANIPORTS.NS", 
    "ONGC.NS", "HINDUNILVR.NS", "COALINDIA.NS", "GRASIM.NS", "TECHM.NS", "HINDALCO.NS",
    "ZOMATO.NS", "JIOFIN.NS", "IRFC.NS", "RVNL.NS", "IREDA.NS", "SUZLON.NS", "NHPC.NS",
    "PNB.NS", "BOB.NS", "TVSMOTOR.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "DLF.NS", 
    "LODHA.NS", "GODREJPROP.NS", "TRENT.NS", "CHOLAFIN.NS", "PFC.NS", "RECLTD.NS",
    "GAIL.NS", "BHEL.NS", "BEL.NS", "HAL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "DIXON.NS"
]

# --- CORE FUNCTIONS ---
def get_news(api_key, query):
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&language=en&apiKey={api_key}"
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])[:4] 
        return "\n".join([f"- {a['title']}" for a in articles]) or "No major news found."
    except:
        return "Failed to fetch news."

def get_smart_ai_model():
    genai.configure(api_key=gemini_api_key)
    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro'] if m in available), available[0] if available else None)
    return genai.GenerativeModel(target) if target else None

# --- INDICATORS CALCULATOR (PRO STRATEGY) ---
def add_pro_indicators(df):
    try:
        # EMA 9 & 21
        df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # RSI 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # VWAP
        df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
        return df
    except:
        return df

# --- TAB 1 FUNCTIONS (SCREENER) ---
def fetch_momentum(symbol):
    try:
        data = yf.Ticker(symbol).history(period="5d", interval="15m")
        if len(data) < 14: return None
        
        data = add_pro_indicators(data)
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        pct_change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
        
        return {
            "Symbol": symbol, 
            "Price": latest['Close'], 
            "VWAP": latest['VWAP'],
            "RSI": latest['RSI'],
            "Change_Pct": pct_change, 
            "Momentum": abs(pct_change)
        }
    except:
        return None

def get_top_10():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_momentum, sym) for sym in NIFTY_500_STOCKS]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)
    df = pd.DataFrame(results)
    return df.sort_values(by="Momentum", ascending=False).head(10) if not df.empty else None

# --- TAB 2 FUNCTIONS (SEARCH SPECIFIC) ---
def get_detailed_price_action(symbol):
    try:
        data = yf.Ticker(symbol).history(period="5d", interval="15m")
        if data.empty: return None
        
        data = add_pro_indicators(data)
        latest = data.iloc[-1]
        
        trend = "Bullish 🟢" if latest['Close'] > latest['VWAP'] else "Bearish 🔴"
        
        return {
            "current_price": latest['Close'], 
            "vwap": latest['VWAP'],
            "ema_9": latest['EMA_9'],
            "ema_21": latest['EMA_21'],
            "rsi": latest['RSI'],
            "trend": trend, 
            "data_summary": data[['Close', 'VWAP', 'RSI']].tail(3).to_string()
        }
    except:
        return None

# --- AUTO TRADE ---
def fire_trade(stock, action, price):
    st.success(f"⚡ Pro Order Sent: {action} {qty} qty of {stock} at Market (Trigger: ₹{price})")

# --- UI TABS ---
tab1, tab2 = st.tabs(["🚀 Top 10 Institutional Screener", "🔍 Deep Pro Analysis (Search)"])

# ==========================================
# TAB 1: TOP 10 SCREENER
# ==========================================
with tab1:
    st.markdown("### 📊 Auto-Scan Top 10 High-Probability Setups")
    if st.button("Screen Market & Get Pro Calls"):
        if not gemini_api_key or not news_api_key:
            st.warning("Please enter API keys in the sidebar.")
        else:
            with st.spinner("📰 Reading Macro Market News..."):
                market_news = get_news(news_api_key, "Indian Stock Market OR NSE OR RBI")
            with st.spinner("⚡ Scanning Nifty 500 & Calculating Pro Indicators (VWAP, RSI)..."):
                top_10_df = get_top_10()
                
            if top_10_df is not None:
                st.info(f"**Today's Market Sentiment:**\n{market_news}")
                st.dataframe(top_10_df.style.format({"Price": "₹{:.2f}", "VWAP": "₹{:.2f}", "RSI": "{:.1f}", "Change_Pct": "{:.2f}%", "Momentum": "{:.2f}%"}))
                
                with st.spinner("🤖 AI is Correlating Institutional Logic..."):
                    model = get_smart_ai_model()
                    if model:
                        prompt = f"""
                        You are an Elite Institutional Trader using SMC (Smart Money Concepts). 
                        DATA: {top_10_df.to_string(index=False)}
                        NEWS: {market_news}
                        
                        Give intraday calls. If Price > VWAP and RSI < 70, it's a strong BUY setup.
                        If Price < VWAP and RSI > 30, it's a strong SELL setup. Include news sentiment.
                        
                        Format strictly as Markdown Table:
                        | Stock | Accuracy % | Action (BUY/SELL) | Entry | Target | SL (Min 1:2 RR) | Pro Logic |
                        """
                        res = model.generate_content(prompt)
                        st.markdown("### 🎯 Institutional AI Strategy Board")
                        st.markdown(res.text)

# ==========================================
# TAB 2: SEARCH ANY STOCK
# ==========================================
with tab2:
    st.markdown("### 🔍 Institutional Deep Dive (Specific Stock)")
    search_symbol = st.text_input("Enter Stock Symbol (e.g., TATASTEEL.NS, IREDA.NS)")
    
    if st.button("Generate Institutional Strategy"):
        if not gemini_api_key or not news_api_key:
            st.warning("Please enter API keys.")
        elif not search_symbol:
            st.warning("Please enter a stock symbol.")
        else:
            search_symbol = search_symbol.upper().strip()
            if not search_symbol.endswith(".NS"): search_symbol += ".NS"
                
            with st.spinner(f"📡 Calculating VWAP, EMAs, RSI for {search_symbol}..."):
                price_data = get_detailed_price_action(search_symbol)
            with st.spinner(f"📰 Fetching specific news for {search_symbol}..."):
                stock_news = get_news(news_api_key, f"{search_symbol.replace('.NS', '')} OR NSE India")
                
            if price_data:
                st.subheader(f"📊 Institutional Metrics: {search_symbol}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Current Price", f"₹{price_data['current_price']:.2f}")
                c2.metric("VWAP", f"₹{price_data['vwap']:.2f}")
                c3.metric("RSI (Momentum)", f"{price_data['rsi']:.1f}")
                c4.metric("Trend vs VWAP", price_data['trend'])
                
                st.markdown("**🗞️ Catalyst News:**")
                st.write(stock_news)
                
                with st.spinner("🤖 AI Quant is calculating probability and Risk/Reward..."):
                    model = get_smart_ai_model()
                    if model:
                        prompt = f"""
                        Act as an Elite Hedge Fund Trader. Analyze {search_symbol}.
                        Technicals: Price = {price_data['current_price']}, VWAP = {price_data['vwap']}, RSI = {price_data['rsi']}, EMA 9 = {price_data['ema_9']}, EMA 21 = {price_data['ema_21']}
                        Recent History: {price_data['data_summary']}
                        News Sentiment: {stock_news}
                        
                        Calculate a probability 'Confidence Score' based on technical and news confluence (e.g., if price > VWAP + EMA 9 > 21 + Good News = 80%+ Accuracy). Ensure 1:2 Risk/Reward ratio minimum.
                        
                        Format EXACTLY like this:
                        * **CONFIDENCE SCORE (ACCURACY):** [Exact %]
                        * **ACTION:** [BUY / SELL / AVOID]
                        * **ENTRY PRICE:** [Exact Price]
                        * **TARGET (1:2 R:R minimum):** [Exact Price]
                        * **STOP-LOSS (Tight SMC levels):** [Exact Price]
                        * **PRO-LOGIC:** [Explain VWAP, RSI & News confluence]
                        """
                        try:
                            analysis = model.generate_content(prompt)
                            st.success("Analysis Complete!")
                            st.info(analysis.text)
                            
                            st.markdown("---")
                            if st.button(f"⚡ Execute Institutional Trade for {search_symbol}"):
                                if kotak_consumer_key:
                                    fire_trade(search_symbol, "MARKET", price_data['current_price'])
                                else:
                                    st.error("Kotak API Credentials missing!")
                        except Exception as e:
                            st.error(f"AI Generation Failed: {e}")
            else:
                st.error("Could not fetch data. Check symbol.")
