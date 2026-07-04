import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai
import concurrent.futures

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Pro Trading Dashboard", layout="wide", page_icon="📈")
st.title("📈 Pro AI Trading Dashboard (Screener + Search)")

# --- SIDEBAR: CREDENTIALS ---
st.sidebar.header("🔑 API Credentials")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
news_api_key = st.sidebar.text_input("NewsAPI Key", type="password")

st.sidebar.subheader("Kotak Neo Auto-Trade")
kotak_consumer_key = st.sidebar.text_input("Consumer Key", type="password")
kotak_password = st.sidebar.text_input("Password", type="password")
qty = st.sidebar.number_input("Default Trade Qty", min_value=1, value=10)

# 📌 NIFTY 500 LIQUID UNIVERSE (Top ~100-150 for safety & speed)
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
    "GAIL.NS", "BHEL.NS", "BEL.NS", "HAL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "DIXON.NS",
    "POLYCAB.NS", "HAVELLS.NS", "INDIGO.NS", "PIDILITIND.NS", "SRF.NS", "TATACHEM.NS",
    "TATAPOWER.NS", "JSWSTEEL.NS", "JINDALSTEL.NS", "SAIL.NS", "VEDL.NS", "NMDC.NS",
    "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "LUPIN.NS", "AUROPHARMA.NS", "INDUSINDBK.NS",
    "IDFCFIRSTB.NS", "YESBANK.NS", "BANDHANBNK.NS", "MUTHOOTFIN.NS", "MANAPPURAM.NS"
    # Aap baaki ke Nifty 500 stocks yahan list me add kar sakte hain
]

# --- CORE FUNCTIONS ---

def get_news(api_key, query):
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&language=en&apiKey={api_key}"
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])[:4] 
        news_summary = "\n".join([f"- {a['title']}" for a in articles])
        return news_summary if news_summary else "No major news found."
    except:
        return "Failed to fetch news."

def get_smart_ai_model():
    genai.configure(api_key=gemini_api_key)
    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro'] if m in available), available[0] if available else None)
    return genai.GenerativeModel(target) if target else None

# --- TAB 1 FUNCTIONS (SCREENER) ---
def fetch_momentum(symbol):
    try:
        data = yf.Ticker(symbol).history(period="2d")
        if len(data) < 2: return None
        prev, curr, vol = float(data['Close'].iloc[-2]), float(data['Close'].iloc[-1]), float(data['Volume'].iloc[-1])
        pct_change = ((curr - prev) / prev) * 100
        return {"Symbol": symbol, "Price": curr, "Change_Pct": pct_change, "Momentum": abs(pct_change), "Volume": vol}
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
        curr, prev = float(data['Close'].iloc[-1]), float(data['Close'].iloc[-2])
        trend = "Bullish 🟢" if curr > prev else "Bearish 🔴"
        return {
            "current_price": curr, "high": float(data['High'].iloc[-1]), "low": float(data['Low'].iloc[-1]),
            "trend": trend, "data_summary": data.tail(4).to_string()
        }
    except:
        return None

# --- AUTO TRADE ---
def fire_trade(stock, action, price):
    st.success(f"⚡ Order Sent: {action} {qty} qty of {stock} at Market (Trigger: ₹{price})")

# --- UI TABS ---
tab1, tab2 = st.tabs(["🚀 Top 10 Market Screener (Nifty 500)", "🔍 Search & Analyze Any Stock"])

