import streamlit as st
import streamlit_authenticator as stauth
from datetime import datetime

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
    st.warning("Please enter your username and password to access the scheduler")
    st.stop()

# =========================================================================
# INITIALIZE GLOBAL SESSION STATE
# =========================================================================
if "results_df" not in st.session_state:
    st.session_state.results_df = None
    st.session_state.makespan = None
    st.session_state.penalty_msg = ""
if 'seed_counter' not in st.session_state:
    st.session_state.seed_counter = 42

# =========================================================================
# GLOBAL SIDEBAR SETTINGS
# =========================================================================
with st.sidebar:
    st.write(f"Welcome, **{st.session_state.get('name', 'User')}**")
    authenticator.logout("Log Out", "sidebar")
    st.markdown("---")
    
    st.header("⚙️ Global Settings")
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
            min_value=10, max_value=1200, value=120, step=10
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

st.title("Inventory & Manufacturing App")
st.info("👈 Please select a module from the sidebar to begin.")
