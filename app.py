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

# --- GOOGLE SHEETS CONNECTION ---
def get_google_sheet_client():
    try:
        # Load credentials from Streamlit Secrets
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
        except Exception as e:
            # If worksheet doesn't exist, return empty
            return pd.DataFrame()
    return pd.DataFrame()

def save_row_to_sheet(worksheet_name, row_data_dict):
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        try:
            ws = sheet.worksheet(worksheet_name)
        except:
            # Create if missing
            ws = sheet.add_worksheet(title=worksheet_name, rows=100, cols=20)
            # Add headers
            ws.append_row(list(row_data_dict.keys()))
            
        # Append data
        ws.append_row(list(row_data_dict.values()))

def delete_rows_from_sheet(worksheet_name, month_year_list):
    """Surgical delete based on Month+Year label"""
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        ws = sheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Create label column to match selection
        df['Label'] = df['Month'] + " " + df['Year'].astype(str)
        
        # Filter keep rows
        df_clean = df[~df['Label'].isin(month_year_list)]
        df_clean = df_clean.drop(columns=['Label'])
        
        # Clear and rewrite
        ws.clear()
        ws.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())

# --- SAVE/LOAD STATE (CLOUD PERSISTENCE) ---
# We use the "State" tab in Google Sheets to act as the "Auto-Save" memory
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
    }
    
    # We overwrite the 'State' tab completely
    client = get_google_sheet_client()
    if client:
        sheet = client.open_by_url(st.secrets["SHEET_URL"])
        try:
            ws = sheet.worksheet("State")
            ws.clear()
        except:
            ws = sheet.add_worksheet(title="State", rows=2, cols=10)
        
        # Write headers and values
        ws.append_row(list(state_data.keys()))
        ws.append_row(list(state_data.values()))

