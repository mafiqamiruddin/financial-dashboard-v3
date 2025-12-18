import streamlit as st
import pandas as pd
from google import genai
import plotly.express as px
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="MY Financial Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    .stContainer { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    [data-testid="stMetricValue"] { font-size: 24px; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    [data-testid="stDataEditor"] { border: 1px solid #e0e0e0; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS FUNCTIONS ---
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
            ws = sheet.worksheet(worksheet_name)
            data = ws.get_all_records()
            return pd.DataFrame(data)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def save_row_to_sheet(worksheet_name, row_data_dict):
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        try:
            ws = sheet.worksheet(worksheet_name)
        except:
            ws = sheet.add_worksheet(title=worksheet_name, rows=100, cols=20)
            
        existing_data = ws.get_all_values()
        if not existing_data:
            ws.append_row(list(row_data_dict.keys()))
            
        ws.append_row(list(row_data_dict.values()))

def delete_rows_from_sheet(worksheet_name, month_year_list):
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        ws = sheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        df['Label'] = df['Month'] + " " + df['Year'].astype(str)
        df_clean = df[~df['Label'].isin(month_year_list)]
        df_clean = df_clean.drop(columns=['Label'])
        
        ws.clear()
        ws.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())

# --- CLOUD SYNC FUNCTIONS ---
def save_cloud_state():
    """Push current screen inputs to Google Sheets 'State' tab"""
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
    """Pull data from Google Sheets 'State' tab"""
    client = get_google_sheet_client()
    if client:
        try:
            sheet = client.open_by_url(st.secrets["SHEET_URL"])
            ws = sheet.worksheet("State")
            data = ws.get_all_records()
            if data: return data[-1]
        except: return None
    return None

# --- INITIALIZATION ---
if 'data_loaded' not in st.session_state:
    cloud_state = load_cloud_state()
    if cloud_state:
        st.session_state.expenses = json.loads(cloud_state.get('expenses', '[]'))
        st.session_state.deductions_list = json.loads(cloud_state.get('deductions', '[]'))
        st.session_state.loaded_salary = float(cloud_state.get('basic_salary', 6000.0))
        st.session_state.loaded_allowances = float(cloud_state.get('allowances', 500.0))
        st.session_state.loaded_var = float(cloud_state.get('variable_income', 0.0))
        st.session_state.loaded_savings = float(cloud_state.get('current_savings', 10000.0))
        st.session_state.loaded_epf = int(cloud_state.get('epf_rate', 11))
        st.session_state.loaded_month = cloud_state.get('month_select', "December")
        st.session_state.loaded_year = int(cloud_state.get('year_input', datetime.now().year))
    else:
        st.session_state.expenses = [
            {"Category": "Housing (Rent/Loan)", "Amount": 1500.0},
            {"Category": "Car Loan/Transport", "Amount": 800.0},
            {"Category": "Food & Groceries", "Amount": 1000.0},
            {"Category": "Utilities & Telco", "Amount": 300.0},
            {"Category": "PTPTN / Education Loan", "Amount": 200.0},
            {"Category": "Savings / Investments", "Amount": 500.0},
        ]
        st.session_state.deductions_list = [
            {"Category": "SOCSO / PERKESO", "Amount": 19.75},
            {"Category": "EIS / SIP", "Amount": 7.90},
            {"Category": "PCB (Monthly Tax)", "Amount": 300.00},
        ]
        st.session_state.loaded_salary = 6000.0
        st.session_state.loaded_allowances = 500.0
        st.session_state.loaded_var = 0.0
        st.session_state.loaded_savings = 10000.0
        st.session_state.loaded_epf = 11
        st.session_state.loaded_month = "December"
        st.session_state.loaded_year = datetime.now().year
    
    st.session_state.data_loaded = True

if 'available_models' not in st.session_state:
    st.session_state.available_models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]

