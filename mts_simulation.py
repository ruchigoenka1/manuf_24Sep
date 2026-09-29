import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# =========================================================================
# 1. AUTHENTICATION & SESSION STATE CHECK
# =========================================================================
if not st.session_state.get("authentication_status"):
    st.warning("Please log in from the main app page.")
    st.stop()

# Initialize session state for MTS simulation results
if "mts_results" not in st.session_state:
    st.session_state.mts_results = None

# Get global start date for Gantt Chart mapping
project_start_date = st.session_state.get('start_date', datetime.today())

# =========================================================================
# 2. PAGE-SPECIFIC SIDEBAR
# =========================================================================
with st.sidebar:
    st.divider()
    st.header("⚙️ MTS Sim Settings")
    sim_days = st.number_input("Simulation Duration (Days)", min_value=30, max_value=1000, value=365, step=30)
    seed_val = st.number_input("Random Seed", value=42, help="Fixes random demand generation for repeatable results.")

# =========================================================================
# 3. INPUT CONFIGURATION (SKU DEFINITIONS)
# =========================================================================
st.title("Make-to-Stock (MTS) Multi-SKU Simulator")
st.markdown("Define parameters below. **Factory Constraint:** The factory can only manufacture **one SKU at a time**. Orders are processed on a strictly **FIFO (First-In, First-Out)** basis. If the factory is busy, new orders wait in the queue.")

num_skus = st.number_input("Number of SKUs to Simulate", min_value=1, max_value=20, value=2, step=1)

default_skus = []
for i in range(int(num_skus)):
    default_skus.append({
        "SKU": f"SKU_{i+1:02d}",
        "Dist Type": "Normal" if i % 2 == 0 else "Uniform",
        "Avg Demand": 50 + (i * 10),
        "Variation / Range": 15,
        "Order Qty (Q)": 500,
        "Factory Touch Time (Days)": 7,
        "WH Reorder Point (ROP)": 300,
        "Initial WH Inventory": 400,
        "Initial Pipeline (WIP)": 0
    })

df_default = pd.DataFrame(default_skus)

st.subheader("📋 Step 1: SKU Parameter Matrix")
edited_df = st.data_editor(
    df_default, 
    num_rows="dynamic", 
    width="stretch",
    column_config={
        "Dist Type": st.column_config.SelectboxColumn(options=["Normal", "Uniform"])
    }
)

# =========================================================================
# 4. FINITE CAPACITY SIMULATION ENGINE (FIFO)
# =========================================================================
st.markdown("---")

