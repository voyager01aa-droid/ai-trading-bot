import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import google.generativeai as genai
import concurrent.futures

# --- PAGE SETUP ---
st.set_page_config(page_title="Nifty Top 10 AI Screener", layout="wide")
st.title("🚀 NSE Top 10 'Big Profit' Screener & AI Bot")

# --- SIDEBAR: CREDENTIALS ---
st.sidebar.header("🔑 API Credentials")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
news_api_key = st.sidebar.text_input("NewsAPI Key", type="password")

st.sidebar.subheader("Kotak Neo Auto-Trade")
kotak_consumer_key = st.sidebar.text_input("Consumer Key", type="password")
kotak_password = st.sidebar.text_input("Password", type="password")
qty = st.sidebar.number_input("Default Trade Quantity", min_value=1, value=10)

# 📌 NIFTY UNIVERSE (Sample 50 Highly Liquid F&O Stocks to prevent crash)
# Note: You can expand this list to 500, but 50-100 is best for free Streamlit speed.
NIFTY_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", 
    "BHARTIARTL.NS", "ITC.NS", "L&T.NS", "BAJFINANCE.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "MARUTI.NS", "TATAMOTORS.NS", "SUNPHARMA.NS", "ASIANPAINT.NS", "HCLTECH.NS", 
    "TATASTEEL.NS", "NTPC.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "M&M.NS", "TITAN.NS", 
    "BAJAJFINSV.NS", "WIPRO.NS", "NESTLEIND.NS", "ADANIENT.NS", "ADANIPORTS.NS", 
    "ONGC.NS", "HINDUNILVR.NS", "COALINDIA.NS", "GRASIM.NS", "TECHM.NS", "HINDALCO.NS", 
    "CIPLA.NS", "DRREDDY.NS", "INDUSINDBK.NS", "TATACONSUM.NS", "APOLLOHOSP.NS", 
    "BAJAJ-AUTO.NS", "BRITANNIA.NS", "EICHERMOT.NS", "DIVISLAB.NS", "HEROMOTOCO.NS", 
    "LTIM.NS", "BPCL.NS", "UPL.NS", "TRENT.NS", "BEL.NS", "HAL.NS"
]

# --- FUNCTION: BATCH SCREENING (Find Top 10 Movers) ---
def fetch_single_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="2d")
        if len(data) < 2: return None
        
        prev_close = float(data['Close'].iloc[-2])
        curr_price = float(data['Close'].iloc[-1])
        vol = float(data['Volume'].iloc[-1])
        
        # Calculate Absolute Momentum (Gainers or Losers both give opportunities)
        pct_change = ((curr_price - prev_close) / prev_close) * 100
        abs_change = abs(pct_change)
        
        return {
            "Symbol": symbol,
            "Price": curr_price,
            "Change_Pct": pct_change,
            "Abs_Momentum": abs_change,
            "Volume": vol
        }
    except:
        return None

def get_top_10_stocks():
    st.info("Fetching real-time data for market screening... (Takes ~10-15 seconds)")
    results = []
    # Using parallel processing for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single_stock, sym) for sym in NIFTY_STOCKS]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
            
    df = pd.DataFrame(results)
    if df.empty: return None
    
    # Sort by highest momentum (volatility) and pick Top 10
    top_10 = df.sort_values(by="Abs_Momentum", ascending=False).head(10)
    return top_10

# --- FUNCTION: SMART AI ANALYSIS (BULK) ---
def analyze_top_10_with_ai(top_10_data):
    genai.configure(api_key=gemini_api_key)
    
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_model = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro'] if m in available_models), available_models[0] if available_models else None)
    
    if not target_model: return "Error: No AI model available."

    model = genai.GenerativeModel(target_model)
    
    # Send all 10 stocks data as a single prompt to save API limits
    data_string = top_10_data.to_string(index=False)
    
    prompt = f"""
    You are a Pro NSE Intraday Trader. I have filtered the Top 10 most volatile stocks in the Indian market today based on momentum.
    
    Here is their current data:
    {data_string}
    
    Analyze this data and provide a strict intraday trading plan for EACH of these 10 stocks. 
    Format your output strictly as a Markdown Table with the following columns:
    | Stock Symbol | Trend | Action (BUY/SELL/HOLD) | Entry Price | Target Price | Stop-Loss | Logic (1 Short Sentence) |
    
    Ensure targets and stop-losses make mathematical sense based on the current price. Be precise.
    """
    
    response = model.generate_content(prompt)
    return response.text

# --- FUNCTION: AUTO TRADE PLACEHOLDER ---
def bulk_auto_trade(stock, action, price):
    # Future integration for Kotak Neo REST API
    st.success(f"⚡ Order Sent: {action} {qty} qty of {stock} at ₹{price}")

# --- MAIN APP UI ---
if st.button("🚀 Screen Market & Generate Top 10 Calls"):
    if not gemini_api_key:
        st.warning("Please enter your Gemini API Key in the sidebar.")
    else:
        with st.spinner("Step 1: Scanning Market for Top 10 Momentum Stocks..."):
            top_10_df = get_top_10_stocks()
            
        if top_10_df is not None:
            st.subheader("📊 Step 1 Complete: Top 10 Market Movers Filtered")
            st.dataframe(top_10_df.style.format({"Price": "₹{:.2f}", "Change_Pct": "{:.2f}%", "Abs_Momentum": "{:.2f}%"}))
            
            with st.spinner(f"Step 2: AI is calculating Entry, Exit, and Stop-Loss for these 10 stocks..."):
                try:
                    ai_recommendations = analyze_top_10_with_ai(top_10_df)
                    st.markdown("### 🎯 AI Trading Strategy (Top 10)")
                    st.markdown(ai_recommendations)
                    
                    st.markdown("---")
                    st.subheader("⚡ 1-Click Auto-Trade Execution")
                    st.info("Since we have 10 stocks, you can execute them individually below based on the AI table above.")
                    
                    # Create execution buttons for the top 10 stocks
                    cols = st.columns(3)
                    for i, row in top_10_df.iterrows():
                        col = cols[i % 3]
                        sym = row['Symbol']
                        prc = row['Price']
                        if col.button(f"Trade {sym} @ ₹{prc:.2f}"):
                            if kotak_consumer_key and kotak_password:
                                bulk_auto_trade(sym, "MARKET", prc)
                            else:
                                st.error("Kotak Credentials missing!")
                except Exception as e:
                    st.error(f"AI Generation Failed: {e}")
        else:
            st.error("Failed to fetch market data. Check your internet or market timings.")
