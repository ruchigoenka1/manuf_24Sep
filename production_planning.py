import streamlit as st
import pandas as pd
import pulp
import plotly.express as px
import graphviz
from datetime import timedelta

# 1. AUTHENTICATION CHECK
if not st.session_state.get("authentication_status"):
    st.warning("Please log in from the main app page.")
    st.stop()

# 2. PAGE CONTENT (Formerly Tab 1)
st.title("Production Planning")
st.subheader("📋 Step 1: Define Job & Process Data")

default_data = pd.DataFrame([
    {"Job": "P1", "Process": "A", "Eligible_Resources": "R1", "Duration": 2, "Preceding_Process": ""},
    # ... rest of your default data ...
])

# ... remaining code from your tab1 block ...

# 3. ACCESSING GLOBAL VARIABLES Example:
if st.button(f"🚀 Run {st.session_state.solver_choice}", type="primary"):
    if st.session_state.solver_choice == "Optimizer":
        solver = pulp.PULP_CBC_CMD(timeLimit=st.session_state.time_limit, msg=False)
        # ... rest of the optimizer logic ...
