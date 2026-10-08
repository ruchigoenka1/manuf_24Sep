import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import scipy.stats as stats

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
st.divider()
st.subheader("Theoretical Cost Analysis")

if eoq > 0:
    # Calculate optimal metrics at EOQ
    opt_num_orders = annual_demand / eoq
    opt_avg_inv = eoq / 2
    opt_holding_cost = opt_avg_inv * annual_holding_cost_per_unit
    opt_ordering_cost = opt_num_orders * fixed_ordering_cost
    opt_total_cost = opt_holding_cost + opt_ordering_cost

    st.markdown("#### Optimal EOQ Policy Metrics")
    eoq_c1, eoq_c2, eoq_c3 = st.columns(3)
    eoq_c1.metric("Economic Order Qty (EOQ)", f"{eoq:,.0f} units")
    eoq_c2.metric("No of Orders (per year)", f"{opt_num_orders:,.1f}")
    eoq_c3.metric("Average Inventory", f"{opt_avg_inv:,.0f} units")

    eoq_c4, eoq_c5, eoq_c6 = st.columns(3)
    eoq_c4.metric("Annual Holding Cost", f"${opt_holding_cost:,.0f}")
    eoq_c5.metric("Annual Ordering Cost", f"${opt_ordering_cost:,.0f}")
    eoq_c6.metric("Total Inventory Cost", f"${opt_total_cost:,.0f}")
    
    st.divider()
else:
    st.warning("Please enter valid parameters to calculate EOQ.")

# Generate Data Table for Cost Curves
# Generate Data Table for Cost Curves
if eoq > 0:
    # Create an array of quantities ranging from 20% of EOQ to 200% of EOQ
    q_range = np.linspace(max(10, eoq * 0.2), eoq * 2, 20).astype(int)
    
    cost_data = []
    for q in q_range:
        avg_inv = q / 2
        num_orders = annual_demand / q
        holding = avg_inv * annual_holding_cost_per_unit
        ordering = num_orders * fixed_ordering_cost
        total = holding + ordering
        cost_data.append([q, num_orders, avg_inv, holding, ordering, total])
        
    df_costs = pd.DataFrame(cost_data, columns=[
        "Order Quantity", 
        "No of Orders", 
        "Average Inventory", 
        "Holding Cost ($)", 
        "Ordering Cost ($)", 
        "Total Inventory Cost ($)"
    ])
    
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
    
    # Format the new columns for clean display
    st.dataframe(
        df_costs.style.format({
            "No of Orders": "{:,.1f}",
            "Average Inventory": "{:,.1f}",
            "Holding Cost ($)": "${:,.0f}", 
            "Ordering Cost ($)": "${:,.0f}", 
            "Total Inventory Cost ($)": "${:,.0f}"
        }), 
        use_container_width=True, 
        hide_index=True
    )
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

