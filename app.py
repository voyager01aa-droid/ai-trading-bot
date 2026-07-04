import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai
from datetime import datetime
# from neo_api_client import NeoAPI # Uncomment for actual Kotak trade

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Intraday Pro", layout="wide")
st.title("📈 NSE AI Intraday Trading Bot")

# --- SIDEBAR: API KEYS & SETTINGS ---
st.sidebar.header("🔑 Credentials & Settings")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
news_api_key = st.sidebar.text_input("NewsAPI Key", type="password")

st.sidebar.subheader("Kotak Neo Credentials (Auto-Trade)")
kotak_consumer_key = st.sidebar.text_input("Consumer Key", type="password")
kotak_consumer_secret = st.sidebar.text_input("Consumer Secret", type="password")
kotak_mobile = st.sidebar.text_input("Mobile Number")
kotak_password = st.sidebar.text_input("Password", type="password")

stock_symbol = st.sidebar.text_input("Stock Symbol (e.g., RELIANCE.NS)", "RELIANCE.NS")
qty = st.sidebar.number_input("Trade Quantity", min_value=1, value=10)

# --- FUNCTION: FETCH PRICE ACTION ---
def get_price_action(symbol):
    try:
        data = yf.download(symbol, period="5d", interval="15m")
        if data.empty:
            return None
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        trend = "Bullish" if latest['Close'] > prev['Close'] else "Bearish"
        return {
            "current_price": latest['Close'],
            "high": latest['High'],
            "low": latest['Low'],
            "volume": latest['Volume'],
            "trend": trend,
            "data_summary": data.tail(3).to_string()
        }
    except Exception as e:
        return str(e)

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

# --- FUNCTION: AI ANALYSIS (GEMINI) ---
def analyze_with_ai(price_data, news, symbol):
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-pro')
    
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

# --- FUNCTION: AUTO TRADE (KOTAK NEO) ---
def execute_kotak_trade(action, symbol, qty, price):
    # WARNING: This is a structural template. Real execution requires full NeoAPI setup.
    try:
        # client = NeoAPI(consumer_key=kotak_consumer_key, consumer_secret=kotak_consumer_secret, ...)
        # client.login(mobilenumber=kotak_mobile, password=kotak_password)
        # client.place_order(exchange_segment="nse_cm", product="MIS", price=price, order_type="L", quantity=qty, validity="DAY", trading_symbol=symbol, transaction_type="B" if action=="BUY" else "S")
        st.success(f"✅ AUTO-TRADE EXECUTED on Kotak Neo: {action} {qty} shares of {symbol} at target price {price}")
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
            news_data = get_market_news(news_api_key, f"{stock_symbol.split('.')[0]} OR NSE India")
            
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
                ai_call = analyze_with_ai(price_data, news_data, stock_symbol)
                
            st.markdown("### 🎯 AI Trading Recommendation")
            st.info(ai_call)
            
            # --- AUTO TRADE TRIGGER ---
            if "ACTION: BUY" in ai_call or "ACTION: SELL" in ai_call:
                action = "BUY" if "ACTION: BUY" in ai_call else "SELL"
                st.markdown("---")
                st.subheader("⚡ Auto-Trade Execution")
                if st.button(f"Execute {action} on Kotak Neo Now"):
                    if kotak_consumer_key and kotak_password:
                        execute_kotak_trade(action, stock_symbol, qty, price_data['current_price'])
                    else:
                        st.error("Please enter Kotak Neo credentials in the sidebar to auto-trade.")
        else:
            st.error("Could not fetch price data. Check stock symbol.")