def load_cloud_state():
    client = get_google_sheet_client()
    if client:
        try:
            sheet = client.open_by_url(st.secrets["SHEET_URL"])
            ws = sheet.worksheet("State")
            data = ws.get_all_records()
            if data:
                return data[-1] # Return last saved state
        except:
            return None
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
        # Defaults
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

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key:
        api_key = st.text_input("Enter Gemini API Key", type="password")
    else:
        st.success("Gemini API Key Connected! 🔒")
    
    # Check GSheets
    if "GCP_CREDENTIALS" in st.secrets:
        st.success("Google Sheets Connected! ☁️")
    else:
        st.error("Missing Google Cloud Credentials in Secrets.")

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

    st.divider()
    if st.button("💾 Force Save Current State"):
        save_cloud_state()
        st.success("Draft saved to Cloud!")

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
        st.session_state.deductions_list = edited_deductions.to_dict('records')
        total_deductions = epf_amount + (edited_deductions['Amount'].sum() if not edited_deductions.empty else 0)
        st.markdown(f"#### Total Deducted: <span style='color:#e74c3c'>RM {total_deductions:.2f}</span>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("🧾 Living Expenses")
        df_expenses_input = pd.DataFrame(st.session_state.expenses)
        edited_expenses = st.data_editor(df_expenses_input, num_rows="dynamic", use_container_width=True, key="expenses_editor", column_config={"Category": st.column_config.TextColumn("Expense Category"), "Amount": st.column_config.NumberColumn("Amount (RM)", format="%.2f")})
        st.session_state.expenses = edited_expenses.to_dict('records')

with col_right:
    gross = basic_salary + allowances + variable_income
    net = gross - total_deductions
    total_exp = edited_expenses['Amount'].sum() if not edited_expenses.empty else 0
    balance = net - total_exp

    st.markdown(f"### Snapshot: {selected_month} {selected_year}")
    c1, c2 = st.columns(2)
    with c1: st.metric("Net Disposable", f"RM {net:.2f}")
    with c2: st.metric("Monthly Surplus", f"RM {balance:.2f}", delta=f"{balance:.2f}")

    with st.container(border=True):
        if not edited_expenses.empty:
            fig = px.pie(edited_expenses, values='Amount', names='Category', hole=0.5, title="Expense Breakdown")
            fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

    # --- DATA MANAGEMENT (GOOGLE SHEETS) ---
    with st.container(border=True):
        st.subheader("☁️ Cloud Database (Google Sheets)")
        db_col1, db_col2 = st.columns(2)
        
        current_data = {
            "Date": datetime(selected_year, months.index(selected_month)+1, 1).strftime("%Y-%m-%d"),
            "Month": selected_month, "Year": selected_year,
            "Net_Income": net, "Total_Expenses": total_exp, "Balance": balance, "EPF_Savings": epf_amount
        }
        
        with db_col1:
            if st.button(f"Save {selected_month} {selected_year}"):
                with st.spinner("Saving to Google Sheets..."):
                    save_row_to_sheet("History", current_data)
                    save_cloud_state() # Also save current draft inputs
                    st.success("Saved permanently to Cloud!")
                    st.rerun()

        st.divider()
        # History Logic
        df_hist = get_sheet_data("History")
        if not df_hist.empty:
            # Multi-select Delete
            df_hist['Label'] = df_hist['Month'] + " " + df_hist['Year'].astype(str)
            to_delete = st.multiselect("Select records to delete from Cloud:", df_hist['Label'].unique())
            if to_delete:
                if st.button("🗑️ Delete Selected from Cloud"):
                    with st.spinner("Deleting..."):
                        delete_rows_from_sheet("History", to_delete)
                        st.success("Deleted!")
                        st.rerun()
            
            # Chart
            st.caption("History Trend")
            df_hist['Date'] = pd.to_datetime(df_hist['Date'])
            df_hist = df_hist.sort_values('Date')
            fig_hist = px.line(df_hist, x='Date', y=['Net_Income', 'Balance'], markers=True, height=250)
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No history found in Google Sheet.")

    # AI Section
    st.markdown("###")
    with st.container():
        st.markdown("""<div style="background-color: #0f172a; padding: 20px; border-radius: 10px; color: white; border: 1px solid #334155; margin-bottom: 10px;">
            <h3 style="margin:0;">✨ AI Financial Auditor</h3></div>""", unsafe_allow_html=True)
        selected_model = st.selectbox("Select AI Model", st.session_state.available_models)
        if st.button("🚀 Generate Analysis", type="primary"):
            if not api_key: st.warning("API Key required.")
            else:
                try:
                    client = genai.Client(api_key=api_key)
                    deduction_txt = "\n".join([f"- {x['Category']}: RM {x['Amount']}" for x in st.session_state.deductions_list])
                    exp_txt = "\n".join([f"- {x['Category']}: RM {x['Amount']}" for x in st.session_state.expenses])
                    prompt = f"""Role: Expert Malaysian Financial Planner. Context: {selected_month} {selected_year}.
                    Stats: Net: RM {net:.2f}, Exp: RM {total_exp:.2f}, Bal: RM {balance:.2f}.
                    Deductions: EPF: RM {epf_amount:.2f}\n{deduction_txt}
                    Expenses: {exp_txt}
                    Provide: 1. Leakage Check 2. Tax Reliefs 3. Researcher Analogy."""
                    with st.spinner(f"Asking {selected_model}..."):
                        response = client.models.generate_content(model=selected_model, contents=prompt)
                        st.markdown(f"""<div style="background-color: #1e293b; padding: 20px; border-radius: 10px; color: #e2e8f0; border-left: 5px solid #8b5cf6;">{response.text}</div>""", unsafe_allow_html=True)
                except Exception as e: st.error(f"Error: {e}")

# Auto-save Draft state to Cloud periodically (or via manual button to stay fast)
# We avoid auto-saving on every keystroke to prevent API rate limits, relying on the 'Save' button or 'Force Save' sidebar button.
