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

if "mts_results" not in st.session_state:
    st.session_state.mts_results = None

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
st.markdown("Define parameters below. **Factory Constraint:** The factory can only manufacture **one SKU at a time**. Orders are processed on a strictly **FIFO (First-In, First-Out)** basis.")

num_skus = st.number_input("Number of SKUs to Simulate", min_value=1, max_value=20, value=4, step=1)

default_demands = [50, 60, 70, 80]
default_skus = []

for i in range(int(num_skus)):
    avg_d = default_demands[i] if i < len(default_demands) else 50 + (i * 10)
    default_skus.append({
        "SKU": f"SKU_{i+1:02d}",
        "Dist Type": "Uniform",
        "Avg Demand": avg_d,
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
    num_rows="fixed", 
    width="stretch",
    column_config={"Dist Type": st.column_config.SelectboxColumn(options=["Normal", "Uniform"])}
)

# =========================================================================
# CAPACITY UTILIZATION CHECK
# =========================================================================
total_util_pct = 0
for _, row in edited_df.iterrows():
    touch_time = float(row["Factory Touch Time (Days)"])
    if touch_time > 0:
        daily_capacity = float(row["Order Qty (Q)"]) / touch_time
        total_util_pct += (float(row["Avg Demand"]) / daily_capacity) * 100

if total_util_pct > 100:
    st.error(f"⚠️ **Capacity Overload:** With this data, the estimated factory capacity utilization is **{total_util_pct:.1f}%**. The factory will constantly run behind demand.")
else:
    st.info(f"✅ **Capacity Check:** With this data, the estimated factory capacity utilization is **{total_util_pct:.1f}%**.")

# =========================================================================
# 4. CORE SIMULATION ENGINE (WRAPPED IN A REUSABLE FUNCTION)
# =========================================================================
def run_mts_simulation(df_inputs, duration, seed, rop_overrides=None):
    np.random.seed(int(seed))
    
    params = {}
    demands = {}
    current_inv = {}
    sales = {}
    inv_levels = {}
    factory_wip_history = {}
    
    for _, row in df_inputs.iterrows():
        sku = str(row["SKU"])
        assigned_rop = rop_overrides[sku] if (rop_overrides and sku in rop_overrides) else int(row["WH Reorder Point (ROP)"])
        
        params[sku] = {
            "order_q": int(row["Order Qty (Q)"]),
            "touch_time": int(row["Factory Touch Time (Days)"]),
            "rop": assigned_rop
        }
        
        avg_d = float(row["Avg Demand"])
        var_d = float(row["Variation / Range"])
        if str(row["Dist Type"]) == "Normal":
            demands[sku] = np.maximum(0, np.random.normal(avg_d, var_d, duration)).round()
        else:
            demands[sku] = np.random.uniform(max(0, avg_d - var_d), avg_d + var_d, duration).round()
            
        current_inv[sku] = int(row["Initial WH Inventory"])
        sales[sku] = np.zeros(duration)
        inv_levels[sku] = np.zeros(duration)
        factory_wip_history[sku] = np.zeros(duration)

    wh_receipts_history = {s: np.zeros(duration) for s in params.keys()}
    wh_pipeline_history = {s: np.zeros(duration) for s in params.keys()}
    pending_orders_history = {s: np.zeros(duration) for s in params.keys()}
    pending_days_history = {s: np.zeros(duration) for s in params.keys()}
    
    pipeline = []
    factory_queue = []
    active_job = None
    master_order_log = []
    
    for _, row in df_inputs.iterrows():
        init_pipe = int(row["Initial Pipeline (WIP)"])
        if init_pipe > 0:
            pipeline.append({'sku': str(row["SKU"]), 'qty': init_pipe, 'arrive_at': 1})

    for day in range(duration):
        for p in pipeline[:]:
            if p['arrive_at'] <= day:
                current_inv[p['sku']] += p['qty']
                wh_receipts_history[p['sku']][day] += p['qty']
                pipeline.remove(p)
                
        for sku in params.keys():
            today_demand = demands[sku][day]
            sold = min(current_inv[sku], today_demand)
            current_inv[sku] -= sold
            sales[sku][day] = sold
            inv_levels[sku][day] = current_inv[sku]
            
        for sku, p_data in params.items():
            q_qty = sum(q['qty'] for q in factory_queue if q['sku'] == sku)
            act_qty = active_job['qty'] if (active_job and active_job['sku'] == sku) else 0
            pipe_qty = sum(p['qty'] for p in pipeline if p['sku'] == sku)
            
            inv_position = current_inv[sku] + q_qty + act_qty + pipe_qty
            
            if inv_position <= p_data["rop"]:
                factory_queue.append({
                    'sku': sku, 'qty': p_data["order_q"], 'touch_time': p_data["touch_time"],
                    'remaining': p_data["touch_time"], 'order_day': day
                })
        
        if active_job is not None:
            active_job['remaining'] -= 1
            if active_job['remaining'] <= 0:
                ready_at = day
                arrive_at = ready_at + 1 
                pipeline.append({'sku': active_job['sku'], 'qty': active_job['qty'], 'arrive_at': arrive_at})
                master_order_log.append({
                    "SKU": active_job['sku'], "Order Placed (Day)": active_job['order_day'],
                    "Production Start (Day)": active_job['start_day'], "Production End (Day)": ready_at,
                    "WH Receipt (Day)": arrive_at, "Order Qty": active_job['qty'],
                    "Wait Time (Days)": active_job['start_day'] - active_job['order_day'],
                    "Total Cycle Time (Days)": arrive_at - active_job['order_day']
                })
                active_job = None 
        
        if active_job is None and len(factory_queue) > 0:
            active_job = factory_queue.pop(0) 
            active_job['start_day'] = day
            
        for sku in params.keys():
            queue_qty = sum(q['qty'] for q in factory_queue if q['sku'] == sku)
            active_qty = active_job['qty'] if (active_job and active_job['sku'] == sku) else 0
            queue_days = sum(q['remaining'] for q in factory_queue if q['sku'] == sku)
            active_days = active_job['remaining'] if (active_job and active_job['sku'] == sku) else 0
            
            total_wip = queue_qty + active_qty
            factory_wip_history[sku][day] = total_wip
            pending_orders_history[sku][day] = total_wip
            pending_days_history[sku][day] = queue_days + active_days
            transit_qty = sum(p['qty'] for p in pipeline if p['sku'] == sku)
            wh_pipeline_history[sku][day] = total_wip + transit_qty

    kpi_results = []
    for sku in params.keys():
        tot_dem = demands[sku].sum()
        tot_sales = sales[sku].sum()
        fill_rate = (tot_sales / tot_dem) * 100 if tot_dem > 0 else 0
        kpi_results.append({
            "SKU": sku, "Fill Rate (%)": fill_rate, "Stockout Days": np.count_nonzero(demands[sku] > sales[sku]),
            "Min Inventory": inv_levels[sku].min(), "Max Inventory": inv_levels[sku].max(), "Avg Inventory": inv_levels[sku].mean()
        })

    return {
        "kpi_results": kpi_results, "inv_levels": inv_levels, "factory_wip_history": factory_wip_history,
        "master_order_log": master_order_log, "sim_days": duration, "num_skus_simulated": len(df_inputs),
        "demand_history": demands, "wh_receipts_history": wh_receipts_history,
        "wh_pipeline_history": wh_pipeline_history, "pending_orders_history": pending_orders_history,
        "pending_days_history": pending_days_history
    }

# =========================================================================
# 5. NEW BLOCK: ITERATIVE HEURISTIC ROP OPTIMIZER
# =========================================================================
st.markdown("---")
st.subheader("🎯 Auto-Optimize Reorder Points (ROP)")
st.markdown("Uses an iterative heuristic search to minimize average inventory while achieving your target service level.")

opt_col1, opt_col2, opt_col3 = st.columns([1, 1, 2])
with opt_col1:
    target_sl = st.number_input("Target Fill Rate (%)", min_value=70.0, max_value=100.0, value=95.0, step=1.0)
with opt_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_opt = st.button("🔍 Run Optimization")

if run_opt:
    if total_util_pct > 100:
        st.warning("Optimization is highly unstable when capacity utilization is over 100%. The factory cannot catch up to demand regardless of ROP.")
    else:
        with st.spinner("Running heuristic optimization loop..."):
            current_rops = {str(row["SKU"]): int(row["WH Reorder Point (ROP)"]) for _, row in edited_df.iterrows()}
            step_sizes = {str(row["SKU"]): max(5, int(row["Order Qty (Q)"] * 0.05)) for _, row in edited_df.iterrows()}
            
            # Baseline capture
            base_res = run_mts_simulation(edited_df, sim_days, seed_val, current_rops)
            base_kpis = {k['SKU']: k for k in base_res['kpi_results']}
            
            max_iters = 15
            for i in range(max_iters):
                sim_res = run_mts_simulation(edited_df, sim_days, seed_val, current_rops)
                df_kpi = pd.DataFrame(sim_res['kpi_results'])
                
                all_met = True
                for _, kpi in df_kpi.iterrows():
                    sku = kpi["SKU"]
                    fr = kpi["Fill Rate (%)"]
                    
                    if fr < target_sl:
                        current_rops[sku] += step_sizes[sku]
                        all_met = False
                    elif fr > (target_sl + 1.5) and current_rops[sku] > step_sizes[sku]: 
                        current_rops[sku] -= step_sizes[sku]
                        all_met = False
                        
                if all_met:
                    break
            
            final_res = run_mts_simulation(edited_df, sim_days, seed_val, current_rops)
            final_kpis = {k['SKU']: k for k in final_res['kpi_results']}
            
            # Prepare Comparison Table
            comp_data = []
            for sku in current_rops.keys():
                comp_data.append({
                    "SKU": sku,
                    "Old ROP": base_kpis[sku]["Avg Inventory"], # just used as placeholder for old rop lookup
                    "Original ROP": int(edited_df.loc[edited_df['SKU'] == sku, 'WH Reorder Point (ROP)'].values[0]),
                    "Optimized ROP": current_rops[sku],
                    "Original Avg Inv": round(base_kpis[sku]["Avg Inventory"], 1),
                    "New Avg Inv": round(final_kpis[sku]["Avg Inventory"], 1),
                    "Final Fill Rate (%)": round(final_kpis[sku]["Fill Rate (%)"], 1)
                })
            
            st.success(f"Optimization completed in {i+1} iterations.")
            st.dataframe(pd.DataFrame(comp_data)[["SKU", "Original ROP", "Optimized ROP", "Original Avg Inv", "New Avg Inv", "Final Fill Rate (%)"]], width="stretch", hide_index=True)
            st.info("💡 To apply these changes, update the ROP values in the Step 1 Matrix above and run the manual simulation below to view the full dashboard.")

# =========================================================================
# 6. MANUAL SIMULATION TRIGGER
# =========================================================================
st.markdown("---")
if st.button("🚀 Run Standard MTS Simulation", type="primary"):
    with st.spinner("Simulating finite-capacity factory physics..."):
        st.session_state.mts_results = run_mts_simulation(edited_df, sim_days, seed_val)

# =========================================================================
# 7. DASHBOARD & VISUALIZATIONS 
# =========================================================================
if st.session_state.mts_results is not None:
    res = st.session_state.mts_results
    
    st.success(f"Simulation dashboard loaded for {int(res['sim_days'])} days across {res['num_skus_simulated']} SKUs.")
    
    with st.expander("📊 Warehouse KPI Scorecard", expanded=True):
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
    
    with st.expander("📈 Multi-Echelon Trajectory Analysis"):
        st.markdown("#### Warehouse: Closing Inventory Level")
        fig_wh = go.Figure()
        for sku, data in res['inv_levels'].items():
            fig_wh.add_trace(go.Scatter(x=np.arange(1, res['sim_days'] + 1), y=data, mode='lines', name=sku, opacity=0.8))
        fig_wh.add_hline(y=0, line_width=1, line_color="black")
        fig_wh.update_layout(xaxis_title="Simulation Day", yaxis_title="Units on Hand", template="plotly_white", height=400, hovermode="x unified")
        st.plotly_chart(fig_wh, width="stretch")
        
        st.markdown("#### Factory: Active & Queued Backlog")
        fig_fac = go.Figure()
        for sku, data in res['factory_wip_history'].items():
            fig_fac.add_trace(go.Scatter(x=np.arange(1, res['sim_days'] + 1), y=data, mode='lines', line_shape='hv', name=sku, opacity=0.8))
        fig_fac.update_layout(xaxis_title="Simulation Day", yaxis_title="Units Backlogged", template="plotly_white", height=400, hovermode="x unified")
        st.plotly_chart(fig_fac, width="stretch")

    with st.expander("📅 Daily Demand Ledger"):
        demand_matrix_data = {"Day": np.arange(1, res['sim_days'] + 1)}
        for sku, arr in res['demand_history'].items():
            demand_matrix_data[sku] = arr.astype(int)
        st.dataframe(pd.DataFrame(demand_matrix_data), width="stretch", hide_index=True)

    with st.expander("📋 Daily Pending Factory Orders (Backlog - Units)"):
        pending_matrix_data = {"Day": np.arange(1, res['sim_days'] + 1)}
        orders_hist = res.get('pending_orders_history', {})
        if orders_hist:
            for sku, arr in orders_hist.items():
                pending_matrix_data[sku] = arr.astype(int)
        st.dataframe(pd.DataFrame(pending_matrix_data), width="stretch", hide_index=True)

    with st.expander("⏱️ Daily Factory Backlog (Processing Days)"):
        pending_days_data = {"Day": np.arange(1, res['sim_days'] + 1)}
        total_days_arr = np.zeros(res['sim_days'])
        
        days_hist = res.get('pending_days_history', {})
        if days_hist:
            for sku, arr in days_hist.items():
                pending_days_data[f"{sku} (Days)"] = arr.astype(int)
                total_days_arr += arr
                
        pending_days_data["Total Backlog (Days)"] = total_days_arr.astype(int)
        pending_days_data["Estimated Clear Day"] = pending_days_data["Day"] + pending_days_data["Total Backlog (Days)"]
        st.dataframe(pd.DataFrame(pending_days_data), width="stretch", hide_index=True)

    with st.expander("📦 Daily Warehouse Movement Ledger"):
        sku_list_wh = list(res['inv_levels'].keys())
        selected_wh_sku = st.selectbox("Select SKU to view daily warehouse movement:", sku_list_wh)
        
        if selected_wh_sku:
            days_array = np.arange(1, res['sim_days'] + 1)
            closing = res['inv_levels'][selected_wh_sku]
            demands_arr = res['demand_history'][selected_wh_sku]
            receipts_arr = res['wh_receipts_history'][selected_wh_sku]
            pipeline_arr = res['wh_pipeline_history'][selected_wh_sku]
            
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

    st.markdown("---")
    st.subheader("🏭 Manufacturing & Order Lifecycle Analysis")
    
    if res['master_order_log']:
        df_orders = pd.DataFrame(res['master_order_log'])
        sku_list_wh = list(res['inv_levels'].keys())
        
        with st.expander("📊 Factory Gantt Chart"):
            df_gantt = df_orders.copy()
            df_gantt["Start Date"] = project_start_date + pd.to_timedelta(df_gantt["Production Start (Day)"], unit="d")
            df_gantt["Finish Date"] = project_start_date + pd.to_timedelta(df_gantt["Production End (Day)"], unit="d")
            df_gantt["Order Formatted"] = df_gantt.apply(lambda r: f"{r['Order Qty']} units", axis=1)

            fig_gantt = px.timeline(
                df_gantt, x_start="Start Date", x_end="Finish Date", y="SKU", color="SKU",
                hover_data={"Wait Time (Days)": True, "Total Cycle Time (Days)": True, "Order Formatted": True}
            )
            fig_gantt.update_yaxes(autorange="reversed")
            fig_gantt.update_layout(template="plotly_white", height=400)
            st.plotly_chart(fig_gantt, width="stretch")

        with st.expander("📋 SKU-Wise Order Ledger"):
            selected_log_sku = st.selectbox("Filter Ledger by SKU:", ["All"] + sku_list_wh)
            if selected_log_sku == "All":
                st.dataframe(df_orders, width="stretch", hide_index=True)
            else:
                st.dataframe(df_orders[df_orders["SKU"] == selected_log_sku], width="stretch", hide_index=True)
                
        with st.expander("📅 Daily Factory Schedule"):
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
                
        with st.expander("⏱️ Time Distribution Analytics"):
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
