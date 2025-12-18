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
            
        # 1. ENFORCE HEADER ROW
        expected_headers = list(row_data_dict.keys())
        current_headers = ws.row_values(1)
        
        if not current_headers or current_headers != expected_headers:
            ws.clear()
            ws.append_row(expected_headers)
        
        # 2. HANDLE DUPLICATES
        all_values = ws.get_all_values()
        if len(all_values) > 1:
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            mask = (df['Month'].astype(str) == str(row_data_dict['Month'])) & \
                   (df['Year'].astype(str) == str(row_data_dict['Year']))
            
            if mask.any():
                indices_to_delete = df.index[mask].tolist()
                for idx in sorted(indices_to_delete, reverse=True):
                    ws.delete_rows(int(idx) + 2)
                    
        # 3. APPEND NEW DATA
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

# --- CLOUD SYNC FUNCTIONS ---
def save_cloud_state():
    """Push current screen inputs to Google Sheets 'State' tab (Draft)"""
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
    
    st.session_state.last_viewed_month = st.session_state.loaded_month
    st.session_state.last_viewed_year = st.session_state.loaded_year
    st.session_state.data_loaded = True

if 'last_viewed_month' not in st.session_state:
    st.session_state.last_viewed_month = st.session_state.get('loaded_month', "December")
if 'last_viewed_year' not in st.session_state:
    st.session_state.last_viewed_year = st.session_state.get('loaded_year', datetime.now().year)

if 'available_models' not in st.session_state:
    st.session_state.available_models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]

