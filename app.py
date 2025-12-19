import streamlit as st
import pandas as pd
from google import genai
import plotly.express as px
import os
import json
import base64
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Smart Cashflow", 
    page_icon="💸",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- SIDEBAR: APPEARANCE & CONFIG ---
with st.sidebar:
    st.title("⚙️ Settings")
    
    # --- 1. APPEARANCE SETTINGS ---
    with st.expander("🎨 Appearance", expanded=True):
        st.caption("Background Theme")
        bg_mode = st.selectbox("Mode", ["Default (Clean)", "Midnight Blue", "Sunset", "Solid Color", "Custom Image"])
        
        # Background Logic
        bg_css = "background-color: #f8fafc;" # Default
        if bg_mode == "Midnight Blue":
            bg_css = "background: linear-gradient(to right, #0f2027, #203a43, #2c5364);"
        elif bg_mode == "Sunset":
            bg_css = "background: linear-gradient(to right, #ff9966, #ff5e62);"
        elif bg_mode == "Solid Color":
            custom_bg_color = st.color_picker("Pick Color", "#f8fafc")
            bg_css = f"background-color: {custom_bg_color};"
        elif bg_mode == "Custom Image":
            bg_file = st.file_uploader("Upload BG", type=["png", "jpg", "jpeg"])
            if bg_file:
                try:
                    b64 = base64.b64encode(bg_file.getvalue()).decode()
                    bg_css = f'background-image: url("data:image/png;base64,{b64}"); background-size: cover; background-repeat: no-repeat;'
                except: st.error("Image Error")

        st.caption("Typography")
        font_name = st.selectbox("Font Family", ["Inter", "Roboto", "Poppins", "Lato", "Montserrat", "Open Sans"])
        font_size = st.slider("Base Size (px)", 12, 20, 16)
        text_color = st.color_picker("Text Color", "#0f172a")

    # --- DYNAMIC CSS INJECTION (FIXED FONT LOADING) ---
    # Fix: Google Fonts needs spaces replaced with '+' (e.g. Open Sans -> Open+Sans)
    font_url_name = font_name.replace(" ", "+")
    
    st.markdown(f"""
    <style>
        /* DYNAMIC FONT IMPORT */
        @import url('https://fonts.googleapis.com/css2?family={font_url_name}:wght@400;600;700&display=swap');

        /* ROOT STYLES - Force Override */
        html, body, [class*="css"], .stMarkdown, .stText {{
            font-family: '{font_name}', sans-serif !important;
            font-size: {font_size}px !important;
            color: {text_color} !important;
        }}
        
        /* BACKGROUND */
        .stApp {{
            {bg_css}
            background-attachment: fixed;
        }}

        /* CARD UI (GLASSMORPHISM) */
        .stContainer {{
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
            margin-bottom: 24px;
        }}

        /* HEADERS */
        h1, h2, h3, h4 {{
            color: {text_color} !important;
            font-family: '{font_name}', sans-serif !important;
        }}

        /* INPUTS */
        .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {{
            border-radius: 8px; border: 1px solid #cbd5e1; color: #334155; font-family: '{font_name}', sans-serif;
        }}

        /* BUTTONS */
        .stButton>button {{
            width: 100%; border-radius: 10px; font-weight: 600; border: none; padding: 0.6rem 1rem;
            background-color: #ffffff; color: #0f172a; border: 1px solid #e2e8f0;
            transition: all 0.2s;
            font-family: '{font_name}', sans-serif;
        }}
        .stButton>button:hover {{ background-color: #f1f5f9; }}
        
        /* PRIMARY BUTTONS */
        div[data-testid="stVerticalBlock"] > div > div > div > div > button[kind="primary"] {{
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: white !important; border: none;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
        }}

        /* METRICS */
        [data-testid="stMetricValue"] {{ font-weight: 700; color: {text_color} !important; font-family: '{font_name}', sans-serif; }}
        [data-testid="stMetricLabel"] {{ font-weight: 600; opacity: 0.7; font-family: '{font_name}', sans-serif; }}

        /* BADGES */
        .total-badge {{
            padding: 8px 12px; border-radius: 8px; font-weight: 600; font-size: 0.9rem;
            display: inline-block; margin-top: 10px; width: 100%; text-align: center;
            font-family: '{font_name}', sans-serif;
        }}
        .badge-green {{ background-color: #dcfce7; color: #166534 !important; border: 1px solid #bbf7d0; }}
        .badge-red {{ background-color: #fee2e2; color: #991b1b !important; border: 1px solid #fecaca; }}
        .badge-blue {{ background-color: #dbeafe; color: #1e40af !important; border: 1px solid #bfdbfe; }}

        /* AI BOX */
        .ai-box {{
            background-color: #0f172a; border-radius: 12px; padding: 20px;
            color: #e2e8f0 !important; border-left: 4px solid #6366f1;
        }}
        .ai-box h3 {{ color: #e2e8f0 !important; }} 
        
        /* TABLE */
        [data-testid="stDataEditor"] {{ border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }}
        
        /* REMOVE TOP PADDING */
        .block-container {{ padding-top: 2rem; }}
    </style>
    """, unsafe_allow_html=True)

    st.divider()
    
    # --- 2. CONFIG ---
    st.header("⚙️ Configuration")
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key: api_key = st.text_input("Enter Gemini API Key", type="password")
    else: st.success("Gemini Connected 🧠")
    
    if "GCP_CREDENTIALS" in st.secrets: 
        st.success("Cloud DB Active ☁️")
        if "SHEET_URL" in st.secrets:
            st.link_button("📂 View Database", st.secrets["SHEET_URL"])
    else: 
        st.error("Missing Google Cloud Credentials.")

    st.divider()
    
    # --- 3. CURRENCY ---
    st.markdown("### 💱 Currency")
    if 'active_currency' not in st.session_state: st.session_state.active_currency = "MYR"
    
    currency_options = ["MYR", "USD", "GBP", "SGD", "EUR", "AUD", "JPY"]
    curr_idx = 0
    if st.session_state.active_currency in currency_options:
        curr_idx = currency_options.index(st.session_state.active_currency)
        
    selected_currency = st.selectbox("Display Currency", currency_options, index=curr_idx)

