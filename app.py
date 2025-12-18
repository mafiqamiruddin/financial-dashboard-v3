import streamlit as st
import pandas as pd
from google import genai
import plotly.express as px
import os
import json
from datetime import datetime

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

# --- STATE MANAGEMENT SYSTEM (FIXED) ---
STATE_FILE = "app_state.json"

def save_state_to_file():
    """Saves the current session state to a local JSON file."""
    # We pull directly from the widget keys
    state_data = {
        "expenses": st.session_state.get('expenses', []),
        "deductions_list": st.session_state.get('deductions_list', []),
        "basic_salary": st.session_state.get('basic_salary', 6000.0),
        "allowances": st.session_state.get('allowances', 500.0),
        "variable_income": st.session_state.get('variable_income', 0.0),
        "current_savings": st.session_state.get('current_savings', 10000.0),
        "epf_rate": st.session_state.get('epf_rate', 11),
        "month_select": st.session_state.get('month_select', "December"),
        "year_input": st.session_state.get('year_input', datetime.now().year),
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state_data, f)
    except Exception as e:
        print(f"Auto-save failed: {e}")

def load_state_from_file():
    """Loads the last saved state from the local JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

# --- INITIALIZATION ---
# Load previous state if it exists
saved_state = load_state_from_file()

# 1. Restore Tables (Expenses & Deductions)
if saved_state:
    if 'expenses' not in st.session_state: 
        st.session_state.expenses = saved_state.get('expenses')
    if 'deductions_list' not in st.session_state: 
        st.session_state.deductions_list = saved_state.get('deductions_list')
else:
    # Defaults for first-time run
    if 'expenses' not in st.session_state:
        st.session_state.expenses = [
            {"Category": "Housing (Rent/Loan)", "Amount": 1500.0},
            {"Category": "Car Loan/Transport", "Amount": 800.0},
            {"Category": "Food & Groceries", "Amount": 1000.0},
            {"Category": "Utilities & Telco", "Amount": 300.0},
            {"Category": "PTPTN / Education Loan", "Amount": 200.0},
            {"Category": "Savings / Investments", "Amount": 500.0},
        ]
    if 'deductions_list' not in st.session_state:
        st.session_state.deductions_list = [
            {"Category": "SOCSO / PERKESO", "Amount": 19.75},
            {"Category": "EIS / SIP", "Amount": 7.90},
            {"Category": "PCB (Monthly Tax)", "Amount": 300.00},
        ]

if 'available_models' not in st.session_state:
    st.session_state.available_models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None

    if not api_key:
        api_key = st.text_input("Enter Gemini API Key", type="password")
        if api_key:
            st.session_state.temp_key = api_key
    else:
        st.success("API Key loaded from Secrets! 🔒")

    st.divider()
    if st.button("🛠️ Check Available Models"):
        if not api_key:
            st.error("Please enter API Key first.")
        else:
            try:
                client = genai.Client(api_key=api_key)
                models = client.models.list()
                fetched = [m.name.replace("models/", "") for m in models if "gemini" in m.name and "embedding" not in m.name]
                if fetched:
                    st.session_state.available_models = sorted(fetched)
                    st.success(f"Found {len(fetched)} models!")
            except Exception as e:
                st.error(f"Connection Error: {e}")

# --- MAIN LAYOUT ---
col_left, col_right = st.columns([1, 1.5], gap="large")

# ================= LEFT COLUMN =================
with col_left:
    with st.container(border=True):
        st.subheader("📅 Period & Income")
        
        # DATE INPUTS
        d_col1, d_col2 = st.columns(2)
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        
        # Determine defaults
        if saved_state and 'month_select' in saved_state:
            try:
                def_month_idx = months.index(saved_state['month_select'])
            except:
                def_month_idx = datetime.now().month - 1
        else:
            def_month_idx = datetime.now().month - 1

        def_year = saved_state.get('year_input', datetime.now().year) if saved_state else datetime.now().year

        # KEY arguments allow automatic state binding
        selected_month = d_col1.selectbox("Month", months, index=def_month_idx, key="month_select")
        selected_year = d_col2.number_input("Year", min_value=2020, max_value=2030, value=def_year, key="year_input")

        st.divider()
        
        # INCOME INPUTS
        # We load defaults from file, but rely on 'key=' to handle updates
        def_savings = saved_state.get('current_savings', 10000.0) if saved_state else 10000.0
        def_salary = saved_state.get('basic_salary', 6000.0) if saved_state else 6000.0
        def_allowance = saved_state.get('allowances', 500.0) if saved_state else 500.0
        def_var = saved_state.get('variable_income', 0.0) if saved_state else 0.0

        current_savings = st.number_input("Current Savings", value=def_savings, step=1000.0, key="current_savings")
        c1, c2 = st.columns(2)
        basic_salary = c1.number_input("Basic Salary", value=def_salary, key="basic_salary")
        allowances = c1.number_input("Allowances", value=def_allowance, key="allowances")
        variable_income = c2.number_input("Side Income", value=def_var, key="variable_income")

    with st.container(border=True):
        st.subheader("📉 Statutory Deductions")
        
        def_epf = saved_state.get('epf_rate', 11) if saved_state else 11
        epf_rate = st.slider("EPF Rate (%)", 0, 20, def_epf, key="epf_rate") 
        epf_amount = (basic_salary + allowances) * (epf_rate / 100)
        st.markdown(f"**EPF Amount:** RM {epf_amount:.2f}")
        
        st.divider()
        st.caption("Other Deductions (Editable)")
        
        df_deductions_input = pd.DataFrame(st.session_state.deductions_list)
        edited_deductions = st.data_editor(
            df_deductions_input,
            num_rows="dynamic",
            use_container_width=True,
            key="deductions_editor",
            column_config={
                "Category": st.column_config.TextColumn("Deduction Name"),
                "Amount": st.column_config.NumberColumn("Amount (RM)", format="%.2f")
            }
        )
        # Immediate Update
        st.session_state.deductions_list = edited_deductions.to_dict('records')
        
        other_deductions_total = edited_deductions['Amount'].sum() if not edited_deductions.empty else 0
        total_deductions = epf_amount + other_deductions_total
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

# ================= RIGHT COLUMN =================
with col_right:
    # Calculations
    gross = basic_salary + allowances + variable_income
    net = gross - total_deductions
    total_exp = edited_expenses['Amount'].sum() if not edited_expenses.empty else 0
    balance = net - total_exp

    # Metrics
    st.markdown(f"### Snapshot: {selected_month} {selected_year}")
    c1, c2 = st.columns(2)
    with c1: st.metric("Net Disposable Income", f"RM {net:.2f}")
    with c2: st.metric("Monthly Surplus", f"RM {balance:.2f}", delta=f"{balance:.2f}")

    # Charts
    with st.container(border=True):
        if not edited_expenses.empty:
            fig = px.pie(edited_expenses, values='Amount', names='Category', hole=0.5, title="Expense Breakdown")
            fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

    with st.container(border=True):
        t_col1, t_col2 = st.columns([3, 1])
        t_col1.subheader("📈 Wealth Projection")
        duration_option = t_col2.selectbox("Projection", ["1 Year", "3 Years", "5 Years", "10 Years"], index=2)
        duration_map = {"1 Year": 12, "3 Years": 36, "5 Years": 60, "10 Years": 120}
        months_to_project = duration_map[duration_option]
        
        future = []
        acc = current_savings
        for m in range(months_to_project):
            acc += balance
            future.append({"Month": m+1, "Wealth": acc})
        
        fig2 = px.area(pd.DataFrame(future), x="Month", y="Wealth", color_discrete_sequence=['#2ecc71'])
        fig2.update_layout(height=250, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig2, use_container_width=True)

    # Data Management & History
    with st.container(border=True):
        st.subheader("💾 Data Management")
        db_col1, db_col2 = st.columns(2)
        month_map = {name: i+1 for i, name in enumerate(months)}
        date_str = datetime(selected_year, month_map[selected_month], 1).strftime("%Y-%m-%d")
        
        current_data = {
            "Date": date_str, "Month": selected_month, "Year": selected_year,
            "Net_Income": net, "Total_Expenses": total_exp, "Balance": balance, "EPF_Savings": epf_amount
        }
        
        with db_col1:
            if st.button(f"Save {selected_month} {selected_year}"):
                file_path = "financial_history.csv"
                new_row = pd.DataFrame([current_data])
                if not os.path.exists(file_path):
                    new_row.to_csv(file_path, index=False)
                else:
                    new_row.to_csv(file_path, mode='a', header=False, index=False)
                st.success("Saved to history!")

        with db_col2:
            if os.path.exists("financial_history.csv"):
                with open("financial_history.csv", "rb") as f:
                    st.download_button("Download CSV", f, "financial_history.csv", "text/csv")
        
        # HISTORICAL TREND CHART
        st.divider()
        if os.path.exists("financial_history.csv"):
            history_df = pd.read_csv("financial_history.csv")
            if not history_df.empty:
                history_df['Date'] = pd.to_datetime(history_df['Date'])
                history_df = history_df.sort_values('Date')
                fig_hist = px.line(history_df, x='Date', y=['Net_Income', 'Balance'], markers=True, title="History Trend", height=250)
                st.plotly_chart(fig_hist, use_container_width=True)

    # AI Section
    st.markdown("###")
    with st.container():
        st.markdown("""<div style="background-color: #0f172a; padding: 20px; border-radius: 10px; color: white; border: 1px solid #334155; margin-bottom: 10px;">
            <h3 style="margin:0;">✨ AI Financial Auditor</h3></div>""", unsafe_allow_html=True)
        
        selected_model = st.selectbox("Select AI Model", st.session_state.available_models)
        
        if st.button("🚀 Generate Analysis", type="primary"):
            if not api_key:
                st.warning("API Key required.")
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
                except Exception as e:
                    st.error(f"Error: {e}")

# --- AUTO-SAVE TRIGGER (SAFE) ---
# We simply call save. We DO NOT manually assign session_state variables here.
# The widgets (like st.number_input) have ALREADY updated session_state by this point.
save_state_to_file()
