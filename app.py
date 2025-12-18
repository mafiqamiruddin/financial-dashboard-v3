import streamlit as st
import pandas as pd
from google import genai
import plotly.express as px
import os
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

# --- SESSION STATE INITIALIZATION ---

# 1. Expenses State
if 'expenses' not in st.session_state:
    st.session_state.expenses = [
        {"Category": "Housing (Rent/Loan)", "Amount": 1500.0},
        {"Category": "Car Loan/Transport", "Amount": 800.0},
        {"Category": "Food & Groceries", "Amount": 1000.0},
        {"Category": "Utilities & Telco", "Amount": 300.0},
        {"Category": "PTPTN / Education Loan", "Amount": 200.0},
        {"Category": "Savings / Investments", "Amount": 500.0},
    ]

# 2. Statutory Deductions State
if 'deductions_list' not in st.session_state:
    st.session_state.deductions_list = [
        {"Category": "SOCSO / PERKESO", "Amount": 19.75},
        {"Category": "EIS / SIP", "Amount": 7.90},
        {"Category": "PCB (Monthly Tax)", "Amount": 300.00},
    ]

# 3. Model State
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

# ================= LEFT COLUMN (INPUTS) =================
with col_left:
    # 1. INCOME & PERIOD CARD (NEW: Month/Year Selection)
    with st.container(border=True):
        st.subheader("📅 Period & Income")
        
        # Date Selection Row
        d_col1, d_col2 = st.columns(2)
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        current_month_index = datetime.now().month - 1
        
        selected_month = d_col1.selectbox("Month", months, index=current_month_index)
        selected_year = d_col2.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year)

        st.divider()
        
        # Income Inputs
        st.caption("Income Details")
        current_savings = st.number_input("Current Savings", value=10000.0, step=1000.0)
        c1, c2 = st.columns(2)
        basic_salary = c1.number_input("Basic Salary", value=6000.0)
        allowances = c1.number_input("Allowances", value=500.0)
        variable_income = c2.number_input("Side Income", value=0.0)

    # 2. STATUTORY DEDUCTIONS CARD
    with st.container(border=True):
        st.subheader("📉 Statutory Deductions")
        
        # EPF Section
        st.caption("Employee Provident Fund (EPF)")
        epf_rate = st.slider("EPF Rate (%)", 0, 20, 11) 
        epf_amount = (basic_salary + allowances) * (epf_rate / 100)
        st.markdown(f"**EPF Amount:** RM {epf_amount:.2f}")
        
        st.divider()
        
        # Other Deductions Table
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
        st.session_state.deductions_list = edited_deductions.to_dict('records')
        
        other_deductions_total = edited_deductions['Amount'].sum() if not edited_deductions.empty else 0
        total_deductions = epf_amount + other_deductions_total
        
        st.markdown(f"#### Total Deducted: <span style='color:#e74c3c'>RM {total_deductions:.2f}</span>", unsafe_allow_html=True)

    # 3. EXPENSES CARD
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

