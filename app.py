import streamlit as st
import pandas as pd
from google import genai
import plotly.express as px
import os
from datetime import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="MY Financial Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR DASHBOARD LOOK ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    .stContainer { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    [data-testid="stMetricValue"] { font-size: 24px; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    /* Make Data Editor look cleaner */
    [data-testid="stDataEditor"] { border: 1px solid #e0e0e0; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE & DATA INIT ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = [
        {"Category": "Housing (Rent/Loan)", "Amount": 1500.0},
        {"Category": "Car Loan/Transport", "Amount": 800.0},
        {"Category": "Food & Groceries", "Amount": 1000.0},
        {"Category": "Utilities & Telco", "Amount": 300.0},
        {"Category": "PTPTN / Education Loan", "Amount": 200.0},
        {"Category": "Savings / Investments", "Amount": 500.0},
    ]

if 'available_models' not in st.session_state:
    st.session_state.available_models = ["gemini-1.5-flash", "gemini-2.0-flash-exp"]

# --- SIDEBAR: SETUP & TOOLS ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # 1. ROBUST API KEY HANDLING
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

    # 2. MODEL CHECKER TOOL
    st.divider()
    st.write("🔧 **System Tools**")
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
    # INCOME CARD
    with st.container(border=True):
        st.subheader("💰 Income & Savings")
        current_savings = st.number_input("Current Savings", value=10000.0, step=1000.0)
        c1, c2 = st.columns(2)
        basic_salary = c1.number_input("Basic Salary", value=6000.0)
        allowances = c1.number_input("Allowances", value=500.0)
        variable_income = c2.number_input("Side Income", value=0.0)

    # DEDUCTIONS CARD
    with st.container(border=True):
        st.subheader("📉 Statutory Deductions")
        epf_rate = st.slider("EPF Rate (%)", 9, 11, 11)
        c1, c2, c3 = st.columns(3)
        socso = c1.number_input("SOCSO", value=19.75)
        eis = c2.number_input("EIS", value=7.90)
        pcb = c3.number_input("PCB", value=300.0)
        
        epf_amt = (basic_salary + allowances) * (epf_rate/100)
        total_deductions = epf_amt + socso + eis + pcb
        st.caption(f"Total Deducted: RM {total_deductions:.2f}")

    # EXPENSES CARD (UPDATED: EDITABLE TABLE)
    with st.container(border=True):
        st.subheader("🧾 Living Expenses")
        st.info("💡 Tip: Click any cell to edit. Use the bottom row to add new items.")
        
        # Convert session state to DataFrame
        df_expenses_input = pd.DataFrame(st.session_state.expenses)
        
        # The Data Editor Widget (Solves Problem #1)
        edited_df = st.data_editor(
            df_expenses_input,
            num_rows="dynamic", # Allows adding/deleting rows
            use_container_width=True,
            column_config={
                "Category": st.column_config.TextColumn("Expense Category"),
                "Amount": st.column_config.NumberColumn("Amount (RM)", format="%.2f")
            }
        )
        
        # Sync changes back to Session State immediately
        st.session_state.expenses = edited_df.to_dict('records')

# ================= RIGHT COLUMN (VISUALS) =================
with col_right:
    # CALCS
    gross = basic_salary + allowances + variable_income
    net = gross - total_deductions
    # Recalculate based on the Edited Dataframe
    total_exp = edited_df['Amount'].sum() if not edited_df.empty else 0
    balance = net - total_exp

    # METRICS ROW
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Net Disposable", f"RM {net:.2f}")
    with c2:
        st.metric("Monthly Surplus", f"RM {balance:.2f}", delta=f"{balance:.2f}")

    # CHART ROW
    with st.container(border=True):
        if not edited_df.empty:
            fig = px.pie(edited_df, values='Amount', names='Category', hole=0.5, title="Expense Breakdown")
            fig.update_layout(height=300, margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

    # WEALTH TRAJECTORY (UPDATED: DYNAMIC SELECTION)
    with st.container(border=True):
        t_col1, t_col2 = st.columns([3, 1])
        t_col1.subheader("📈 Wealth Projection")
        
        # Selector for Duration (Solves Problem #3)
        duration_option = t_col2.selectbox("Projection", ["1 Year", "3 Years", "5 Years", "10 Years"], index=2)
        
        # Map selection to months
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

    # DATABASE SECTION (UPDATED: RESTORED CSV FEATURE)
    with st.container(border=True):
        st.subheader("💾 Data Management")
        
        db_col1, db_col2 = st.columns(2)
        
        # Prepare Current Data Row
        current_data = {
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Month": datetime.now().strftime("%B"),
            "Net_Income": net,
            "Total_Expenses": total_exp,
            "Balance": balance,
            "EPF_Savings": (basic_salary + allowances) * (epf_rate/100)
        }
        
        with db_col1:
            if st.button("Save Month to History"):
                file_path = "financial_history.csv"
                new_row = pd.DataFrame([current_data])
                if not os.path.exists(file_path):
                    new_row.to_csv(file_path, index=False)
                    st.success("Created new DB!")
                else:
                    new_row.to_csv(file_path, mode='a', header=False, index=False)
                    st.success("Saved successfully!")
        
        with db_col2:
            if os.path.exists("financial_history.csv"):
                with open("financial_history.csv", "rb") as f:
                    st.download_button(
                        label="Download CSV",
                        data=f,
                        file_name="financial_history.csv",
                        mime="text/csv"
                    )

    # AI AUDITOR SECTION (The "Dark Card")
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
                    # Prompt Logic
                    exp_txt = "\n".join([f"- {x['Category']}: RM {x['Amount']}" for x in st.session_state.expenses])
                    prompt = f"""
                    Role: Expert Malaysian Financial Planner.
                    Stats: Net Income: RM {net:.2f}, Expenses: RM {total_exp:.2f}, Balance: RM {balance:.2f}
                    Expenses:
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