# --- HELPER FUNCTIONS ---
def get_default_state():
    return {
        "basic_salary": 6000.0, "allowances": 500.0, "variable_income": 0.0, "current_savings": 10000.0, "epf_rate": 11,
        "expenses": [{"Category": "Housing", "Amount": 1500.0}, {"Category": "Car", "Amount": 800.0}, {"Category": "Food", "Amount": 1000.0}, {"Category": "Utilities", "Amount": 300.0}, {"Category": "Loans", "Amount": 200.0}, {"Category": "Savings", "Amount": 500.0}],
        "deductions": [{"Category": "SOCSO", "Amount": 19.75}, {"Category": "EIS", "Amount": 7.90}, {"Category": "PCB", "Amount": 300.00}]
    }

def get_google_sheet_client():
    try:
        if "GCP_CREDENTIALS" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GCP_CREDENTIALS"]), ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
            return gspread.authorize(creds)
    except: return None
    return None

def get_sheet_data(worksheet_name):
    client = get_google_sheet_client()
    if client:
        try:
            ws = client.open_by_url(st.secrets["SHEET_URL"]).worksheet(worksheet_name)
            df = pd.DataFrame(ws.get_all_records())
            return df if not df.empty else pd.DataFrame()
        except: return pd.DataFrame()
    return pd.DataFrame()

def save_row_to_history(row_data_dict):
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        try: ws = sheet.worksheet("History")
        except: ws = sheet.add_worksheet(title="History", rows=100, cols=20)
        
        expected_headers = list(row_data_dict.keys())
        if not ws.row_values(1) or ws.row_values(1) != expected_headers:
            ws.clear(); ws.append_row(expected_headers)
        
        all_values = ws.get_all_values()
        if len(all_values) > 1:
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            mask = (df['Month'].astype(str) == str(row_data_dict['Month'])) & (df['Year'].astype(str) == str(row_data_dict['Year']))
            if mask.any():
                for idx in sorted(df.index[mask].tolist(), reverse=True): ws.delete_rows(int(idx) + 2)
        ws.append_row(list(row_data_dict.values()))