if st.button("🚀 Run MTS Simulation", type="primary"):
    np.random.seed(int(seed_val))
    
    # Extract params into fast lookup dictionaries
    params = {}
    demands = {}
    current_inv = {}
    sales = {}
    inv_levels = {}
    factory_wip_history = {}
    
    for _, row in edited_df.iterrows():
        sku = str(row["SKU"])
        params[sku] = {
            "order_q": int(row["Order Qty (Q)"]),
            "touch_time": int(row["Factory Touch Time (Days)"]),
            "rop": int(row["WH Reorder Point (ROP)"])
        }
        
        avg_d = float(row["Avg Demand"])
        var_d = float(row["Variation / Range"])
        if str(row["Dist Type"]) == "Normal":
            demands[sku] = np.maximum(0, np.random.normal(avg_d, var_d, sim_days)).round()
        else:
            demands[sku] = np.random.uniform(max(0, avg_d - var_d), avg_d + var_d, sim_days).round()
            
        current_inv[sku] = int(row["Initial WH Inventory"])
        sales[sku] = np.zeros(sim_days)
        inv_levels[sku] = np.zeros(sim_days)
        factory_wip_history[sku] = np.zeros(sim_days)

    # Add these two lines right after factory_wip_history[sku] = np.zeros(sim_days)
    wh_receipts_history = {s: np.zeros(sim_days) for s in params.keys()}
    wh_pipeline_history = {s: np.zeros(sim_days) for s in params.keys()}
    
    # State tracking
    pipeline = [] # Transit to WH
    factory_queue = [] # Waiting to be produced
    active_job = None # Currently on the machine
    master_order_log = []
    
    # Pre-load initial WIP into transit pipeline to avoid blocking the factory on day 1
    for _, row in edited_df.iterrows():
        init_pipe = int(row["Initial Pipeline (WIP)"])
        if init_pipe > 0:
            pipeline.append({'sku': str(row["SKU"]), 'qty': init_pipe, 'arrive_at': 1})

    with st.spinner("Simulating finite-capacity factory physics..."):
        # Master Daily Loop
        for day in range(sim_days):
            
            # A. Receive incoming shipments to WH
            for p in pipeline[:]:
                if p['arrive_at'] <= day:
                    current_inv[p['sku']] += p['qty']
                    wh_receipts_history[p['sku']][day] += p['qty'] # ADD THIS LINE
                    pipeline.remove(p)
                    
            # B. Fulfill Demand
            for sku in params.keys():
                today_demand = demands[sku][day]
                sold = min(current_inv[sku], today_demand)
                current_inv[sku] -= sold
                sales[sku][day] = sold
                inv_levels[sku][day] = current_inv[sku]
                
            # C. Check Inventory Position & Trigger Orders
            for sku, p_data in params.items():
                # On order = Factory Queue + Active Job + Pipeline
                q_qty = sum(q['qty'] for q in factory_queue if q['sku'] == sku)
                act_qty = active_job['qty'] if (active_job and active_job['sku'] == sku) else 0
                pipe_qty = sum(p['qty'] for p in pipeline if p['sku'] == sku)
                
                inv_position = current_inv[sku] + q_qty + act_qty + pipe_qty
                
                if inv_position <= p_data["rop"]:
                    # Enter the back of the line (FIFO)
                    factory_queue.append({
                        'sku': sku,
                        'qty': p_data["order_q"],
                        'touch_time': p_data["touch_time"],
                        'remaining': p_data["touch_time"],
                        'order_day': day
                    })
            
            # D. Factory Processing (Single Machine)
            if active_job is not None:
                active_job['remaining'] -= 1
                
                if active_job['remaining'] <= 0:
                    # Job finishes today
                    ready_at = day
                    arrive_at = ready_at + 1 # Arrives at WH next day
                    
                    pipeline.append({
                        'sku': active_job['sku'], 
                        'qty': active_job['qty'], 
                        'arrive_at': arrive_at
                    })
                    
                    master_order_log.append({
                        "SKU": active_job['sku'],
                        "Order Placed (Day)": active_job['order_day'],
                        "Production Start (Day)": active_job['start_day'],
                        "Production End (Day)": ready_at,
                        "WH Receipt (Day)": arrive_at,
                        "Order Qty": active_job['qty'],
                        "Wait Time (Days)": active_job['start_day'] - active_job['order_day'],
                        "Total Cycle Time (Days)": arrive_at - active_job['order_day']
                    })
                    
                    active_job = None # Clear machine
            
            # E. Pull next job if idle
            if active_job is None and len(factory_queue) > 0:
                active_job = factory_queue.pop(0) # FIFO Pull
                active_job['start_day'] = day
                
            # F. Record Daily WIP & Pipeline Tracker
            for sku in params.keys():
                wip = sum(q['qty'] for q in factory_queue if q['sku'] == sku)
                if active_job and active_job['sku'] == sku:
                    wip += active_job['qty']
                factory_wip_history[sku][day] = wip
                
                # # ADD THIS LINE TO TRACK PIPELINE:
                # wh_pipeline_history[sku][day] = sum(p['qty'] for p in pipeline if p['sku'] == sku)
                # UPDATE THIS LINE: Sum factory queue + active job + transit pipeline
                transit_qty = sum(p['qty'] for p in pipeline if p['sku'] == sku)
                wh_pipeline_history[sku][day] = wip + transit_qty

        # Process KPIs
        kpi_results = []
        for sku in params.keys():
            tot_dem = demands[sku].sum()
            tot_sales = sales[sku].sum()
            fill_rate = (tot_sales / tot_dem) * 100 if tot_dem > 0 else 0
            
            kpi_results.append({
                "SKU": sku,
                "Fill Rate (%)": fill_rate,
                "Stockout Days": np.count_nonzero(demands[sku] > sales[sku]),
                "Min Inventory": inv_levels[sku].min(),
                "Max Inventory": inv_levels[sku].max(),
                "Avg Inventory": inv_levels[sku].mean()
            })
            
        # Save results to session state
        st.session_state.mts_results = {
            "kpi_results": kpi_results,
            "inv_levels": inv_levels,
            "factory_wip_history": factory_wip_history,
            "master_order_log": master_order_log,
            "sim_days": sim_days,
            "num_skus_simulated": len(edited_df),
            # ADD THESE 3 LINES:
            "demand_history": demands,
            "wh_receipts_history": wh_receipts_history,
            "wh_pipeline_history": wh_pipeline_history
        }