# ================= RIGHT COLUMN (VISUALS) =================
with col_right:
    # CALCS
    gross = basic_salary + allowances + variable_income
    net = gross - total_deductions
    total_exp = edited_expenses['Amount'].sum() if not edited_expenses.empty else 0
    balance = net - total_exp

    # METRICS
    st.markdown(f"### Snapshot: {selected_month} {selected_year}")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Net Disposable Income", f"RM {net:.2f}")
    with c2:
        st.metric("Monthly Surplus", f"RM {balance:.2f}", delta=f"{balance:.2f}")

    # CHART
    with st.container(border=True):
        if not edited_expenses.empty:
            fig = px.pie(edited_expenses, values='Amount', names='Category', hole=0.5, title="Expense Breakdown")
            fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

    # TRAJECTORY
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

    # DATA MANAGEMENT (UPDATED: Uses Selected Date)
    with st.container(border=True):
        st.subheader("💾 Data Management")
        db_col1, db_col2 = st.columns(2)
        
        # Logic to create a proper Date object from Month/Year selection
        month_map = {name: i+1 for i, name in enumerate(months)}
        month_num = month_map[selected_month]
        # Create a date string for sorting (e.g. 2025-10-01)
        date_obj = datetime(selected_year, month_num, 1)
        date_str = date_obj.strftime("%Y-%m-%d")
        
        current_data = {
            "Date": date_str,  # SAVES YOUR SELECTED DATE
            "Month": selected_month,
            "Year": selected_year,
            "Net_Income": net,
            "Total_Expenses": total_exp,
            "Balance": balance,
            "EPF_Savings": epf_amount
        }
        
        with db_col1:
            if st.button(f"Save {selected_month} {selected_year}"):
                file_path = "financial_history.csv"
                new_row = pd.DataFrame([current_data])
                
                if not os.path.exists(file_path):
                    new_row.to_csv(file_path, index=False)
                    st.success(f"Created DB & Saved {selected_month}!")
                else:
                    # Append logic
                    new_row.to_csv(file_path, mode='a', header=False, index=False)
                    st.success(f"Saved {selected_month} {selected_year} to history!")
        
        with db_col2:
            if os.path.exists("financial_history.csv"):
                with open("financial_history.csv", "rb") as f:
                    st.download_button("Download CSV", f, "financial_history.csv", "text/csv")
                    # ... (after the download button code) ...
        
        st.divider()
        st.subheader("📊 Historical Trends")
        
        if os.path.exists("financial_history.csv"):
            history_df = pd.read_csv("financial_history.csv")
            if not history_df.empty:
                # Ensure date is sorted
                history_df['Date'] = pd.to_datetime(history_df['Date'])
                history_df = history_df.sort_values('Date')
                
                # Plot the trend
                fig_history = px.line(
                    history_df, 
                    x='Month', # or 'Date' if you prefer precise dates
                    y=['Net_Income', 'Balance', 'Total_Expenses'], 
                    markers=True,
                    title="My Financial Evolution",
                    color_discrete_map={
                        "Net_Income": "#2ecc71", 
                        "Total_Expenses": "#e74c3c", 
                        "Balance": "#3498db"
                    }
                )
                st.plotly_chart(fig_history, use_container_width=True)
            else:
                st.info("No history data found yet.")
        else:
            st.info("Save your first month to see the trend line!")

    # AI AUDITOR
    st.markdown("###")
    with st.container():
        st.markdown("""
        <div style="background-color: #0f172a; padding: 20px; border-radius: 10px; color: white; border: 1px solid #334155; margin-bottom: 10px;">
            <h3 style="margin:0;">✨ AI Financial Auditor</h3>
            <p style="color: #94a3b8; font-size: 0.9em; margin:0;">Select a model and generate your audit.</p>
        </div>
        """, unsafe_allow_html=True)
        
        selected_model = st.selectbox("Select AI Model", st.session_state.available_models)
        
        if st.button("🚀 Generate Analysis", type="primary"):
            if not api_key:
                st.warning("API Key required.")
            else:
                try:
                    client = genai.Client(api_key=api_key)
                    deduction_txt = "\n".join([f"- {x['Category']}: RM {x['Amount']}" for x in st.session_state.deductions_list])
                    exp_txt = "\n".join([f"- {x['Category']}: RM {x['Amount']}" for x in st.session_state.expenses])
                    
                    prompt = f"""
                    Role: Expert Malaysian Financial Planner.
                    Context: Analysis for {selected_month} {selected_year}.
                    Stats: Net Income: RM {net:.2f}, Expenses: RM {total_exp:.2f}, Balance: RM {balance:.2f}
                    
                    Statutory Deductions:
                    - EPF: RM {epf_amount:.2f}
                    {deduction_txt}
                    
                    Living Expenses:
                    {exp_txt}
                    
                    Provide:
                    1. Leakage Check (KL Cost of Living context)
                    2. Tax Relief Suggestions (Malaysian Context)
                    3. Researcher/Engineering Analogy for financial health.
                    """
                    
                    with st.spinner(f"Asking {selected_model}..."):
                        response = client.models.generate_content(model=selected_model, contents=prompt)
                        st.markdown(f"""
                        <div style="background-color: #1e293b; padding: 20px; border-radius: 10px; color: #e2e8f0; border-left: 5px solid #8b5cf6;">
                            {response.text}
                        </div>
                        """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")