# ------------------------------------------------
# Periodic Review System Optimization
# ------------------------------------------------
with st.expander("📅 Periodic Review System Optimization"):
    st.markdown("Analyze costs for a periodic review (Order-Up-To) system across different review intervals to find the lowest total cost.")
    
    # User Input for Target Service Level
    pr_sl = st.number_input("Target Service Level (%) for Periodic Review", min_value=50.0, max_value=99.99, value=95.0, step=0.1)
    
    if avg_daily_demand > 0 and fixed_ordering_cost > 0 and annual_holding_cost_per_unit > 0:
        # Calculate z-score based on service level
        z_score = stats.norm.ppf(pr_sl / 100.0)
        daily_std_dev = avg_daily_demand * cov
        
        pr_data = []
        # Simulate review periods (T) from 1 to 90 days
        for t in range(1, 91):
            # Standard Deviation over protection interval (T + L)
            std_dev_lt = daily_std_dev * math.sqrt(t + lead_time)
            
            # Safety Stock and Target Level (S)
            ss = z_score * std_dev_lt
            target_level = (avg_daily_demand * (t + lead_time)) + ss
            
            # Operational metrics
            avg_inv = ss + ((avg_daily_demand * t) / 2)
            num_orders = 365 / t
            
            # Costs
            hc = avg_inv * annual_holding_cost_per_unit
            oc = num_orders * fixed_ordering_cost
            tc = hc + oc
            
            pr_data.append({
                "Review Period (Days)": int(t),
                "Target Level (S)": target_level,
                "No of Orders": num_orders,
                "Average Inventory": avg_inv,
                "Holding Cost ($)": hc,
                "Ordering Cost ($)": oc,
                "Total Inventory Cost ($)": tc
            })
            
        df_pr = pd.DataFrame(pr_data)
        
        # Identify the row with the lowest total cost
        opt_pr = df_pr.loc[df_pr["Total Inventory Cost ($)"].idxmin()]
        
        # 1. Optimal Metrics Dashboard
        st.markdown("#### Optimal Periodic Review Policy Metrics")
        pr_c1, pr_c2, pr_c3, pr_c4 = st.columns(4)
        pr_c1.metric("Optimal Review Period (T)", f"{opt_pr['Review Period (Days)']:.0f} days")
        pr_c2.metric("Target Level (Order-Up-To)", f"{opt_pr['Target Level (S)']:,.0f} units")
        pr_c3.metric("No of Orders (per year)", f"{opt_pr['No of Orders']:,.1f}")
        pr_c4.metric("Average Inventory", f"{opt_pr['Average Inventory']:,.0f} units")

        pr_c5, pr_c6, pr_c7 = st.columns(3)
        pr_c5.metric("Annual Holding Cost", f"${opt_pr['Holding Cost ($)']:,.0f}")
        pr_c6.metric("Annual Ordering Cost", f"${opt_pr['Ordering Cost ($)']:,.0f}")
        pr_c7.metric("Total Inventory Cost", f"${opt_pr['Total Inventory Cost ($)']:,.0f}")
        
        st.divider()
        
        # 2. Cost Curves Plot
        fig_pr = go.Figure()
        fig_pr.add_trace(go.Scatter(x=df_pr["Review Period (Days)"], y=df_pr["Holding Cost ($)"], mode="lines", name="Holding Cost", line=dict(color="orange")))
        fig_pr.add_trace(go.Scatter(x=df_pr["Review Period (Days)"], y=df_pr["Ordering Cost ($)"], mode="lines", name="Ordering Cost", line=dict(color="cyan")))
        fig_pr.add_trace(go.Scatter(x=df_pr["Review Period (Days)"], y=df_pr["Total Inventory Cost ($)"], mode="lines", name="Total Cost", line=dict(color="lightgreen", width=3)))
        
        fig_pr.add_vline(x=opt_pr['Review Period (Days)'], line_dash="dash", line_color="white", 
                         annotation_text=f"Optimal T: {opt_pr['Review Period (Days)']:.0f} days", annotation_position="top right")
        
        fig_pr.update_layout(title="Periodic Review Costs vs. Review Period", xaxis_title="Review Period (Days)", yaxis_title="Annual Cost ($)")
        fig_pr = style_plotly_fig(fig_pr)
        st.plotly_chart(fig_pr, use_container_width=True)
        
        # 3. Formatted Data Table
        st.markdown("##### Periodic Review Cost Data Table")
        st.dataframe(
            df_pr.style.format({
                "Target Level (S)": "{:,.0f}",
                "No of Orders": "{:,.1f}",
                "Average Inventory": "{:,.1f}",
                "Holding Cost ($)": "${:,.0f}", 
                "Ordering Cost ($)": "${:,.0f}", 
                "Total Inventory Cost ($)": "${:,.0f}"
            }), 
            use_container_width=True, 
            hide_index=True
        )

    # ------------------------------------------------
    # Periodic Review Operational Simulation Dashboard
    # ------------------------------------------------
    st.divider()
    st.subheader("Periodic Review Operational Simulation")
    st.markdown("Test a specific Review Period against a 365-day stochastic demand distribution to see operational and financial impacts.")
    
    # Default to the optimal review period found above
    custom_t = st.number_input("Enter Review Period (Days) to Simulate", min_value=1, value=int(opt_pr['Review Period (Days)']), step=1)
    
    if st.button("Simulate Periodic Review Strategy", type="primary"):
        with st.spinner(f"Simulating 365 days for Review Period: {custom_t} days..."):
            
            # 1. Generate Demand
            if cov == 0:
                sim_demand_pr = np.full(365, int(avg_daily_demand))
            else:
                np.random.seed(42)
                std_dev_daily = avg_daily_demand * cov 
                var = std_dev_daily**2
                theta = var / avg_daily_demand
                k = avg_daily_demand / theta
                sim_demand_pr = np.random.gamma(k, theta, 365).round().astype(int)
    
            # 2. Calculate the Order-Up-To Target Level (S) for the custom T
            z_score_sim = stats.norm.ppf(pr_sl / 100.0)
            std_dev_lt_sim = (avg_daily_demand * cov) * math.sqrt(custom_t + lead_time)
            target_level_sim = (avg_daily_demand * (custom_t + lead_time)) + (z_score_sim * std_dev_lt_sim)
            
            # 3. Run Periodic Review Simulation
            inventory = int(target_level_sim) # Estimated starting balance
            pipeline = []
            phys_balances = []
            lost_sales = 0
            stockout_days = 0
            total_demand = 0
            total_orders_placed = 0
            
            for day in range(365):
                demand_today = sim_demand_pr[day]
                total_demand += demand_today
                
                # Receive shipments
                shipment_received = sum(qty for arr_day, qty in pipeline if arr_day == day)
                pipeline = [(arr_day, qty) for arr_day, qty in pipeline if arr_day > day]
                
                inventory += shipment_received
                
                # Fulfill Demand
                if inventory >= demand_today:
                    inventory -= demand_today
                else:
                    unmet = demand_today - inventory
                    lost_sales += unmet
                    stockout_days += 1
                    inventory = 0
                    
                phys_balances.append(inventory)
                
                # Reorder Logic - ONLY on Review Days
                if day % custom_t == 0:
                    inventory_position = inventory + sum(qty for arr_day, qty in pipeline)
                    order_qty = max(0, target_level_sim - inventory_position)
                    
                    if order_qty > 0:
                        pipeline.append((day + int(lead_time), order_qty))
                        total_orders_placed += 1
                        
            # 4. Calculate Dashboard Metrics
            total_fulfilled = total_demand - lost_sales
            fill_rate = (total_fulfilled / total_demand * 100) if total_demand > 0 else 100
            avg_inv = np.mean(phys_balances)
            min_inv = np.min(phys_balances)
            max_inv = np.max(phys_balances)
            
            sim_holding_cost = avg_inv * annual_holding_cost_per_unit
            sim_ordering_