# =========================================================================
# 5. DASHBOARD & VISUALIZATIONS (Persisted via Session State)
# =========================================================================
if st.session_state.mts_results is not None:
    res = st.session_state.mts_results
    
    st.success(f"Simulation completed for {int(res['sim_days'])} days across {res['num_skus_simulated']} SKUs.")
    
    st.subheader("📊 Warehouse KPI Scorecard")
    df_kpi = pd.DataFrame(res['kpi_results'])
    
    st.dataframe(
        df_kpi.style.format({
            "Fill Rate (%)": "{:.2f}%",
            "Stockout Days": "{:.0f}",
            "Min Inventory": "{:.0f}",
            "Max Inventory": "{:.0f}",
            "Avg Inventory": "{:.1f}"
        }).background_gradient(subset=['Fill Rate (%)'], cmap='RdYlGn', vmin=80, vmax=100)
          .background_gradient(subset=['Stockout Days'], cmap='Reds', vmin=0, vmax=res['sim_days']*0.1),
        width="stretch", hide_index=True
    )
    
    st.markdown("---")
    st.subheader("📈 Multi-Echelon Trajectory Analysis")
    
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("#### Warehouse: Closing Inventory Level")
        fig_wh = go.Figure()
        for sku, data in res['inv_levels'].items():
            fig_wh.add_trace(go.Scatter(x=np.arange(1, res['sim_days'] + 1), y=data, mode='lines', name=sku, opacity=0.8))
        fig_wh.add_hline(y=0, line_width=1, line_color="black")
        fig_wh.update_layout(xaxis_title="Simulation Day", yaxis_title="Units on Hand", template="plotly_white", height=400, hovermode="x unified")
        st.plotly_chart(fig_wh, width="stretch")
        
    with chart_col2:
        st.markdown("#### Factory: Active & Queued Backlog")
        st.caption("Volume waiting in queue + actively on the machine.")
        fig_fac = go.Figure()
        for sku, data in res['factory_wip_history'].items():
            fig_fac.add_trace(go.Scatter(x=np.arange(1, res['sim_days'] + 1), y=data, mode='lines', line_shape='hv', name=sku, opacity=0.8))
        fig_fac.update_layout(xaxis_title="Simulation Day", yaxis_title="Units Backlogged", template="plotly_white", height=400, hovermode="x unified")
        st.plotly_chart(fig_fac, width="stretch")
        
    # =========================================================================
    # 6. MANUFACTURING & ORDER LOGS
    # =========================================================================
    st.markdown("---")

    # =========================================================================
    # NEW BLOCK: WAREHOUSE DAILY LEDGER
    # =========================================================================
    st.markdown("---")
    st.subheader("📦 Daily Warehouse Ledger")
    
    sku_list_wh = list(res['inv_levels'].keys())
    selected_wh_sku = st.selectbox("Select SKU to view daily warehouse movement:", sku_list_wh)
    
    if selected_wh_sku:
        days_array = np.arange(1, res['sim_days'] + 1)
        closing = res['inv_levels'][selected_wh_sku]
        demands_arr = res['demand_history'][selected_wh_sku]
        receipts_arr = res['wh_receipts_history'][selected_wh_sku]
        pipeline_arr = res['wh_pipeline_history'][selected_wh_sku]
        
        # Reverse-calculate Opening Balance (Opening = Closing + Demand - Receipts)
        opening = np.zeros(res['sim_days'])
        opening[0] = closing[0] + demands_arr[0] - receipts_arr[0]
        for i in range(1, res['sim_days']):
            opening[i] = closing[i-1]
            
        df_wh_ledger = pd.DataFrame({
            "Day": days_array,
            "Opening Balance": opening.astype(int),
            "Daily Demand": demands_arr.astype(int),
            "Units Received": receipts_arr.astype(int),
            "Closing Balance": closing.astype(int),
            "Pipeline (In Transit)": pipeline_arr.astype(int)
        })
        
        st.dataframe(df_wh_ledger, width="stretch", hide_index=True)

    
    st.subheader("🏭 Manufacturing & Order Lifecycle Analysis")
    
    if res['master_order_log']:
        df_orders = pd.DataFrame(res['master_order_log'])
        
        tab_gantt, tab_sku, tab_sched, tab_metrics = st.tabs([
            "📊 Factory Gantt Chart",
            "📋 SKU-Wise Order Ledger", 
            "📅 Daily Factory Schedule", 
            "⏱️ Time Distribution Analytics"
        ])
        
        with tab_gantt:
            st.markdown("#### Factory Manufacturing Schedule")
            st.caption("Visualizes the sequential FIFO processing on the single factory line.")
            
            df_gantt = df_orders.copy()
            df_gantt["Start Date"] = project_start_date + pd.to_timedelta(df_gantt["Production Start (Day)"], unit="d")
            df_gantt["Finish Date"] = project_start_date + pd.to_timedelta(df_gantt["Production End (Day)"], unit="d")
            df_gantt["Order Formatted"] = df_gantt.apply(lambda r: f"{r['Order Qty']} units", axis=1)

            fig_gantt = px.timeline(
                df_gantt, 
                x_start="Start Date", 
                x_end="Finish Date", 
                y="SKU", 
                color="SKU",
                text="Order Formatted",
                hover_data={"Wait Time (Days)": True, "Total Cycle Time (Days)": True}
            )
            fig_gantt.update_yaxes(autorange="reversed")
            fig_gantt.update_layout(template="plotly_white", height=400)
            st.plotly_chart(fig_gantt, width="stretch")

        with tab_sku:
            st.markdown("#### Complete Factory Order Book")
            sku_list = list(res['inv_levels'].keys())
            selected_log_sku = st.selectbox("Filter Ledger by SKU:", ["All"] + sku_list)
            
            if selected_log_sku == "All":
                st.dataframe(df_orders, width="stretch", hide_index=True)
            else:
                st.dataframe(df_orders[df_orders["SKU"] == selected_log_sku], width="stretch", hide_index=True)
                
        with tab_sched:
            st.markdown("#### Active Production Schedule")
            
            active_days = []
            for _, order in df_orders.iterrows():
                for d in range(order["Production Start (Day)"], order["Production End (Day)"]):
                    active_days.append({
                        "Day": d, 
                        "Date": (project_start_date + timedelta(days=d)).strftime('%Y-%m-%d'),
                        "SKU in Production": order["SKU"], 
                        "Batch Qty": order["Order Qty"]
                    })
                    
            if active_days:
                df_schedule = pd.DataFrame(active_days).sort_values(by=["Day"])
                st.dataframe(df_schedule, width="stretch", hide_index=True)
                
        with tab_metrics:
            st.markdown("#### Lead Time & Wait Time Distributions")
            
            df_time_summary = df_orders.groupby("SKU").agg({
                "Wait Time (Days)": ["mean", "max"],
                "Total Cycle Time (Days)": ["mean", "max"]
            }).round(1)
            
            df_time_summary.columns = ["Avg Wait Time", "Max Wait Time", "Avg Total Cycle Time", "Max Total Cycle Time"]
            st.dataframe(df_time_summary.reset_index(), width="stretch", hide_index=True)
            
            fig_cycle = px.box(
                df_orders, x="SKU", y="Total Cycle Time (Days)", 
                color="SKU", points="all",
                title="Total Cycle Time Distribution (Order Placed to WH Receipt)"
            )
            fig_cycle.update_layout(template="plotly_white", showlegend=False, height=400)
            st.plotly_chart(fig_cycle, width="stretch")
            
    else:
        st.info("No orders were placed during this simulation period (Inventory never dropped below ROP).")
