import streamlit as st
import pandas as pd
from google import genai
import plotly.express as px
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Smart Cashflow Apps", 
    page_icon="🧬",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- ADVANCED CUSTOM CSS (AESTHETIC & TECH THEME) ---
st.markdown("""
<style>
    /* IMPORT GOOGLE FONT INTER */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* GLOBAL STYLES */
    .stApp {
        background-color: #f8fafc; /* Very light cool gray */
        font-family: 'Inter', sans-serif;
    }
    
    /* REMOVE TOP PADDING */
    .block-container {
        padding-top: 2rem;
    }

    /* CARD STYLE CONTAINERS */
    .stContainer {
        background-color: #ffffff;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #f1f5f9;
        margin-bottom: 24px;
    }

    /* HEADERS */
    h1, h2, h3 {
        color: #0f172a;
        font-weight: 700;
        letter-spacing: -0.025em;
    }
    
    h4 {
        font-weight: 600;
        color: #334155;
    }

    /* INPUT FIELDS - CLEANER LOOK */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        color: #334155;
    }

    /* BUTTONS - TECH STYLE */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        font-weight: 600;
        border: none;
        padding: 0.6rem 1rem;
        transition: all 0.2s;
    }
    
    /* Primary Action Buttons */
    div[data-testid="stVerticalBlock"] > div > div > div > div > button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
        box-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.39);
    }

    /* METRICS - BIG & BOLD */
    [data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
        color: #1e293b;
        font-family: 'Inter', monospace;
    }
    [data-testid="stMetricLabel"] {
        font-size: 14px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* BADGES FOR TOTALS */
    .total-badge {
        padding: 8px 12px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 15px;
        display: inline-block;
        margin-top: 10px;
        width: 100%;
        text-align: center;
    }
    .badge-green { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    .badge-red { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .badge-blue { background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }

    /* AI BOX STYLING */
    .ai-box {
        background-color: #1e293b;
        border-radius: 12px;
        padding: 20px;
        color: #e2e8f0;
        border-left: 4px solid #8b5cf6;
        font-family: 'Inter', sans-serif;
        box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.2);
    }
    
    /* TABLE STYLING */
    [data-testid="stDataEditor"] {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER: DEFAULT TEMPLATE ---
def get_default_state():
    """Returns the baseline 'clean slate' data."""
    return {
        "basic_salary": 6000.0,
        "allowances": 500.0,
        "variable_income": 0.0,
        "current_savings": 10000.0,
        "epf_rate": 11,
        "expenses": [
            {"Category": "Housing (Rent/Loan)", "Amount": 1500.0},
            {"Category": "Car Loan/Transport", "Amount": 800.0},
            {"Category": "Food & Groceries", "Amount": 1000.0},
            {"Category": "Utilities & Telco", "Amount": 300.0},
            {"Category": "PTPTN / Education Loan", "Amount": 200.0},
            {"Category": "Savings / Investments", "Amount": 500.0},
        ],
        "deductions": [
            {"Category": "SOCSO / PERKESO", "Amount": 19.75},
            {"Category": "EIS / SIP", "Amount": 7.90},
            {"Category": "PCB (Monthly Tax)", "Amount": 300.00},
        ]
    }

# --- GOOGLE SHEETS FUNCTIONS (ROBUST) ---
def get_google_sheet_client():
    try:
        if "GCP_CREDENTIALS" in st.secrets:
            creds_json = json.loads(st.secrets["GCP_CREDENTIALS"])
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
            client = gspread.authorize(creds)
            return client
    except Exception as e:
        st.error(f"Secret Error: {e}")
    return None

def get_sheet_data(worksheet_name):
    client = get_google_sheet_client()
    if client:
        try:
            sheet = client.open_by_url(st.secrets["SHEET_URL"])
            try:
                ws = sheet.worksheet(worksheet_name)
                data = ws.get_all_records()
                df = pd.DataFrame(data)
                if df.empty: return pd.DataFrame()
                return df
            except gspread.exceptions.WorksheetNotFound:
                return pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()
    return pd.DataFrame()

def save_row_to_history(row_data_dict):
    """Saves a row to History with strict Header Enforcement."""
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        try:
            ws = sheet.worksheet("History")
        except:
            ws = sheet.add_worksheet(title="History", rows=100, cols=20)
            
        expected_headers = list(row_data_dict.keys())
        current_headers = ws.row_values(1)
        
        if not current_headers or current_headers != expected_headers:
            ws.clear()
            ws.append_row(expected_headers)
        
        all_values = ws.get_all_values()
        if len(all_values) > 1:
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            mask = (df['Month'].astype(str) == str(row_data_dict['Month'])) & \
                   (df['Year'].astype(str) == str(row_data_dict['Year']))
            if mask.any():
                indices_to_delete = df.index[mask].tolist()
                for idx in sorted(indices_to_delete, reverse=True):
                    ws.delete_rows(int(idx) + 2)
                    
        ws.append_row(list(row_data_dict.values()))

def delete_rows_from_sheet(worksheet_name, month_year_list):
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        ws = sheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df['Label'] = df['Month'] + " " + df['Year'].astype(str)
            df_clean = df[~df['Label'].isin(month_year_list)]
            df_clean = df_clean.drop(columns=['Label'])
            ws.clear()
            ws.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())

# --- CURRENCY LOGIC ---
def convert_value(value, rate):
    return value * rate

def perform_currency_switch(target_currency):
    """Converts the entire session state to the new currency."""
    current_currency = st.session_state.active_currency
    
    if current_currency == target_currency:
        return

    rate = 1.0
    
    # 1. Normalize to MYR first
    if current_currency != "MYR":
        ticker = f"{current_currency}MYR=X"
        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                to_myr_rate = data['Close'].iloc[-1]
                st.session_state.basic_salary *= to_myr_rate
                st.session_state.allowances *= to_myr_rate
                st.session_state.variable_income *= to_myr_rate
                st.session_state.current_savings *= to_myr_rate
                for exp in st.session_state.expenses: exp['Amount'] *= to_myr_rate
                for ded in st.session_state.deductions_list: ded['Amount'] *= to_myr_rate
            else:
                st.error("Could not fetch rates to normalize currency.")
                return
        except:
            st.error("Currency API Error")
            return

    # 2. Convert from MYR to Target
    if target_currency != "MYR":
        ticker = f"MYR{target_currency}=X"
        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                to_target_rate = data['Close'].iloc[-1]
                st.session_state.basic_salary *= to_target_rate
                st.session_state.allowances *= to_target_rate
                st.session_state.variable_income *= to_target_rate
                st.session_state.current_savings *= to_target_rate
                for exp in st.session_state.expenses: exp['Amount'] *= to_target_rate
                for ded in st.session_state.deductions_list: ded['Amount'] *= to_target_rate
            else:
                st.error("Could not fetch target rates.")
                return
        except:
            st.error("Currency API Error")
            return

    # 3. Update Sync Helpers & State
    st.session_state.loaded_salary = st.session_state.basic_salary
    st.session_state.loaded_allowances = st.session_state.allowances
    st.session_state.loaded_var = st.session_state.variable_income
    st.session_state.loaded_savings = st.session_state.current_savings
    st.session_state.active_currency = target_currency
    st.rerun()

# --- CLOUD SYNC FUNCTIONS ---
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
        "currency": st.session_state.get('active_currency', "MYR") # Save Currency
    }
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        try: ws = sheet.worksheet("State")
        except: ws = sheet.add_worksheet(title="State", rows=2, cols=10)
        ws.clear()
        ws.append_row(list(state_data.keys()))
        ws.append_row(list(state_data.values()))

def load_cloud_state():
    client = get_google_sheet_client()
    if client:
        try:
            sheet = client.open_by_url(st.secrets["SHEET_URL"])
            ws = sheet.worksheet("State")
            data = ws.get_all_records()
            if data: return data[-1]
        except: return None
    return None

# --- CURRENCY HELPER ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def get_currency_data(target_currency_code):
    """Fetches MYR to Target Currency data."""
    try:
        ticker_symbol = f"MYR{target_currency_code}=X"
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1y")
        current_rate = hist['Close'].iloc[-1]
        return current_rate, hist
    except Exception as e:
        return None, None

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
        st.session_state.expenses = defaults['expenses']
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

# Safety Check
if 'last_viewed_month' not in st.session_state:
    st.session_state.last_viewed_month = st.session_state.get('loaded_month', "December")
if 'last_viewed_year' not in st.session_state:
    st.session_state.last_viewed_year = st.session_state.get('loaded_year', datetime.now().year)
if 'active_currency' not in st.session_state:
    st.session_state.active_currency = "MYR"

if 'available_models' not in st.session_state:
    st.session_state.available_models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key: api_key = st.text_input("Enter Gemini API Key", type="password")
    else: st.success("Gemini Connected 🧠")
    
    if "GCP_CREDENTIALS" in st.secrets: 
        st.success("Google Cloud Active ☁️")
        if "SHEET_URL" in st.secrets:
            st.link_button("📂 View Database", st.secrets["SHEET_URL"])
    else: 
        st.error("Missing Google Cloud Credentials.")

    st.divider()
    
    # --- GLOBAL CURRENCY SWITCHER ---
    st.markdown("### 💱 Currency")
    currency_options = ["MYR", "USD", "GBP", "SGD", "EUR", "AUD", "JPY"]
    selected_currency = st.selectbox(
        "Dashboard Currency", 
        currency_options, 
        index=currency_options.index(st.session_state.active_currency) if st.session_state.active_currency in currency_options else 0
    )
    
    if selected_currency != st.session_state.active_currency:
        with st.spinner(f"Converting dashboard to {selected_currency}..."):
            perform_currency_switch(selected_currency)

    st.divider()
    st.markdown("### ☁️ Sync")
    col_sync1, col_sync2 = st.columns(2)
    with col_sync1:
        if st.button("⬆️ Upload"):
            with st.spinner("Syncing..."):
                save_cloud_state()
            st.success("Uploaded!")
    with col_sync2:
        if st.button("⬇️ Pull"):
            with st.spinner("Downloading..."):
                cloud_state = load_cloud_state()
                if cloud_state:
                    st.session_state["basic_salary"] = float(cloud_state.get('basic_salary', 0.0))
                    st.session_state["allowances"] = float(cloud_state.get('allowances', 0.0))
                    st.session_state["variable_income"] = float(cloud_state.get('variable_income', 0.0))
                    st.session_state["current_savings"] = float(cloud_state.get('current_savings', 0.0))
                    st.session_state["epf_rate"] = int(cloud_state.get('epf_rate', 11))
                    st.session_state["month_select"] = cloud_state.get('month_select', "December")
                    st.session_state["year_input"] = int(cloud_state.get('year_input', datetime.now().year))
                    st.session_state.expenses = json.loads(cloud_state.get('expenses', '[]'))
                    st.session_state.deductions_list = json.loads(cloud_state.get('deductions', '[]'))
                    st.session_state["active_currency"] = cloud_state.get('currency', "MYR")
                    
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
        user_persona = st.text_area("Scenario", placeholder="e.g., Senior Lecturer in KL...", height=70)
        
        if st.button("✨ Generate Profile"):
            if not api_key: st.error("API Key required.")
            else:
                with st.spinner(f"Creating Digital Twin..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        prompt = f"""You are a Data Entry API. Persona: "{user_persona}". 
                        Return JSON only: {{"basic_salary": float, "allowances": float, "variable_income": float, "current_savings": float, "epf_rate": int, "expenses": [{{"Category":str,"Amount":float}}], "deductions": [{{"Category":str,"Amount":float}}]}}"""
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

    # --- RESTORED BUTTON ---
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
st.title("🧬 FinTwin: Financial Digital Twin")
st.markdown("---")

col_left, col_right = st.columns([1, 1.2], gap="large")

curr = st.session_state.active_currency

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
                found_record = None
                if not df_history.empty and 'Month' in df_history.columns and 'Year' in df_history.columns:
                     mask = (df_history['Month'] == selected_month) & (df_history['Year'] == selected_year)
                     if mask.any(): found_record = df_history[mask].iloc[0]
                
                if found_record is not None and 'Expenses_JSON' in found_record:
                    st.session_state["basic_salary"] = float(found_record.get('Basic_Salary', 0))
                    st.session_state["allowances"] = float(found_record.get('Allowances', 0))
                    st.session_state["variable_income"] = float(found_record.get('Variable_Income', 0))
                    st.session_state["current_savings"] = float(found_record.get('Current_Savings', 0))
                    st.session_state["epf_rate"] = int(found_record.get('EPF_Rate', 11))
                    st.session_state.expenses = json.loads(found_record.get('Expenses_JSON', '[]'))
                    st.session_state.deductions_list = json.loads(found_record.get('Deductions_JSON', '[]'))
                    st.session_state["active_currency"] = found_record.get('Currency', "MYR")
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
        st.info(f"EPF Contribution: {curr} {epf_amount:.2f}")
        
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

    # --- SNAPSHOT HERO CARD ---
    with st.container():
        st.markdown(f"### 📊 Snapshot: {selected_month} {selected_year}")
        c1, c2 = st.columns(2)
        c1.metric("Net Disposable", f"{curr} {net:,.2f}")
        c2.metric("Monthly Surplus", f"{curr} {balance:,.2f}", delta=f"{balance:,.2f}")

    # --- CURRENCY CHART ---
    if curr != "MYR":
        with st.container():
            st.subheader(f"💱 MYR to {curr} Trend")
            ticker_name = f"MYR{curr}=X"
            try:
                hist = yf.Ticker(ticker_name).history(period="1y")
                if not hist.empty:
                    current_rate = hist['Close'].iloc[-1]
                    st.caption(f"Live Rate: 1 MYR = {current_rate:.4f} {curr}")
                    fig_rate = px.line(hist, y="Close", height=200)
                    fig_rate.update_layout(margin=dict(t=10, b=0, l=0, r=0), yaxis_title=None, xaxis_title=None)
                    st.plotly_chart(fig_rate, use_container_width=True)
            except: st.warning("Chart unavailable")

    with st.container():
        if not edited_expenses.empty:
            fig = px.pie(edited_expenses, values='Amount', names='Category', hole=0.6, title=f"Spending Breakdown")
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

    # --- CLOUD DATABASE ---
    with st.container():
        st.subheader("☁️ Cloud Database")
        db_col1, db_col2 = st.columns(2)
        
        current_data = {
            "Date": datetime(selected_year, months.index(selected_month)+1, 1).strftime("%Y-%m-%d"),
            "Month": selected_month, "Year": selected_year, "Net_Income": net, "Total_Expenses": total_exp, 
            "Balance": balance, "EPF_Savings": epf_amount, "Basic_Salary": basic_salary, 
            "Allowances": allowances, "Variable_Income": variable_income, "Current_Savings": current_savings, 
            "EPF_Rate": epf_rate, "Expenses_JSON": json.dumps(st.session_state.expenses), 
            "Deductions_JSON": json.dumps(st.session_state.deductions_list),
            "Currency": curr 
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

    # --- AI AUDITOR ---
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