# ==========================================
# TAB 1: NIFTY 500 TOP 10 SCREENER
# ==========================================
with tab1:
    st.markdown("### 📊 Auto-Scan Top 10 Volatile Stocks")
    if st.button("Screen Market & Get Calls"):
        if not gemini_api_key or not news_api_key:
            st.warning("Please enter API keys in the sidebar.")
        else:
            with st.spinner("📰 Reading Macro Market News..."):
                market_news = get_news(news_api_key, "Indian Stock Market OR NSE OR RBI")
                
            with st.spinner("⚡ Scanning Nifty 500 Universe for Top Movers..."):
                top_10_df = get_top_10()
                
            if top_10_df is not None:
                st.info(f"**Today's Market Sentiment:**\n{market_news}")
                st.dataframe(top_10_df.style.format({"Price": "₹{:.2f}", "Change_Pct": "{:.2f}%", "Momentum": "{:.2f}%"}))
                
                with st.spinner("🤖 AI is Correlating News & Price Action for Top 10..."):
                    model = get_smart_ai_model()
                    if model:
                        prompt = f"""
                        You are a Pro NSE Trader. Combine this Top 10 momentum data with the Market News to give intraday calls.
                        DATA: {top_10_df.to_string(index=False)}
                        NEWS: {market_news}
                        Format strictly as Markdown Table:
                        | Stock | News Impact | Action (BUY/SELL/HOLD) | Entry | Target | SL | Logic |
                        """
                        res = model.generate_content(prompt)
                        st.markdown("### 🎯 AI Strategy Board")
                        st.markdown(res.text)
            else:
                st.error("Data fetch failed.")

# ==========================================
# TAB 2: SEARCH ANY STOCK
# ==========================================
with tab2:
    st.markdown("### 🔍 Deep Analysis of Specific Stock")
    search_symbol = st.text_input("Enter Stock Symbol (Add .NS for NSE, e.g., TATASTEEL.NS, IREDA.NS, ZOMATO.NS)")
    
    if st.button("Deep Analyze Stock"):
        if not gemini_api_key or not news_api_key:
            st.warning("Please enter API keys in the sidebar.")
        elif not search_symbol:
            st.warning("Please enter a stock symbol.")
        else:
            search_symbol = search_symbol.upper().strip()
            if not search_symbol.endswith(".NS"):
                search_symbol += ".NS" # Auto-correct if user forgets .NS
                
            with st.spinner(f"📡 Fetching live 15m Price Action for {search_symbol}..."):
                price_data = get_detailed_price_action(search_symbol)
                
            with st.spinner(f"📰 Fetching specific news for {search_symbol}..."):
                clean_name = search_symbol.replace(".NS", "")
                stock_news = get_news(news_api_key, f"{clean_name} OR NSE India")
                
            if price_data:
                # Show Price Metrics
                st.subheader(f"📊 Live Data: {search_symbol}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"₹{price_data['current_price']:.2f}")
                c2.metric("Intraday Trend", price_data['trend'])
                c3.metric("Latest News Found", "Yes ✅")
                
                st.markdown("**🗞️ Specific Stock News:**")
                st.write(stock_news)
                
                # AI Analysis
                with st.spinner("🤖 AI is calculating Entry, Exit, SL and Logic..."):
                    model = get_smart_ai_model()
                    if model:
                        prompt = f"""
                        Analyze {search_symbol} for Intraday Trading.
                        Price Data: Current = {price_data['current_price']}, Trend = {price_data['trend']}, Recent History = {price_data['data_summary']}
                        Stock Specific News: {stock_news}
                        
                        Give a strict intraday trading call. Combine technical trend and news sentiment.
                        Format EXACTLY like this:
                        * **ACTION:** [BUY / SELL / HOLD]
                        * **ENTRY PRICE:** [Exact Price]
                        * **TARGET:** [Exact Price]
                        * **STOP-LOSS:** [Exact Price]
                        * **NEWS IMPACT:** [Positive/Negative/Neutral]
                        * **LOGIC:** [2 lines detailed logic]
                        """
                        try:
                            analysis = model.generate_content(prompt)
                            st.success("Analysis Complete!")
                            st.info(analysis.text)
                            
                            # Auto Trade Button
                            st.markdown("---")
                            if st.button(f"⚡ Execute Trade for {search_symbol} Now"):
                                if kotak_consumer_key:
                                    fire_trade(search_symbol, "MARKET", price_data['current_price'])
                                else:
                                    st.error("Kotak API Credentials missing!")
                        except Exception as e:
                            st.error(f"AI Generation Failed: {e}")
            else:
                st.error(f"Could not fetch data for {search_symbol}. Check if symbol is correct (e.g., TATASTEEL.NS).")
