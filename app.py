import streamlit as st
import streamlit_authenticator as stauth

st.set_page_config(layout="wide", page_title="Inventory & Manufacturing App")

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
# 1. TOP SIDEBAR: WELCOME & LOGOUT
# =========================================================================
with st.sidebar:
    st.write(f"Welcome, **{st.session_state.get('name', 'System Admin')}**")
    authenticator.logout("Log Out", "sidebar")
    st.divider()

# =========================================================================
# 2. MIDDLE SIDEBAR: NAVIGATION MENU
# =========================================================================
prod_plan_page = st.Page("1_Production_Planning.py", title="Production Planning", icon="🗓️")
plot_page = st.Page("plot_page.py", title="Closing Balance Plotter", icon="📈")
# dem_hist_page = st.Page("2_Demand_Histogram.py", title="Demand Histogram Simulator", icon="📊")
# dem_analysis_page = st.Page("3_Demand_Analysis.py", title="Demand Analysis", icon="📈")
# cont_review_page = st.Page("4_Continuous_Review.py", title="Continuous Review Simulator", icon="🔄")
# per_review_page = st.Page("5_Periodic_Review.py", title="Periodic Review Simulator", icon="📅")
# inv_audit_page = st.Page("6_Inventory_Audit.py", title="Inventory Audit", icon="📋")
# inv_kpi_page = st.Page("7_Inventory_KPI.py", title="Inventory KPI & Aging", icon="🎯")
# ccc_map_page = st.Page("8_Cash_Conversion_Cycle.py", title="Cash Conversion Map", icon="🗺️")
# cash_flow_page = st.Page("9_Cash_Flow_Scenario.py", title="Cash Flow & Scenarios", icon="💵")

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
# 3. RUN THE ACTIVE PAGE CONTENT
# =========================================================================
pg.run()