def delete_rows_from_sheet(worksheet_name, month_year_list):
    client = get_google_sheet_client()
    if client:
        ws = client.open_by_url(st.secrets["SHEET_URL"]).worksheet(worksheet_name)
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty:
            df['Label'] = df['Month'] + " " + df['Year'].astype(str)
            df_clean = df[~df['Label'].isin(month_year_list)].drop(columns=['Label'])
            ws.clear(); ws.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())

def save_cloud_state():
    state_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expenses": json.dumps(st.session_state.get('expenses', [])),
        "deductions": json.dumps(st.session_state.get('deductions_list', [])),
        "basic_salary": st.session_state.get('basic_salary', 6000.0),
        "allowances": st.session_state.get('allowances', 500.0),
        "variable_income": st.session_state.get('variable_income', 0.0),
        "current_savings": st.session_state.get('current_savings', 10000.0),
        "epf_rate": st.session_state.get('epf_rate', 11),
        "month_select": st.session_state.get('month_select', "December"),
        "year_input": st.session_state.get('year_input', datetime.now().year),
        "currency": st.session_state.get('active_currency', "MYR")
    }
    client = get_google_sheet_client()
    if client:
        try: ws = client.open_by_url(st.secrets["SHEET_URL"]).worksheet("State")
        except: ws = client.open_by_url(st.secrets["SHEET_URL"]).add_worksheet(title="State", rows=2, cols=10)
        ws.clear(); ws.append_row(list(state_data.keys())); ws.append_row(list(state_data.values()))

def load_cloud_state():
    client = get_google_sheet_client()
    if client:
        try:
            data = client.open_by_url(st.secrets["SHEET_URL"]).worksheet("State").get_all_records()
            if data: return data[-1]
        except: return None
    return None

@st.cache_data(ttl=3600)
def get_currency_data(target_currency_code):
    try:
        ticker = yf.Ticker(f"MYR{target_currency_code}=X")
        hist = ticker.history(period="1y")
        return hist['Close'].iloc[-1], hist
    except: return None, None

def perform_currency_switch(target_currency):
    current_currency = st.session_state.active_currency
    if current_currency == target_currency: return
    
    rate = 1.0
    # Normalize to MYR
    if current_currency != "MYR":
        try:
            data = yf.Ticker(f"{current_currency}MYR=X").history(period="1d")
            if not data.empty:
                to_myr = data['Close'].iloc[-1]
                st.session_state.basic_salary *= to_myr
                st.session_state.allowances *= to_myr
                st.session_state.variable_income *= to_myr
                st.session_state.current_savings *= to_myr
                for x in st.session_state.expenses: x['Amount'] *= to_myr
                for x in st.session_state.deductions_list: x['Amount'] *= to_myr
            else: st.error("Rate Error"); return
        except: st.error("API Error"); return

    # Convert to Target
    if target_currency != "MYR":
        try:
            data = yf.Ticker(f"MYR{target_currency}=X").history(period="1d")
            if not data.empty:
                to_target = data['Close'].iloc[-1]
                st.session_state.basic_salary *= to_target
                st.session_state.allowances *= to_target
                st.session_state.variable_income *= to_target
                st.session_state.current_savings *= to_target
                for x in st.session_state.expenses: x['Amount'] *= to_target
                for x in st.session_state.deductions_list: x['Amount'] *= to_target
            else: st.error("Rate Error"); return
        except: st.error("API Error"); return

    st.session_state.loaded_salary = st.session_state.basic_salary
    st.session_state.loaded_allowances = st.session_state.allowances
    st.session_state.loaded_var = st.session_state.variable_income
    st.session_state.loaded_savings = st.session_state.current_savings
    st.session_state.active_currency = target_currency
    st.rerun()

