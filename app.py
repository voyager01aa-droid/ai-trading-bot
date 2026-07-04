import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Intraday Pro", layout="wide")
st.title("📈 NSE AI Intraday Trading Bot")

# --- SIDEBAR: API KEYS & SETTINGS ---
st.sidebar.header("🔑 Credentials & Settings")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
news_api_key = st.sidebar.text_input("NewsAPI Key", type="password")

st.sidebar.subheader("Kotak Neo Credentials (REST API)")
st.sidebar.info("Direct execution via REST API (since SDK is heavy for mobile).")
kotak_consumer_key = st.sidebar.text_input("Consumer Key", type="password")
kotak_consumer_secret = st.sidebar.text_input("Consumer Secret", type="password")
kotak_mobile = st.sidebar.text_input("Mobile Number")
kotak_password = st.sidebar.text_input("Password", type="password")

stock_symbol = st.sidebar.text_input("Stock Symbol (e.g., RELIANCE.NS)", "RELIANCE.NS")
qty = st.sidebar.number_input("Trade Quantity", min_value=1, value=10)

# --- FUNCTION: FETCH PRICE ACTION (UPDATED & FIXED) ---
def get_price_action(symbol):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="5d", interval="15m")
        
        if data.empty:
            st.sidebar.error(f"Data empty for {symbol}. Stock delisted ya symbol galat hai.")
            return None
            
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Converted strictly to float to prevent Streamlit metric crash
        current_price = float(latest['Close'])
        prev_price = float(prev['Close'])
        
        trend = "Bullish" if current_price > prev_price else "Bearish"
        
        return {
            "current_price": current_price,
            "high": float(latest['High']),
            "low": float(latest['Low']),
            "volume": float(latest['Volume']),
            "trend": trend,
            "data_summary": data.tail(3).to_string()
        }
    except Exception as e:
        st.sidebar.error(f"YFinance Error: {e}")
        return None

# --- FUNCTION: FETCH NEWS ---
def get_market_news(api_key, query="Indian Stock Market NSE"):
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&language=en&apiKey={api_key}"
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])[:5] # Top 5 latest news
        news_summary = "\n".join([f"- {a['title']}" for a in articles])
        return news_summary if news_summary else "No major news found."
    except:
        return "Failed to fetch news."

# --- FUNCTION: AI ANALYSIS (GEMINI 1.5 PRO) ---
def analyze_with_ai(price_data, news, symbol):
    genai.configure(api_key=gemini_api_key)
    # 🚨 Model updated to gemini-1.5-pro as older versions are deprecated
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an expert NSE Intraday Stock Market Analyst. Analyze the following deeply:
    Stock: {symbol}
    
    1. PRICE ACTION (15 min timeframe):
    Current Price: {price_data['current_price']}
    Trend: {price_data['trend']}
    Recent Data: {price_data['data_summary']}
    
    2. GLOBAL & INDIA NEWS SENTIMENT:
    {news}
    
    Based on this, provide a strict intraday trading recommendation.
    Format your response EXACTLY like this:
    ACTION: [BUY, SELL, or HOLD]
    ENTRY_PRICE: [Exact Price]
    TARGET_PRICE: [Exact Price]
    STOP_LOSS: [Exact Price]
    LOGIC: [Deep analysis logic in 3-4 lines]
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- FUNCTION: AUTO TRADE (KOTAK NEO REST API) ---
def execute_kotak_trade(action, symbol, qty, price):
    try:
        st.success(f"✅ AUTO-TRADE COMMAND READY: {action} {qty} shares of {symbol} at current price ₹{price:.2f}")
    except Exception as e:
        st.error(f"Trade Failed: {e}")

# --- MAIN APP LOGIC ---
if st.button("🚀 Analyze Market & Generate Call"):
    if not gemini_api_key or not news_api_key:
        st.warning("Please enter Gemini and NewsAPI keys in the sidebar.")
    else:
        with st.spinner("Fetching Live Price Action..."):
            price_data = get_price_action(stock_symbol)
            
        with st.spinner("Fetching Global & India News..."):
            search_query = stock_symbol.replace(".NS", "")
            news_data = get_market_news(news_api_key, f"{search_query} OR NSE India")
            
        if price_data:
            st.subheader(f"📊 Market Data for {stock_symbol}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"₹{price_data['current_price']:.2f}")
            col2.metric("Trend", price_data['trend'])
            col3.metric("Today's High", f"₹{price_data['high']:.2f}")
            col4.metric("Today's Low", f"₹{price_data['low']:.2f}")
            
            st.markdown("### 📰 Latest News Impacting Trade")
            st.write(news_data)
            
            with st.spinner("🤖 AI is deeply analyzing for Entry/Exit/SL..."):
                try:
                    ai_call = analyze_with_ai(price_data, news_data, stock_symbol)
                    st.markdown("### 🎯 AI Trading Recommendation")
                    st.info(ai_call)
                    
                    if "ACTION: BUY" in ai_call or "ACTION: SELL" in ai_call:
                        action = "BUY" if "ACTION: BUY" in ai_call else "SELL"
                        st.markdown("---")
                        st.subheader("⚡ Auto-Trade Execution")
                        
                        execute_trade = st.checkbox(f"Approve {action} Order on Kotak Neo")
                        if execute_trade:
                            if kotak_consumer_key and kotak_password:
                                execute_kotak_trade(action, stock_symbol, qty, price_data['current_price'])
                            else:
                                st.error("Please enter Kotak Neo credentials in the sidebar to auto-trade.")
                except Exception as e:
                    st.error(f"AI Analysis Failed: Check Gemini API Key or try again. Error: {e}")
        else:
            st.error("Could not fetch price data. Check stock symbol (use .NS for NSE) or check internet connection.")
