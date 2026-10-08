import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import scipy.stats as stats

# Plotly styling
def style_plotly_fig(fig):
    fig.update_layout(
        plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', font=dict(color='white'),
        title_font=dict(color='white'), legend=dict(font=dict(color='white'), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', gridcolor='#2b2b2b')
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', gridcolor='#2b2b2b', rangemode="tozero")
    return fig

st.title("Data-Driven Policy Optimization")
st.write("Upload your historical inventory dataset to analyze cost sensitivities and simulate continuous and periodic review policies.")

# ------------------------------------------------
# File Upload & Global Parameters
# ------------------------------------------------
with st.sidebar:
    st.header("Upload Data")
    uploaded_file = st.file_uploader("Upload Inventory Dataset (Excel/CSV)", type=["xlsx", "xls", "csv"])
    
    st.header("Cost Parameters")
    fixed_ordering_cost = st.number_input("Fixed Ordering Cost ($/order)", value=500.0, step=50.0)
    annual_holding_cost_per_unit = st.number_input("Annual Holding Cost ($/unit/year)", value=20.0, step=1.0)
    
    st.header("Operational Parameters")
    lead_time = st.number_input("Lead Time (Days)", min_value=1, value=3, step=1)
    service_level = st.number_input("Target Service Level (%)", min_value=50.0, max_value=99.99, value=95.0, step=0.1)

if uploaded_file is not None:
    # Read data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    if 'Demand/Sales' not in df.columns:
        st.error("Uploaded file must contain a 'Demand/Sales' column.")
        st.stop()
        
    # Extract dataset metrics
    demand_array = df['Demand/Sales'].fillna(0).values
    total_days = len(demand_array)
    total_demand = np.sum(demand_array)
    avg_daily_demand = np.mean(demand_array)
    std_dev_demand = np.std(demand_array)
    
    # Timeframe adjusted costs
    period_years = total_days / 365.0
    period_holding_cost_per_unit = annual_holding_cost_per_unit * period_years
    z_score = stats.norm.ppf(service_level / 100.0)

    st.success(f"Dataset loaded successfully! Identified **{total_days} days** of data. Timeframe factor: **{period_years:.2f} years**.")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Average Daily Demand", f"{avg_daily_demand:.2f} units")
    c2.metric("Demand Std Dev", f"{std_dev_demand:.2f} units")
    c3.metric("Total Period Demand", f"{total_demand:,.0f} units")
    
    # ------------------------------------------------
    # Continuous Review System (EOQ)
    # ------------------------------------------------
    st.divider()
    st.header("1. Continuous Review System")
    
    # Theoretical Optimization
    if period_holding_cost_per_unit > 0 and fixed_ordering_cost > 0 and total_demand > 0:
        eoq = math.sqrt((2 * total_demand * fixed_ordering_cost) / period_holding_cost_per_unit)
    else:
        eoq = 0
        
    q_range = np.linspace(max(10, eoq * 0.2), eoq * 2, 20).astype(int)
    cr_data = []
    
    for q in q_range:
        avg_inv = q / 2
        num_orders = total_demand / q if q > 0 else 0
        hc = avg_inv * period_holding_cost_per_unit
        oc = num_orders * fixed_ordering_cost
        tc = hc + oc
        cr_data.append([q, num_orders, avg_inv, hc, oc, tc])
        
    df_cr = pd.DataFrame(cr_data, columns=["Order Quantity (Q)", "No of Orders", "Average Inventory", "Holding Cost ($)", "Ordering Cost ($)", "Total Cost ($)"])
    opt_cr = df_cr.loc[df_cr["Total Cost ($)"].idxmin()]
    
    st.subheader("Cost Sensitivity Analysis")
    st.info(f"**Optimal Order Quantity (EOQ):** {opt_cr['Order Quantity (Q)']:.0f} units | **Minimum Total Cost:** ${opt_cr['Total Cost ($)']:,.0f}")
    
    fig_cr = go.Figure()
    fig_cr.add_trace(go.Scatter(x=df_cr["Order Quantity (Q)"], y=df_cr["Holding Cost ($)"], mode="lines", name="Holding Cost", line=dict(color="orange")))
    fig_cr.add_trace(go.Scatter(x=df_cr["Order Quantity (Q)"], y=df_cr["Ordering Cost ($)"], mode="lines", name="Ordering Cost", line=dict(color="cyan")))
    fig_cr.add_trace(go.Scatter(x=df_cr["Order Quantity (Q)"], y=df_cr["Total Cost ($)"], mode="lines", name="Total Cost", line=dict(color="lightgreen", width=3)))
    fig_cr.add_vline(x=opt_cr['Order Quantity (Q)'], line_dash="dash", line_color="white", annotation_text="Min Cost", annotation_position="top right")
    fig_cr.update_layout(title="Continuous Review: Costs vs Order Quantity", xaxis_title="Order Quantity", yaxis_title=f"Cost over {total_days} Days ($)")
    st.plotly_chart(style_plotly_fig(fig_cr), use_container_width=True)
    
    with st.expander("View Continuous Review Cost Table"):
        st.dataframe(df_cr.style.highlight_min(subset=['Total Cost ($)'], color='#2e5c36').format({"No of Orders": "{:,.1f}", "Average Inventory": "{:,.1f}", "Holding Cost ($)": "${:,.0f}", "Ordering Cost ($)": "${:,.0f}", "Total Cost ($)": "${:,.0f}"}), use_container_width=True, hide_index=True)

    # Continuous Review Simulation
    st.subheader("Continuous Review Simulation")
    
    # Calculate default ROP based on SL
    std_dev_lt = std_dev_demand * math.sqrt(lead_time)
    default_rop = (avg_daily_demand * lead_time) + (z_score * std_dev_lt)
    
    col_q, col_rop = st.columns(2)
    sim_q = col_q.number_input("Simulation Order Quantity", min_value=1, value=int(opt_cr['Order Quantity (Q)']), step=10)
    sim_rop = col_rop.number_input("Simulation Reorder Point (ROP)", min_value=1, value=int(default_rop), step=10)
    
    if st.button("Run Continuous Review Simulation", type="primary"):
        inventory = int(sim_rop + (sim_q / 2))
        pipeline = []
        phys_balances = []
        lost_sales = 0
        stockout_days = 0
        orders_placed = 0
        
        for day in range(total_days):
            demand_today = demand_array[day]
            
            shipments = sum(qty for arr_day, qty in pipeline if arr_day == day)
            pipeline = [(arr_day, qty) for arr_day, qty in pipeline if arr_day > day]
            inventory += shipments
            
            if inventory >= demand_today:
                inventory -= demand_today
            else:
                lost_sales += (demand_today - inventory)
                stockout_days += 1
                inventory = 0
                
            phys_balances.append(inventory)
            
            inv_position = inventory + sum(qty for arr_day, qty in pipeline)
            if inv_position < sim_rop:
                pipeline.append((day + int(lead_time), sim_q))
                orders_placed += 1
                
        total_fulfilled = total_demand - lost_sales
        fill_rate = (total_fulfilled / total_demand * 100) if total_demand > 0 else 100
        avg_inv = np.mean(phys_balances)
        
        hc_sim = avg_inv * period_holding_cost_per_unit
        oc_sim = orders_placed * fixed_ordering_cost
        
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Fill Rate", f"{fill_rate:.2f}%")
        sc2.metric("Stockout Days", f"{stockout_days}")
        sc3.metric("Total Orders Placed", f"{orders_placed}")
        sc4.metric("Total Period Cost", f"${(hc_sim + oc_sim):,.0f}")
        
    # ------------------------------------------------
    # Periodic Review System
    # ------------------------------------------------
    st.divider()
    st.header("2. Periodic Review System")
    
    # Theoretical Optimization
    pr_data = []
    for t in range(1, 91):
        std_dev_lt_pr = std_dev_demand * math.sqrt(t + lead_time)
        ss = z_score * std_dev_lt_pr
        target_lvl = (avg_daily_demand * (t + lead_time)) + ss
        
        avg_inv_pr = ss + ((avg_daily_demand * t) / 2)
        num_orders_pr = total_days / t
        
        hc_pr = avg_inv_pr * period_holding_cost_per_unit
        oc_pr = num_orders_pr * fixed_ordering_cost
        tc_pr = hc_pr + oc_pr
        
        pr_data.append([t, target_lvl, num_orders_pr, avg_inv_pr, hc_pr, oc_pr, tc_pr])
        
    df_pr = pd.DataFrame(pr_data, columns=["Review Period (Days)", "Target Level", "No of Orders", "Average Inventory", "Holding Cost ($)", "Ordering Cost ($)", "Total Cost ($)"])
    opt_pr = df_pr.loc[df_pr["Total Cost ($)"].idxmin()]
    
    st.subheader("Cost Sensitivity Analysis")
    st.info(f"**Optimal Review Period:** {opt_pr['Review Period (Days)']:.0f} days | **Minimum Total Cost:** ${opt_pr['Total Cost ($)']:,.0f}")
    
    fig_pr = go.Figure()
    fig_pr.add_trace(go.Scatter(x=df_pr["Review Period (Days)"], y=df_pr["Holding Cost ($)"], mode="lines", name="Holding Cost", line=dict(color="orange")))
    fig_pr.add_trace(go.Scatter(x=df_pr["Review Period (Days)"], y=df_pr["Ordering Cost ($)"], mode="lines", name="Ordering Cost", line=dict(color="cyan")))
    fig_pr.add_trace(go.Scatter(x=df_pr["Review Period (Days)"], y=df_pr["Total Cost ($)"], mode="lines", name="Total Cost", line=dict(color="lightgreen", width=3)))
    fig_pr.add_vline(x=opt_pr['Review Period (Days)'], line_dash="dash", line_color="white", annotation_text="Min Cost", annotation_position="top right")
    fig_pr.update_layout(title="Periodic Review: Costs vs Review Period", xaxis_title="Review Period (Days)", yaxis_title=f"Cost over {total_days} Days ($)")
    st.plotly_chart(style_plotly_fig(fig_pr), use_container_width=True)
    
    with st.expander("View Periodic Review Cost Table"):
        st.dataframe(df_pr.style.highlight_min(subset=['Total Cost ($)'], color='#2e5c36').format({"Target Level": "{:,.0f}", "No of Orders": "{:,.1f}", "Average Inventory": "{:,.1f}", "Holding Cost ($)": "${:,.0f}", "Ordering Cost ($)": "${:,.0f}", "Total Cost ($)": "${:,.0f}"}), use_container_width=True, hide_index=True)

    # Periodic Review Simulation
    st.subheader("Periodic Review Simulation")
    
    col_t, col_s = st.columns(2)
    sim_t = col_t.number_input("Simulation Review Period (Days)", min_value=1, value=int(opt_pr['Review Period (Days)']), step=1)
    sim_s = col_s.number_input("Simulation Target Level (Order-Up-To)", min_value=1, value=int(opt_pr['Target Level']), step=10)
    
    if st.button("Run Periodic Review Simulation", type="primary"):
        inventory = int(sim_s)
        pipeline = []
        phys_balances = []
        lost_sales = 0
        stockout_days = 0
        orders_placed = 0
        
        for day in range(total_days):
            demand_today = demand_array[day]
            
            shipments = sum(qty for arr_day, qty in pipeline if arr_day == day)
            pipeline = [(arr_day, qty) for arr_day, qty in pipeline if arr_day > day]
            inventory += shipments
            
            if inventory >= demand_today:
                inventory -= demand_today
            else:
                lost_sales += (demand_today - inventory)
                stockout_days += 1
                inventory = 0
                
            phys_balances.append(inventory)
            
            if day % sim_t == 0:
                inv_position = inventory + sum(qty for arr_day, qty in pipeline)
                order_qty = max(0, sim_s - inv_position)
                if order_qty > 0:
                    pipeline.append((day + int(lead_time), order_qty))
                    orders_placed += 1
                    
        total_fulfilled = total_demand - lost_sales
        fill_rate = (total_fulfilled / total_demand * 100) if total_demand > 0 else 100
        avg_inv = np.mean(phys_balances)
        
        hc_sim = avg_inv * period_holding_cost_per_unit
        oc_sim = orders_placed * fixed_ordering_cost
        
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Fill Rate", f"{fill_rate:.2f}%")
        sc2.metric("Stockout Days", f"{stockout_days}")
        sc3.metric("Total Orders Placed", f"{orders_placed}")
        sc4.metric("Total Period Cost", f"${(hc_sim + oc_sim):,.0f}")
else:
    st.info("Please upload an inventory dataset in the sidebar to begin optimization.")
