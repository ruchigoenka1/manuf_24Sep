import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math

# Updated styling function for a dark background
def style_plotly_fig(fig):
    fig.update_layout(
        plot_bgcolor='#0E1117', 
        paper_bgcolor='#0E1117',
        font=dict(color='white'),
        title_font=dict(color='white'),
        legend=dict(
            font=dict(color='white'),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', gridcolor='#2b2b2b')
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', gridcolor='#2b2b2b', rangemode="tozero")
    return fig

st.title("Economic Order Quantity (EOQ) & Optimization")
st.write("Analyze theoretical inventory costs and simulate real-world fulfillment based on dynamic demand parameters.")

# ------------------------------------------------
# User Inputs
# ------------------------------------------------
st.sidebar.header("Cost Parameters")
fixed_ordering_cost = st.sidebar.number_input("Fixed Ordering Cost ($)", value=500.0, step=50.0)
holding_cost_pct = st.sidebar.number_input("Holding Cost (% of Avg Inv)", value=20.0, step=1.0)
unit_value = st.sidebar.number_input("Unit Value ($)", value=100.0, step=10.0)

st.sidebar.header("Demand & Policy Parameters")
avg_daily_demand = st.sidebar.number_input("Average Daily Demand", value=25)
cov = st.sidebar.number_input("Coefficient of Variation (COV)", value=0.0, step=0.1)
rop = st.sidebar.number_input("Reorder Point (ROP)", value=300)
lead_time = st.sidebar.number_input("Lead Time (Days)", value=3)

# ------------------------------------------------
# EOQ Theoretical Calculations
# ------------------------------------------------
annual_demand = avg_daily_demand * 365
annual_holding_cost_per_unit = unit_value * (holding_cost_pct / 100)

if annual_holding_cost_per_unit > 0 and fixed_ordering_cost > 0 and annual_demand > 0:
    eoq = math.sqrt((2 * annual_demand * fixed_ordering_cost) / annual_holding_cost_per_unit)
else:
    eoq = 0

st.divider()
st.subheader("Theoretical Cost Analysis")
st.info(f"**Calculated Economic Order Quantity (EOQ):** {eoq:,.0f} units")

# Generate Data Table for Cost Curves
if eoq > 0:
    # Create an array of quantities ranging from 20% of EOQ to 200% of EOQ
    q_range = np.linspace(max(10, eoq * 0.2), eoq * 2, 20).astype(int)
    
    cost_data = []
    for q in q_range:
        holding = (q / 2) * annual_holding_cost_per_unit
        ordering = (annual_demand / q) * fixed_ordering_cost
        total = holding + ordering
        cost_data.append([q, holding, ordering, total])
        
    df_costs = pd.DataFrame(cost_data, columns=["Order Quantity", "Holding Cost ($)", "Ordering Cost ($)", "Total Inventory Cost ($)"])
    
    # Cost Graph
    fig_eoq = go.Figure()
    fig_eoq.add_trace(go.Scatter(x=df_costs["Order Quantity"], y=df_costs["Holding Cost ($)"], mode="lines", name="Holding Cost", line=dict(color="orange")))
    fig_eoq.add_trace(go.Scatter(x=df_costs["Order Quantity"], y=df_costs["Ordering Cost ($)"], mode="lines", name="Ordering Cost", line=dict(color="cyan")))
    fig_eoq.add_trace(go.Scatter(x=df_costs["Order Quantity"], y=df_costs["Total Inventory Cost ($)"], mode="lines", name="Total Cost", line=dict(color="lightgreen", width=3)))
    
    # Mark the EOQ point
    min_cost = df_costs["Total Inventory Cost ($)"].min()
    fig_eoq.add_vline(x=eoq, line_dash="dash", line_color="white", annotation_text=f"EOQ: {eoq:.0f}", annotation_position="top right")
    
    fig_eoq.update_layout(title="Inventory Costs vs. Order Quantity", xaxis_title="Order Quantity (Units)", yaxis_title="Annual Cost ($)")
    fig_eoq = style_plotly_fig(fig_eoq)
    
    # Stacked Layout
    st.plotly_chart(fig_eoq, use_container_width=True)
    st.markdown("##### Cost Data Table")
    st.dataframe(df_costs.style.format({"Holding Cost ($)": "${:,.0f}", "Ordering Cost ($)": "${:,.0f}", "Total Inventory Cost ($)": "${:,.0f}"}), use_container_width=True, hide_index=True)

# ------------------------------------------------
# Simulation Dashboard
# ------------------------------------------------
st.divider()
st.subheader("Operational Simulation Dashboard")
st.markdown("Test specific order quantities against a 365-day stochastic demand distribution to see operational and financial impacts.")

custom_q = st.number_input("Enter Order Quantity to Simulate", value=int(eoq) if eoq > 0 else int(avg_daily_demand * 10), step=50)

if st.button("Simulate Fulfillment Strategy", type="primary"):
    with st.spinner("Simulating 365 days of fulfillment..."):
        # 1. Generate Demand
        if cov == 0:
            sim_demand = np.full(365, int(avg_daily_demand))
        else:
            np.random.seed(42)
            std_dev = avg_daily_demand * cov 
            var = std_dev**2
            theta = var / avg_daily_demand
            k = avg_daily_demand / theta
            sim_demand = np.random.gamma(k, theta, 365).round().astype(int)

        # 2. Run Lightweight Simulation (Continuous Review)
        inventory = int(rop + (custom_q / 2)) # Estimated opening balance
        pipeline = []
        phys_balances = []
        lost_sales = 0
        stockout_days = 0
        total_demand = 0
        total_orders_placed = 0
        
        for day in range(365):
            demand_today = sim_demand[day]
            total_demand += demand_today
            
            # Receive shipments
            shipment_received = sum(qty for arr_day, qty in pipeline if arr_day == day)
            pipeline = [(arr_day, qty) for arr_day, qty in pipeline if arr_day > day]
            
            inventory += shipment_received
            
            # Fulfill
            if inventory >= demand_today:
                inventory -= demand_today
            else:
                unmet = demand_today - inventory
                lost_sales += unmet
                stockout_days += 1
                inventory = 0
                
            phys_balances.append(inventory)
            
            # Reorder Logic
            inventory_position = inventory + sum(qty for arr_day, qty in pipeline)
            if inventory_position < rop:
                pipeline.append((day + int(lead_time), custom_q))
                total_orders_placed += 1
                
        # 3. Calculate Dashboard Metrics
        total_fulfilled = total_demand - lost_sales
        fill_rate = (total_fulfilled / total_demand * 100) if total_demand > 0 else 100
        avg_inv = np.mean(phys_balances)
        min_inv = np.min(phys_balances)
        max_inv = np.max(phys_balances)
        
        # Calculate Simulated Costs
        annual_holding_cost_per_unit = unit_value * (holding_cost_pct / 100)
        sim_holding_cost = avg_inv * annual_holding_cost_per_unit
        sim_ordering_cost = total_orders_placed * fixed_ordering_cost
        sim_total_cost = sim_holding_cost + sim_ordering_cost

        # 4. Render Metrics in Units and Value
        st.markdown(f"#### Results for Order Quantity: **{custom_q:,.0f} units**")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fill Rate", f"{fill_rate:.2f}%")
        c2.metric("Stockout Days", f"{stockout_days} days")
        c3.metric("Total Annual Demand", f"{total_demand:,.0f} units")
        c4.metric("Missed Sales", f"{lost_sales:,.0f} units")
        
        st.markdown("**Inventory Holding Analysis**")
        ic1, ic2, ic3 = st.columns(3)
        
        # Unit row
        ic1.metric("Avg Inventory (Units)", f"{avg_inv:,.0f}")
        ic2.metric("Min Inventory (Units)", f"{min_inv:,.0f}")
        ic3.metric("Max Inventory (Units)", f"{max_inv:,.0f}")
        
        # Value row
        ic1.metric("Avg Capital Blocked ($)", f"${(avg_inv * unit_value):,.0f}")
        ic2.metric("Min Capital Blocked ($)", f"${(min_inv * unit_value):,.0f}")
        ic3.metric("Max Capital Blocked ($)", f"${(max_inv * unit_value):,.0f}")
        
        st.markdown("**Operational Cost Analysis**")
        oc1, oc2, oc3, oc4 = st.columns(4)
        oc1.metric("Total Orders Placed", f"{total_orders_placed}")
        oc2.metric("Annual Holding Cost", f"${sim_holding_cost:,.0f}")
        oc3.metric("Annual Ordering Cost", f"${sim_ordering_cost:,.0f}")
        oc4.metric("Total Inventory Cost", f"${sim_total_cost:,.0f}")