# --- INITIALIZATION ---
if 'data_loaded' not in st.session_state:
    cloud_state = load_cloud_state()
    defaults = get_default_state()
    if cloud_state:
        st.session_state.expenses = json.loads(cloud_state.get('expenses', json.dumps(defaults['expenses'])))
        st.session_state.deductions_list = json.loads(cloud_state.get('deductions', json.dumps(defaults['deductions'])))
        st.session_state.loaded_salary = float(cloud_state.get('basic_salary', defaults['basic_salary']))
        st.session_state.loaded_allowances = float(cloud_state.get('allowances', defaults['allowances']))
        st.session_state.loaded_var = float(cloud_state.get('variable_income', defaults['variable_income']))
        st.session_state.loaded_savings = float(cloud_state.get('current_savings', defaults['current_savings']))
        st.session_state.loaded_epf = int(cloud_state.get('epf_rate', defaults['epf_rate']))
        st.session_state.loaded_month = cloud_state.get('month_select', "December")
        st.session_state.loaded_year = int(cloud_state.get('year_input', datetime.now().year))
        st.session_state.active_currency = cloud_state.get('currency', "MYR")
    else:
        for k, v in defaults.items(): st.session_state[k] = v 
        st.session_state.deductions_list = defaults['deductions']
        st.session_state.loaded_salary = defaults['basic_salary']
        st.session_state.loaded_allowances = defaults['allowances']
        st.session_state.loaded_var = defaults['variable_income']
        st.session_state.loaded_savings = defaults['current_savings']
        st.session_state.loaded_epf = defaults['epf_rate']
        st.session_state.loaded_month = "December"
        st.session_state.loaded_year = datetime.now().year
        st.session_state.active_currency = "MYR"
    
    st.session_state.last_viewed_month = st.session_state.loaded_month
    st.session_state.last_viewed_year = st.session_state.loaded_year
    st.session_state.data_loaded = True

# Safety Checks
if 'last_viewed_month' not in st.session_state: st.session_state.last_viewed_month = st.session_state.get('loaded_month', "December")
if 'last_viewed_year' not in st.session_state: st.session_state.last_viewed_year = st.session_state.get('loaded_year', datetime.now().year)
if 'available_models' not in st.session_state: st.session_state.available_models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]

