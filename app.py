import streamlit as st
import streamlit_authenticator as stauth
from datetime import datetime

st.set_page_config(layout="wide", page_title="Advanced Job Scheduler")

# =========================================================================
# SECURE AUTHENTICATION MODULE 
# =========================================================================
config = {
    'credentials': {
        'usernames': {
            'admin': {
                'email': 'ashutosh.goenka123@gmail.com',
                'name': 'System Admin',
                'password': '$2b$12$93MC4ONIi0.6QXjnL9uGveabXcSb1jCkauE4UiR68KeA5/0HRTyCK'
            },
        }
    },
    'cookie': {
        'expiry_days': 1, 
        'key': 'random_secret_signature_key_here', 
        'name': 'job_scheduler_cookie'
    }
}

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

try:
    authenticator.login()
except Exception as e:
    st.error(e)

if st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect")
    st.stop()
elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your username and password to access the app")
    st.stop()

# =========================================================================
# GLOBAL SESSION STATE INITIALIZATION 
# =========================================================================
if "results_df" not in st.session_state:
    st.session_state.results_df = None
    st.session_state.makespan = None
    st.session_state.penalty_msg = ""

if 'seed_counter' not in st.session_state:
    st.session_state.seed_counter = 42

# =========================================================================
# 1. APP NAVIGATION (DECLARE FIRST SO IT APPEARS AT THE TOP)
# =========================================================================
prod_plan_page = st.Page("production_planning.py", title="Production Planning", icon="🗓️")
plot_page = st.Page("plot_page.py", title="Closing Balance Plotter", icon="📈")
# dem_hist_page = st.Page("demand_histogram.py", title="Demand Histogram Simulator", icon="📊")
# dem_analysis_page = st.Page("demand_analysis.py", title="Demand Analysis", icon="📈")
# cont_review_page = st.Page("continuous_review.py", title="Continuous Review Simulator", icon="🔄")
# per_review_page = st.Page("periodic_review.py", title="Periodic Review Simulator", icon="📅")
# inv_audit_page = st.Page("inventory_audit.py", title="Inventory Audit", icon="📋")
# inv_kpi_page = st.Page("inventory_kpi.py", title="Inventory KPI & Aging", icon="🎯")
# ccc_map_page = st.Page("cash_conversion_map.py", title="Cash Conversion Map", icon="🗺️")
# cash_flow_page = st.Page("cash_flow_scenario.py", title="Cash Flow & Scenarios", icon="💵")



# Initialize the navigation menu. Streamlit will pin this to the top of the sidebar.
pg = st.navigation([
    prod_plan_page, 
    plot_page,
    # dem_hist_page, 
    # dem_analysis_page, 
    # cont_review_page, 
    # per_review_page, 
    # inv_audit_page, 
    # inv_kpi_page, 
    # ccc_map_page, 
    # cash_flow_page
])

# =========================================================================
# 2. GLOBAL SIDEBAR & ENGINE SETTINGS (RENDERS BELOW NAVIGATION)
# =========================================================================
with st.sidebar:
    st.divider() # Visual break between the navigation menu and settings
    st.write(f"Welcome, **{st.session_state.get('name', 'User')}**")
    authenticator.logout("Log Out", "sidebar")
    st.markdown("---")
    
    st.header("⚙️ Global Settings (Scheduler)")
    st.session_state.start_date = st.date_input("Project Start Date", datetime(2024, 1, 1))

    st.session_state.scheduling_strategy = st.radio(
        "Scheduling Strategy Objective:",
        ("As Soon As Possible (ASAP)", "Just In Time / Close to Due Date")
    )

    st.session_state.solver_choice = st.radio(
        "Select Solving Engine:", 
        ("Optimizer", "Evolutionary Algorithm")
    )

    st.markdown("---")
    st.header("⏱️ Engine Parameters")

    if st.session_state.solver_choice == "Optimizer":
        st.session_state.time_limit = st.number_input(
            "Optimizer Time Limit (Seconds)", 
            min_value=10, max_value=1200, value=120, step=10,
            help="Limits how long the solver searches. Increase if you get timeout errors."
        )
    else:
        st.session_state.ga_generations = st.number_input(
            "No of Generation", 
            min_value=50, max_value=1000, value=100, step=50
        )
        st.session_state.ga_pop_size = st.number_input(
            "Size", 
            min_value=20, max_value=500, value=50, step=10
        )

# =========================================================================
# 3. RUN THE SELECTED PAGE
# =========================================================================
pg.run()