# --- SIDEBAR: SYNC & AI CENTER ---
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key: api_key = st.text_input("Enter Gemini API Key", type="password")
    else: st.success("Gemini API Key Connected! 🔒")
    
    if "GCP_CREDENTIALS" in st.secrets: 
        st.success("Google Sheets Connected! ☁️")
        if "SHEET_URL" in st.secrets:
            st.link_button("📂 Open Google Database", st.secrets["SHEET_URL"])
    else: 
        st.error("Missing Google Cloud Credentials.")

    st.divider()
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
                    st.session_state["basic_salary"] = float(cloud_state.get('basic_salary', 0.0))
                    st.session_state["allowances"] = float(cloud_state.get('allowances', 0.0))
                    st.session_state["variable_income"] = float(cloud_state.get('variable_income', 0.0))
                    st.session_state["current_savings"] = float(cloud_state.get('current_savings', 0.0))
                    st.session_state["epf_rate"] = int(cloud_state.get('epf_rate', 11))
                    st.session_state["month_select"] = cloud_state.get('month_select', "December")
                    st.session_state["year_input"] = int(cloud_state.get('year_input', datetime.now().year))
                    st.session_state.expenses = json.loads(cloud_state.get('expenses', '[]'))
                    st.session_state.deductions_list = json.loads(cloud_state.get('deductions', '[]'))
                    
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
            st.success("Draft Updated!")

    st.divider()
    with st.expander("🤖 AI Auto-Fill (Magic)"):
        st.caption("Describe a persona, and AI will fill the dashboard for you.")
        selected_fill_model = st.selectbox("Select Model", st.session_state.available_models, index=0, key="fill_model_select")
        user_persona = st.text_area("Scenario:", placeholder="e.g., Senior Lecturer in KL with 2 kids and a Honda City loan.", height=70)
        
        if st.button("✨ Fill Dashboard"):
            if not api_key:
                st.error("Please enter API Key first.")
            else:
                with st.spinner(f"Generating with {selected_fill_model}..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        prompt_structure = """
                        You are a Data Entry API. Based on this persona: "{persona}"
                        Generate realistic monthly financial figures (in MYR) for a Malaysian context.
                        Return ONLY a valid JSON object with this EXACT structure (no markdown):
                        {{
                            "basic_salary": float, "allowances": float, "variable_income": float,
                            "current_savings": float, "epf_rate": int,
                            "expenses": [{{"Category": "Housing", "Amount": float}}, ...],
                            "deductions": [{{"Category": "SOCSO", "Amount": float}}, ...]
                        }}
                        """
                        final_prompt = prompt_structure.format(persona=user_persona if user_persona else "Average Malaysian Executive")
                        response = client.models.generate_content(model=selected_fill_model, contents=final_prompt)
                        raw_text = response.text.replace("```json", "").replace("```", "").strip()
                        ai_data = json.loads(raw_text)
                        
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
        
        # --- SMART CONTEXT SWITCHING LOGIC ---
        try: def_idx = months.index(st.session_state.loaded_month)
        except: def_idx = 0
        
        selected_month = d_col1.selectbox("Month", months, index=def_idx, key="month_select")
        selected_year = d_col2.number_input("Year", min_value=2020, max_value=2030, value=st.session_state.loaded_year, key="year_input")
        
        # THE WATCHER: Check if Month/Year Changed (Automatic Reset)
        if (selected_month != st.session_state.last_viewed_month) or (selected_year != st.session_state.last_viewed_year):
            with st.spinner(f"Checking records for {selected_month} {selected_year}..."):
                df_history = get_sheet_data("History")
                found_record = None
                if not df_history.empty and 'Month' in df_history.columns and 'Year' in df_history.columns:
                     mask = (df_history['Month'] == selected_month) & (df_history['Year'] == selected_year)
                     if mask.any():
                         found_record = df_history[mask].iloc[0]
                
                if found_record is not None and 'Expenses_JSON' in found_record:
                    # CASE A: RECORD EXISTS -> LOAD IT
                    try:
                        st.session_state["basic_salary"] = float(found_record.get('Basic_Salary', 0))
                        st.session_state["allowances"] = float(found_record.get('Allowances', 0))
                        st.session_state["variable_income"] = float(found_record.get('Variable_Income', 0))
                        st.session_state["current_savings"] = float(found_record.get('Current_Savings', 0))
                        st.session_state["epf_rate"] = int(found_record.get('EPF_Rate', 11))
                        st.session_state.expenses = json.loads(found_record.get('Expenses_JSON', '[]'))
                        st.session_state.deductions_list = json.loads(found_record.get('Deductions_JSON', '[]'))
                        st.toast(f"📂 Loaded data for {selected_month} {selected_year}", icon="✅")
                    except Exception as e:
                        st.error(f"Error loading record: {e}")
                else:
                    # CASE B: NO RECORD -> RESET TO DEFAULT
                    defaults = get_default_state()
                    st.session_state["basic_salary"] = defaults['basic_salary']
                    st.session_state["allowances"] = defaults['allowances']
                    st.session_state["variable_income"] = defaults['variable_income']
                    st.session_state["current_savings"] = defaults['current_savings']
                    st.session_state["epf_rate"] = defaults['epf_rate']
                    st.session_state.expenses = defaults['expenses']
                    st.session_state.deductions_list = defaults['deductions']
                    st.toast(f"✨ New Month: {selected_month} {selected_year} (Reset to Default)", icon="🆕")

                st.session_state.loaded_salary = st.session_state["basic_salary"]
                st.session_state.loaded_allowances = st.session_state["allowances"]
                st.session_state.loaded_var = st.session_state["variable_income"]
                st.session_state.loaded_savings = st.session_state["current_savings"]
                st.session_state.loaded_epf = st.session_state["epf_rate"]
                st.session_state.last_viewed_month = selected_month
                st.session_state.last_viewed_year = selected_year
                st.rerun()

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
        edited_expenses = st.data_editor(
            df_expenses_input, 
            num_rows="dynamic", 
            use_container_width=True, 
            key="expenses_editor", 
            column_config={
                "Category": st.column_config.TextColumn("Expense Category"), 
                "Amount": st.column_config.NumberColumn("Amount (RM)", format="%.2f")
            }
        )
        st.session_state.expenses = edited_expenses.to_dict('records')
        total_living_expenses = edited_expenses['Amount'].sum() if not edited_expenses.empty else 0.0
        st.markdown(f"#### Total Expenses: <span style='color:#e74c3c'>RM {total_living_expenses:.2f}</span>", unsafe_allow_html=True)

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

    with st.container(border=True):
        t_col1, t_col2 = st.columns([3, 1])
        t_col1.subheader("📈 Wealth Projection")
        
        duration_option = t_col2.selectbox("Projection", ["1 Year", "3 Years", "5 Years", "10 Years"], index=1)
        duration_map = {"1 Year": 12, "3 Years": 36, "5 Years": 60, "10 Years": 120}
        months_to_project = duration_map[duration_option]
        years_count = months_to_project // 12

        t_col2.markdown("**Inflation Scenarios**")
        t_col2.caption("Adjust rates for each year:")
        
        default_rates = [{"Year": i+1, "Inflation (%)": 3.0} for i in range(years_count)]
        df_rates_input = pd.DataFrame(default_rates)
        
        edited_rates = t_col2.data_editor(
            df_rates_input, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Year": st.column_config.NumberColumn(format="%d"),
                "Inflation (%)": st.column_config.NumberColumn(format="%.1f%%")
            }
        )
        
        yearly_rates_list = [x / 100 for x in edited_rates["Inflation (%)"].tolist()]

        future = []
        acc = current_savings
        cumulative_deflator = 1.0 
        
        for m in range(months_to_project):
            current_year_idx = m // 12
            if current_year_idx < len(yearly_rates_list):
                current_annual_rate = yearly_rates_list[current_year_idx]
            else:
                current_annual_rate = 0.03
                
            monthly_inflation = current_annual_rate / 12
            acc += balance
            cumulative_deflator *= (1 + monthly_inflation)
            real_value = acc / cumulative_deflator
            
            future.append({
                "Month": m+1, 
                "Nominal Wealth": acc,
                "Real Purchasing Power": real_value
            })
        
        df_future = pd.DataFrame(future)
        df_melted = df_future.melt(id_vars=["Month"], var_name="Metric", value_name="Amount")
        
        fig2 = px.line(
            df_melted, 
            x="Month", 
            y="Amount", 
            color="Metric",
            color_discrete_map={
                "Nominal Wealth": "#2ecc71", 
                "Real Purchasing Power": "#e74c3c"
            }
        )
        fig2.update_traces(fill='tozeroy', selector=dict(name="Nominal Wealth"))
        fig2.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0), legend=dict(orientation="h", y=1.1, title=None))
        t_col1.plotly_chart(fig2, use_container_width=True)

    # --- CLOUD DATABASE (UPDATED) ---
    with st.container(border=True):
        st.subheader("☁️ Cloud Database")
        db_col1, db_col2 = st.columns(2)
        
        current_data = {
            "Date": datetime(selected_year, months.index(selected_month)+1, 1).strftime("%Y-%m-%d"),
            "Month": selected_month, 
            "Year": selected_year,
            "Net_Income": net, 
            "Total_Expenses": total_exp, 
            "Balance": balance, 
            "EPF_Savings": epf_amount,
            "Basic_Salary": basic_salary,
            "Allowances": allowances,
            "Variable_Income": variable_income,
            "Current_Savings": current_savings,
            "EPF_Rate": epf_rate,
            "Expenses_JSON": json.dumps(st.session_state.expenses),
            "Deductions_JSON": json.dumps(st.session_state.deductions_list)
        }
        
        with db_col1:
            if st.button(f"Save {selected_month} {selected_year} Record"):
                with st.spinner("Saving full record..."):
                    save_row_to_history(current_data)
                    st.success("Record Saved!")
                    st.session_state.last_viewed_month = selected_month
                    st.rerun()

        st.divider()
        
        # --- NEW: LOAD & DELETE SECTIONS ---
        df_hist = get_sheet_data("History")
        if not df_hist.empty and 'Month' in df_hist.columns and 'Year' in df_hist.columns:
            df_hist['Label'] = df_hist['Month'] + " " + df_hist['Year'].astype(str)
            
            c_load, c_del = st.columns(2)
            
            # 1. LOAD RECORD (JUMP BACK)
            with c_load:
                st.caption("📂 Load / Jump to Record")
                record_to_load = st.selectbox("Select Record", df_hist['Label'].unique(), index=None, placeholder="Choose past month...", key="loader_box")
                if st.button("Load Record", key="btn_load"):
                    if record_to_load:
                        with st.spinner("Loading..."):
                            row = df_hist[df_hist['Label'] == record_to_load].iloc[0]
                            # Update Session Keys
                            st.session_state["month_select"] = row['Month']
                            st.session_state["year_input"] = int(row['Year'])
                            
                            st.session_state["basic_salary"] = float(row.get('Basic_Salary', 0))
                            st.session_state["allowances"] = float(row.get('Allowances', 0))
                            st.session_state["variable_income"] = float(row.get('Variable_Income', 0))
                            st.session_state["current_savings"] = float(row.get('Current_Savings', 0))
                            st.session_state["epf_rate"] = int(row.get('EPF_Rate', 11))
                            st.session_state.expenses = json.loads(row.get('Expenses_JSON', '[]'))
                            st.session_state.deductions_list = json.loads(row.get('Deductions_JSON', '[]'))
                            
                            # Sync Helpers
                            st.session_state.loaded_salary = st.session_state["basic_salary"]
                            st.session_state.loaded_allowances = st.session_state["allowances"]
                            st.session_state.loaded_var = st.session_state["variable_income"]
                            st.session_state.loaded_savings = st.session_state["current_savings"]
                            st.session_state.loaded_epf = st.session_state["epf_rate"]
                            st.session_state.loaded_month = row['Month']
                            st.session_state.loaded_year = int(row['Year'])
                            st.session_state.last_viewed_month = row['Month']
                            st.session_state.last_viewed_year = int(row['Year'])
                            
                            st.rerun()

            # 2. DELETE RECORD
            with c_del:
                st.caption("🗑️ Delete Record")
                to_delete = st.multiselect("Select Record", df_hist['Label'].unique(), key="deleter_box")
                if st.button("Delete Selected", key="btn_del"):
                    if to_delete:
                        delete_rows_from_sheet("History", to_delete)
                        st.success("Deleted!")
                        st.rerun()

            st.caption("History Trend")
            if 'Date' in df_hist.columns:
                df_hist['Date'] = pd.to_datetime(df_hist['Date'])
                df_hist = df_hist.sort_values('Date')
                fig_hist = px.line(df_hist, x='Date', y=['Net_Income', 'Balance'], markers=True, height=250)
                st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No history found in Cloud.")

    # --- AI FINANCIAL AUDITOR ---
    st.markdown("###")
    with st.container():
        st.markdown("""<div style="background-color: #0f172a; padding: 20px; border-radius: 10px; color: white; border: 1px solid #334155; margin-bottom: 10px;">
            <h3 style="margin:0;">✨ AI Financial Auditor</h3></div>""", unsafe_allow_html=True)
        selected_auditor_model = st.selectbox("Select AI Model", st.session_state.available_models, key="auditor_model_select")
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
                    with st.spinner(f"Asking {selected_auditor_model}..."):
                        response = client.models.generate_content(model=selected_auditor_model, contents=prompt)
                        st.markdown(f"""<div style="background-color: #1e293b; padding: 20px; border-radius: 10px; color: #e2e8f0; border-left: 5px solid #8b5cf6;">{response.text}</div>""", unsafe_allow_html=True)
                except Exception as e: st.error(f"Error: {e}")