# --- SIDEBAR LOGIC (Continuation) ---
with st.sidebar:
    if selected_currency != st.session_state.active_currency:
        with st.spinner(f"Converting to {selected_currency}..."):
            perform_currency_switch(selected_currency)

    st.divider()
    st.markdown("### ☁️ Sync")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬆️ Upload"):
            with st.spinner("Syncing..."): save_cloud_state(); st.success("Uploaded!")
    with c2:
        if st.button("⬇️ Pull"):
            with st.spinner("Downloading..."):
                cs = load_cloud_state()
                if cs:
                    st.session_state["basic_salary"] = float(cs.get('basic_salary', 0))
                    st.session_state["allowances"] = float(cs.get('allowances', 0))
                    st.session_state["variable_income"] = float(cs.get('variable_income', 0))
                    st.session_state["current_savings"] = float(cs.get('current_savings', 0))
                    st.session_state["epf_rate"] = int(cs.get('epf_rate', 11))
                    st.session_state["month_select"] = cs.get('month_select', "December")
                    st.session_state["year_input"] = int(cs.get('year_input', datetime.now().year))
                    st.session_state.expenses = json.loads(cs.get('expenses', '[]'))
                    st.session_state.deductions_list = json.loads(cs.get('deductions', '[]'))
                    st.session_state["active_currency"] = cs.get('currency', "MYR")
                    
                    st.session_state.loaded_salary = st.session_state["basic_salary"]
                    st.session_state.loaded_allowances = st.session_state["allowances"]
                    st.session_state.loaded_var = st.session_state["variable_income"]
                    st.session_state.loaded_savings = st.session_state["current_savings"]
                    st.session_state.loaded_epf = st.session_state["epf_rate"]
                    st.session_state.loaded_month = st.session_state["month_select"]
                    st.session_state.loaded_year = st.session_state["year_input"]
                    st.session_state.last_viewed_month = st.session_state["month_select"]
                    st.session_state.last_viewed_year = st.session_state["year_input"]
                    st.rerun()
            st.success("Updated!")

    st.divider()
    with st.expander("🤖 Magic Auto-Fill"):
        selected_fill_model = st.selectbox("Model", st.session_state.available_models, index=0, key="fill_model_select")
        user_persona = st.text_area("Scenario", placeholder="e.g., Senior Lecturer in KL", height=70)
        if st.button("✨ Generate Profile"):
            if not api_key: st.error("API Key required.")
            else:
                with st.spinner("Generating..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        prompt = f"""You are a Data Entry API. Persona: "{user_persona}". Return JSON: {{"basic_salary": float, "allowances": float, "variable_income": float, "current_savings": float, "epf_rate": int, "expenses": [{{"Category":str,"Amount":float}}], "deductions": [{{"Category":str,"Amount":float}}]}}"""
                        response = client.models.generate_content(model=selected_fill_model, contents=prompt)
                        ai_data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
                        
                        st.session_state["basic_salary"] = float(ai_data.get("basic_salary", 0))
                        st.session_state["allowances"] = float(ai_data.get("allowances", 0))
                        st.session_state["variable_income"] = float(ai_data.get("variable_income", 0))
                        st.session_state["current_savings"] = float(ai_data.get("current_savings", 0))
                        st.session_state["epf_rate"] = int(ai_data.get("epf_rate", 11))
                        st.session_state.expenses = ai_data.get("expenses", [])
                        st.session_state.deductions_list = ai_data.get("deductions", [])
                        
                        st.session_state.loaded_salary = st.session_state["basic_salary"]
                        st.session_state.loaded_allowances = st.session_state["allowances"]
                        st.session_state.loaded_var = st.session_state["variable_income"]
                        st.session_state.loaded_savings = st.session_state["current_savings"]
                        st.session_state.loaded_epf = st.session_state["epf_rate"]
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    st.divider()
    if st.button("🛠️ Check AI Models"):
        if not api_key: st.error("API Key required.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                models = client.models.list()
                fetched = [m.name.replace("models/", "") for m in models if "gemini" in m.name and "embedding" not in m.name]
                if fetched: st.session_state.available_models = sorted(fetched); st.success(f"Found {len(fetched)} models!")
            except Exception as e: st.error(f"Error: {e}")

# --- MAIN LAYOUT ---
# MAIN TITLE ON TOP OF PAGE
st.title("💸 Smart Cashflow")
curr = st.session_state.active_currency
st.caption(f"Financial Digital Twin | Current Currency: {curr}")
st.markdown("---")

col_left, col_right = st.columns([1, 1.2], gap="large")

with col_left:
    # --- PERIOD & INCOME ---
    with st.container():
        st.subheader(f"📅 Period & Income ({curr})")
        d_col1, d_col2 = st.columns(2)
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        
        try: def_idx = months.index(st.session_state.loaded_month)
        except: def_idx = 0
        
        selected_month = d_col1.selectbox("Month", months, index=def_idx, key="month_select")
        selected_year = d_col2.number_input("Year", min_value=2020, max_value=2030, value=st.session_state.loaded_year, key="year_input")
        
        if (selected_month != st.session_state.last_viewed_month) or (selected_year != st.session_state.last_viewed_year):
            with st.spinner(f"Syncing records..."):
                df_history = get_sheet_data("History")
                found = None
                if not df_history.empty and 'Month' in df_history.columns and 'Year' in df_history.columns:
                     mask = (df_history['Month'] == selected_month) & (df_history['Year'] == selected_year)
                     if mask.any(): found = df_history[mask].iloc[0]
                
                if found is not None and 'Expenses_JSON' in found:
                    st.session_state["basic_salary"] = float(found.get('Basic_Salary', 0))
                    st.session_state["allowances"] = float(found.get('Allowances', 0))
                    st.session_state["variable_income"] = float(found.get('Variable_Income', 0))
                    st.session_state["current_savings"] = float(found.get('Current_Savings', 0))
                    st.session_state["epf_rate"] = int(found.get('EPF_Rate', 11))
                    st.session_state.expenses = json.loads(found.get('Expenses_JSON', '[]'))
                    st.session_state.deductions_list = json.loads(found.get('Deductions_JSON', '[]'))
                    st.session_state["active_currency"] = found.get('Currency', "MYR")
                    st.toast(f"Data Loaded: {selected_month} {selected_year}", icon="✅")
                else:
                    defaults = get_default_state()
                    st.session_state["basic_salary"] = defaults['basic_salary']
                    st.session_state["allowances"] = defaults['allowances']
                    st.session_state["variable_income"] = defaults['variable_income']
                    st.session_state["current_savings"] = defaults['current_savings']
                    st.session_state["epf_rate"] = defaults['epf_rate']
                    st.session_state.expenses = defaults['expenses']
                    st.session_state.deductions_list = defaults['deductions']
                    st.session_state["active_currency"] = "MYR"
                    st.toast(f"New Period: {selected_month} {selected_year}", icon="✨")

                st.session_state.loaded_salary = st.session_state["basic_salary"]
                st.session_state.loaded_allowances = st.session_state["allowances"]
                st.session_state.loaded_var = st.session_state["variable_income"]
                st.session_state.loaded_savings = st.session_state["current_savings"]
                st.session_state.loaded_epf = st.session_state["epf_rate"]
                st.session_state.last_viewed_month = selected_month
                st.session_state.last_viewed_year = selected_year
                st.rerun()

        st.divider()
        current_savings = st.number_input(f"Current Savings ({curr})", value=st.session_state.loaded_savings, step=1000.0, key="current_savings")
        c1, c2 = st.columns(2)
        basic_salary = c1.number_input(f"Basic Salary ({curr})", value=st.session_state.loaded_salary, key="basic_salary")
        allowances = c1.number_input(f"Allowances ({curr})", value=st.session_state.loaded_allowances, key="allowances")
        variable_income = c2.number_input(f"Side Income ({curr})", value=st.session_state.loaded_var, key="variable_income")
        
        total_gross = basic_salary + allowances + variable_income
        st.markdown(f"<div class='total-badge badge-green'>Total Gross Income: {curr} {total_gross:,.2f}</div>", unsafe_allow_html=True)

    # --- DEDUCTIONS ---
    with st.container():
        st.subheader(f"📉 Deductions ({curr})")
        epf_rate = st.slider("EPF Rate (%)", 0, 20, st.session_state.loaded_epf, key="epf_rate") 
        epf_amount = (basic_salary + allowances) * (epf_rate / 100)
        st.info(f"EPF Contribution: {curr} {epf_amount:,.2f}")
        
        df_deductions_input = pd.DataFrame(st.session_state.deductions_list)
        edited_deductions = st.data_editor(df_deductions_input, num_rows="dynamic", use_container_width=True, key="deductions_editor", column_config={"Category": st.column_config.TextColumn("Deduction Name"), "Amount": st.column_config.NumberColumn(f"Amount ({curr})", format="%.2f")})
        st.session_state.deductions_list = edited_deductions.to_dict('records')
        total_deductions = epf_amount + (edited_deductions['Amount'].sum() if not edited_deductions.empty else 0)
        st.markdown(f"<div class='total-badge badge-red'>Total Deducted: {curr} {total_deductions:,.2f}</div>", unsafe_allow_html=True)

    # --- EXPENSES ---
    with st.container():
        st.subheader(f"🧾 Expenses ({curr})")
        df_expenses_input = pd.DataFrame(st.session_state.expenses)
        edited_expenses = st.data_editor(df_expenses_input, num_rows="dynamic", use_container_width=True, key="expenses_editor", column_config={"Category": st.column_config.TextColumn("Expense Category"), "Amount": st.column_config.NumberColumn(f"Amount ({curr})", format="%.2f")})
        st.session_state.expenses = edited_expenses.to_dict('records')
        total_living_expenses = edited_expenses['Amount'].sum() if not edited_expenses.empty else 0.0
        st.markdown(f"<div class='total-badge badge-blue'>Total Expenses: {curr} {total_living_expenses:,.2f}</div>", unsafe_allow_html=True)

with col_right:
    gross = basic_salary + allowances + variable_income
    net = gross - total_deductions
    total_exp = edited_expenses['Amount'].sum() if not edited_expenses.empty else 0
    balance = net - total_exp

    # --- SNAPSHOT ---
    with st.container():
        st.markdown(f"### 📊 Snapshot: {selected_month} {selected_year}")
        c1, c2 = st.columns(2)
        c1.metric("Net Disposable", f"{curr} {net:,.2f}")
        c2.metric("Monthly Surplus", f"{curr} {balance:,.2f}", delta=f"{balance:,.2f}")

    if curr != "MYR":
        with st.container():
            st.subheader(f"💱 MYR to {curr}")
            rate, hist = get_currency_data(curr)
            if rate:
                st.caption(f"1 MYR = {rate:.4f} {curr}")
                fig_rate = px.line(hist, y="Close", height=200)
                fig_rate.update_layout(margin=dict(t=10, b=0, l=0, r=0), yaxis_title=None, xaxis_title=None)
                st.plotly_chart(fig_rate, use_container_width=True)
            else: st.warning("Chart unavailable")

    with st.container():
        if not edited_expenses.empty:
            fig = px.pie(edited_expenses, values='Amount', names='Category', hole=0.6, title="Spending Breakdown")
            fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

    with st.container():
        t_col1, t_col2 = st.columns([3, 1])
        t_col1.subheader("📈 Wealth Projection")
        duration_option = t_col2.selectbox("Duration", ["1 Year", "3 Years", "5 Years", "10 Years"], index=1)
        duration_map = {"1 Year": 12, "3 Years": 36, "5 Years": 60, "10 Years": 120}
        months_to_project = duration_map[duration_option]
        years_count = months_to_project // 12
        
        t_col2.caption("Inflation %")
        default_rates = [{"Year": i+1, "Inflation": 3.0} for i in range(years_count)]
        edited_rates = t_col2.data_editor(pd.DataFrame(default_rates), hide_index=True, use_container_width=True, column_config={"Inflation": st.column_config.NumberColumn(format="%.1f")})
        yearly_rates_list = [x / 100 for x in edited_rates["Inflation"].tolist()]

        future = []
        acc = current_savings
        cumulative_deflator = 1.0 
        for m in range(months_to_project):
            current_year_idx = m // 12
            rate = yearly_rates_list[current_year_idx] if current_year_idx < len(yearly_rates_list) else 0.03
            monthly_inflation = rate / 12
            acc += balance
            cumulative_deflator *= (1 + monthly_inflation)
            future.append({"Month": m+1, "Nominal Wealth": acc, "Real Purchasing Power": acc / cumulative_deflator})
        
        df_future = pd.DataFrame(future).melt(id_vars=["Month"], var_name="Metric", value_name="Amount")
        fig2 = px.line(df_future, x="Month", y="Amount", color="Metric", color_discrete_map={"Nominal Wealth": "#2ecc71", "Real Purchasing Power": "#e74c3c"})
        fig2.update_traces(fill='tozeroy', selector=dict(name="Nominal Wealth"))
        fig2.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0), legend=dict(orientation="h", y=1.1, title=None))
        t_col1.plotly_chart(fig2, use_container_width=True)

    with st.container():
        st.subheader("☁️ Cloud Database")
        db_col1, db_col2 = st.columns(2)
        
        current_data = {
            "Date": datetime(selected_year, months.index(selected_month)+1, 1).strftime("%Y-%m-%d"),
            "Month": selected_month, "Year": selected_year, "Net_Income": net, "Total_Expenses": total_exp, 
            "Balance": balance, "EPF_Savings": epf_amount, "Basic_Salary": basic_salary, 
            "Allowances": allowances, "Variable_Income": variable_income, "Current_Savings": current_savings, 
            "EPF_Rate": epf_rate, "Expenses_JSON": json.dumps(st.session_state.expenses), 
            "Deductions_JSON": json.dumps(st.session_state.deductions_list), "Currency": curr 
        }
        
        with db_col1:
            if st.button(f"Save Record ({selected_month})", type="primary"):
                with st.spinner("Saving..."):
                    save_row_to_history(current_data)
                    st.success("Saved!")
                    st.session_state.last_viewed_month = selected_month
                    st.rerun()

        st.divider()
        df_hist = get_sheet_data("History")
        if not df_hist.empty and 'Month' in df_hist.columns and 'Year' in df_hist.columns:
            df_hist['Label'] = df_hist['Month'] + " " + df_hist['Year'].astype(str)
            c_load, c_del = st.columns(2)
            
            with c_load:
                record_to_load = st.selectbox("Select Record", df_hist['Label'].unique(), index=None, placeholder="Load past data...", key="loader_box")
                def load_record_callback():
                    record_label = st.session_state.loader_box
                    if record_label:
                        df = get_sheet_data("History")
                        df['Label'] = df['Month'] + " " + df['Year'].astype(str)
                        row = df[df['Label'] == record_label].iloc[0]
                        st.session_state["month_select"] = row['Month']
                        st.session_state["year_input"] = int(row['Year'])
                        st.session_state["basic_salary"] = float(row.get('Basic_Salary', 0))
                        st.session_state["allowances"] = float(row.get('Allowances', 0))
                        st.session_state["variable_income"] = float(row.get('Variable_Income', 0))
                        st.session_state["current_savings"] = float(row.get('Current_Savings', 0))
                        st.session_state["epf_rate"] = int(row.get('EPF_Rate', 11))
                        st.session_state.expenses = json.loads(row.get('Expenses_JSON', '[]'))
                        st.session_state.deductions_list = json.loads(row.get('Deductions_JSON', '[]'))
                        st.session_state["active_currency"] = row.get('Currency', "MYR")
                        st.session_state.loaded_month = row['Month']
                        st.session_state.loaded_year = int(row['Year'])
                        st.session_state.loaded_salary = float(row.get('Basic_Salary', 0))
                        st.session_state.loaded_allowances = float(row.get('Allowances', 0))
                        st.session_state.loaded_var = float(row.get('Variable_Income', 0))
                        st.session_state.loaded_savings = float(row.get('Current_Savings', 0))
                        st.session_state.loaded_epf = int(row.get('EPF_Rate', 11))
                        st.session_state.last_viewed_month = row['Month']
                        st.session_state.last_viewed_year = int(row['Year'])
                        st.toast(f"Jumped to {record_label}!", icon="🚀")
                st.button("Load Record", on_click=load_record_callback)

            with c_del:
                to_delete = st.multiselect("Select Record", df_hist['Label'].unique(), key="deleter_box", label_visibility="hidden")
                if st.button("Delete Selected"):
                    if to_delete:
                        delete_rows_from_sheet("History", to_delete)
                        st.success("Deleted!")
                        st.rerun()

            if 'Date' in df_hist.columns:
                df_hist['Date'] = pd.to_datetime(df_hist['Date'])
                fig_hist = px.area(df_hist.sort_values('Date'), x='Date', y=['Net_Income', 'Balance'], markers=True, height=200)
                st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No history found.")

    st.markdown("###")
    with st.container():
        st.markdown("""<div class='ai-box'><h3>🤖 AI Financial Auditor</h3></div>""", unsafe_allow_html=True)
        selected_auditor_model = st.selectbox("Select Model", st.session_state.available_models, key="auditor_model_select")
        if st.button("🚀 Analyze Portfolio", type="primary"):
            if not api_key: st.warning("API Key required.")
            else:
                try:
                    client = genai.Client(api_key=api_key)
                    deduction_txt = "\n".join([f"- {x['Category']}: {curr} {x['Amount']}" for x in st.session_state.deductions_list])
                    exp_txt = "\n".join([f"- {x['Category']}: {curr} {x['Amount']}" for x in st.session_state.expenses])
                    prompt = f"""Role: Expert Financial Planner. Context: {selected_month} {selected_year}.
                    Stats: Net: {curr} {net:.2f}, Exp: {curr} {total_exp:.2f}, Bal: {curr} {balance:.2f}.
                    Deductions: EPF: {curr} {epf_amount:.2f}\n{deduction_txt}
                    Expenses: {exp_txt}
                    Provide: 1. Leakage Check 2. Tax Reliefs 3. Strategic Advice."""
                    with st.spinner(f"AI is analyzing your finances..."):
                        response = client.models.generate_content(model=selected_auditor_model, contents=prompt)
                        st.markdown(f"""<div class='ai-box'>{response.text}</div>""", unsafe_allow_html=True)
                except Exception as e: st.error(f"Error: {e}")