# --- SIDEBAR: SYNC & AI CENTER ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key: api_key = st.text_input("Enter Gemini API Key", type="password")
    else: st.success("Gemini API Key Connected! 🔒")
    
    if "GCP_CREDENTIALS" in st.secrets: st.success("Google Sheets Connected! ☁️")
    else: st.error("Missing Google Cloud Credentials.")

    st.divider()
    # CLOUD SYNC CONTROLS
    st.markdown("### ☁️ Cross-Device Sync")
    st.info("Switching devices? Use these buttons to sync your draft inputs.")
    
    col_sync1, col_sync2 = st.columns(2)
    with col_sync1:
        if st.button("⬆️ Upload Draft"):
            with st.spinner("Syncing to Cloud..."):
                save_cloud_state()
            st.success("Draft Uploaded!")
            
    with col_sync2:
        if st.button("⬇️ Pull Draft"):
            with st.spinner("Downloading..."):
                cloud_state = load_cloud_state()
                if cloud_state:
                    # KEY FIX: Explicitly update session keys
                    st.session_state["basic_salary"] = float(cloud_state.get('basic_salary', 0.0))
                    st.session_state["allowances"] = float(cloud_state.get('allowances', 0.0))
                    st.session_state["variable_income"] = float(cloud_state.get('variable_income', 0.0))
                    st.session_state["current_savings"] = float(cloud_state.get('current_savings', 0.0))
                    st.session_state["epf_rate"] = int(cloud_state.get('epf_rate', 11))
                    
                    st.session_state["month_select"] = cloud_state.get('month_select', "December")
                    st.session_state["year_input"] = int(cloud_state.get('year_input', datetime.now().year))
                    
                    st.session_state.expenses = json.loads(cloud_state.get('expenses', '[]'))
                    st.session_state.deductions_list = json.loads(cloud_state.get('deductions', '[]'))
                    
                    # Update helpers
                    st.session_state.loaded_salary = st.session_state["basic_salary"]
                    st.session_state.loaded_allowances = st.session_state["allowances"]
                    st.session_state.loaded_var = st.session_state["variable_income"]
                    st.session_state.loaded_savings = st.session_state["current_savings"]
                    st.session_state.loaded_epf = st.session_state["epf_rate"]
                    st.session_state.loaded_month = st.session_state["month_select"]
                    st.session_state.loaded_year = st.session_state["year_input"]

                    st.rerun() 
            st.success("Draft Updated!")

    # --- NEW: AI AUTO-FILL SECTION ---
    st.divider()
    with st.expander("🤖 AI Auto-Fill (Magic)"):
        st.caption("Describe a persona, and AI will fill the dashboard for you.")
        user_persona = st.text_area("Scenario:", placeholder="e.g., Senior Lecturer in KL with 2 kids and a Honda City loan.", height=70)
        
        if st.button("✨ Fill Dashboard"):
            if not api_key:
                st.error("Please enter API Key first.")
            else:
                with st.spinner("AI is generating a realistic profile..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        prompt_structure = """
                        You are a Data Entry API. 
                        Based on this persona: "{persona}"
                        Generate realistic monthly financial figures (in MYR) for a Malaysian context.
                        
                        Return ONLY a valid JSON object with this EXACT structure (no markdown, no extra text):
                        {{
                            "basic_salary": float,
                            "allowances": float,
                            "variable_income": float,
                            "current_savings": float,
                            "epf_rate": int (between 0 and 20),
                            "expenses": [
                                {{"Category": "Housing", "Amount": float}},
                                {{"Category": "Car/Transport", "Amount": float}},
                                {{"Category": "Food", "Amount": float}},
                                {{"Category": "Utilities", "Amount": float}},
                                {{"Category": "Loans/Debts", "Amount": float}},
                                {{"Category": "Savings/Investments", "Amount": float}}
                            ],
                            "deductions": [
                                {{"Category": "SOCSO", "Amount": float}},
                                {{"Category": "EIS", "Amount": float}},
                                {{"Category": "PCB (Tax)", "Amount": float}}
                            ]
                        }}
                        """
                        final_prompt = prompt_structure.format(persona=user_persona if user_persona else "Average Malaysian Executive")
                        
                        response = client.models.generate_content(
                            model="gemini-2.0-flash-exp", 
                            contents=final_prompt
                        )
                        
                        raw_text = response.text.replace("```json", "").replace("```", "").strip()
                        ai_data = json.loads(raw_text)
                        
                        # Inject into Session State
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
                        
                        st.success("Dashboard populated!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"AI Generation Failed: {e}")

    st.divider()
    if st.button("🛠️ Check Available Models"):
        if not api_key: st.error("API Key required.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                models = client.models.list()
                fetched = [m.name.replace("models/", "") for m in models if "gemini" in m.name and "embedding" not in m.name]
                if fetched: st.session_state.available_models = sorted(fetched); st.success(f"Found {len(fetched)} models!")
            except Exception as e: st.error(f"Error: {e}")

# --- MAIN LAYOUT ---
col_left, col_right = st.columns([1, 1.5], gap="large")

with col_left:
    with st.container(border=True):
        st.subheader("📅 Period & Income")
        d_col1, d_col2 = st.columns(2)
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        try: def_idx = months.index(st.session_state.loaded_month)
        except: def_idx = 0
        selected_month = d_col1.selectbox("Month", months, index=def_idx, key="month_select")
        selected_year = d_col2.number_input("Year", min_value=2020, max_value=2030, value=st.session_state.loaded_year, key="year_input")
        st.divider()
        current_savings = st.number_input("Current Savings", value=st.session_state.loaded_savings, step=1000.0, key="current_savings")
        c1, c2 = st.columns(2)
        basic_salary = c1.number_input("Basic Salary", value=st.session_state.loaded_salary, key="basic_salary")
        allowances = c1.number_input("Allowances", value=st.session_state.loaded_allowances, key="allowances")
        variable_income = c2.number_input("Side Income", value=st.session_state.loaded_var, key="variable_income")

    with st.container(border=True):
        st.subheader("📉 Statutory Deductions")
        epf_rate = st.slider("EPF Rate (%)", 0, 20, st.session_state.loaded_epf, key="epf_rate") 
        epf_amount = (basic_salary + allowances) * (epf_rate / 100)
        st.markdown(f"**EPF Amount:** RM {epf_amount:.2f}")
        st.divider()
        st.caption("Other Deductions")
        df_deductions_input = pd.DataFrame(st.session_state.deductions_list)
        edited_deductions = st.data_editor(df_deductions_input, num_rows="dynamic", use_container_width=True, key="deductions_editor", column_config={"Category": st.column_config.TextColumn("Deduction Name"), "Amount": st.column_config.NumberColumn("Amount (RM)", format="%.2f")})
        st.session_state.deductions_list = edited_
