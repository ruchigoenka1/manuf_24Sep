import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io

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

# ------------------------------------------------
# Sample Excel Generator
# ------------------------------------------------
def generate_sample_excel():
    df_sample = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-03", "2024-01-07", "2024-01-10", "2024-01-12"],
        "Closing Balance": [500, 439, 358, 600, 520]
    })
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_sample.to_excel(writer, index=False, sheet_name='Sample Data')
    return buffer.getvalue()

# ------------------------------------------------
# Reusable Simulation Core Engine
# ------------------------------------------------
def run_simulation(sim_demand, policy, lead_time, p1, p2, opening_balance, max_wait_time, unit_value, unit_profit, holding_cost_pct, ordering_cost):
    num_days = len(sim_demand)
    inventory = opening_balance
    pipeline_orders = []
    backorder_queue = [] 
    
    sim_phys_balances = []
    sim_net_balances = []
    sim_active_backorders = []
    sim_daily_lost_sales = []
    sim_closing_net_pipeline = []
    sim_new_orders = []
    
    total_demand_overall = 0
    total_lost_sales = 0
    
    for day in range(num_days):
        demand_today = sim_demand[day]
        total_demand_overall += demand_today
        daily_lost_sales = 0
        
        # 1. Expire unfulfilled backorders
        active_backorders = []
        for bo in backorder_queue:
            if (day - bo['day_created']) > max_wait_time:
                daily_lost_sales += bo['qty']
                total_lost_sales += bo['qty']
            else:
                active_backorders.append(bo)
        backorder_queue = active_backorders

        # 2. Receive shipments
        shipment_received = 0
        for order in pipeline_orders.copy():
            if order[0] == day:
                shipment_received += order[1]
                pipeline_orders.remove(order)

        # 3. Fulfill existing backorders
        while shipment_received > 0 and backorder_queue:
            if shipment_received >= backorder_queue[0]['qty']:
                shipment_received -= backorder_queue[0]['qty']
                backorder_queue.pop(0)
            else:
                backorder_queue[0]['qty'] -= shipment_received
                shipment_received = 0

        inventory += shipment_received

        # 4. Process today's demand
        if inventory >= demand_today:
            inventory -= demand_today
        else:
            unmet = demand_today - inventory
            inventory = 0
            if max_wait_time > 0:
                backorder_queue.append({'qty': unmet, 'day_created': day})
            else:
                daily_lost_sales += unmet
                total_lost_sales += unmet

        # Calculate Current Metrics
        current_backorders = sum(bo['qty'] for bo in backorder_queue)
        net_inventory = inventory - current_backorders
        pipeline_qty = sum(qty for arrival, qty in pipeline_orders)
        inventory_position = net_inventory + pipeline_qty

        # 5. Order Triggers based on Policy
        new_order = 0
        if policy == "Continuous Review":
            rop, order_qty = p1, p2
            if inventory_position < rop:
                new_order = order_qty
                pipeline_orders.append((day + lead_time, order_qty))
        else:
            review_period, order_up_to_S = p1, p2
            if day % review_period == 0:
                if inventory_position < order_up_to_S:
                    new_order = order_up_to_S - inventory_position
                    pipeline_orders.append((day + lead_time, new_order))

        closing_net_with_pipeline = net_inventory + pipeline_qty

        sim_phys_balances.append(inventory)
        sim_net_balances.append(net_inventory)
        sim_active_backorders.append(current_backorders)
        sim_daily_lost_sales.append(daily_lost_sales)
        sim_closing_net_pipeline.append(closing_net_with_pipeline)
        sim_new_orders.append(new_order)
        
    # Financial & KPI Calculations
    avg_phys_inv = np.mean(sim_phys_balances)
    total_sales = total_demand_overall - total_lost_sales
    fill_rate = (total_sales / total_demand_overall * 100) if total_demand_overall > 0 else 100
    stockout_days = sum(1 for x in sim_daily_lost_sales if x > 0)
    
    avg_working_capital = avg_phys_inv * unit_value
    daily_holding_rate = (holding_cost_pct / 100) / 365
    total_holding_cost = sum(sim_phys_balances) * unit_value * daily_holding_rate
    
    total_orders_placed = sum(1 for x in sim_new_orders if x > 0)
    total_ordering_cost = total_orders_placed * ordering_cost
    total_inventory_cost = total_holding_cost + total_ordering_cost
    
    gross_profit_from_sales = total_sales * unit_profit
    net_profit = gross_profit_from_sales - total_inventory_cost
    
    return {
        'Physical Inventory': sim_phys_balances,
        'Net Inventory': sim_net_balances,
        'Active Backorders': sim_active_backorders,
        'Daily Lost Sales': sim_daily_lost_sales,
        'Closing Net Including Pipeline': sim_closing_net_pipeline,
        'New Order': sim_new_orders,
        'Total Demand': total_demand_overall,
        'Total Sales': total_sales,
        'Missed Demand': total_lost_sales,
        'Fill Rate': fill_rate,
        'Stockout Days': stockout_days,
        'Avg Physical Inventory': avg_phys_inv,
        'Avg Working Capital': avg_working_capital,
        'Total Holding Cost': total_holding_cost,
        'Total Ordering Cost': total_ordering_cost,
        'Total Inventory Cost': total_inventory_cost,
        'Gross Profit': gross_profit_from_sales,
        'Net Profit': net_profit,
        'Orders Placed': total_orders_placed
    }


st.title("Historical Audit & Financial Simulator")
st.write("Upload historical inventory data to simulate your policy and analyze fulfillment, working capital, and overall profitability.")

# ------------------------------------------------
# Download Template Section
# ------------------------------------------------
st.download_button(
    label="📥 Download Sample Excel Template",
    data=generate_sample_excel(),
    file_name="inventory_sample_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.divider()

# ------------------------------------------------
# File Upload & Demand Extraction
# ------------------------------------------------
uploaded_file = st.file_uploader("Upload Historical Data", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        df_hist = pd.read_csv(uploaded_file)
    else:
        df_hist = pd.read_excel(uploaded_file)
        
    time_col = df_hist.columns[0]
    balance_col = df_hist.columns[1]
    
    is_numeric_index = pd.api.types.is_numeric_dtype(df_hist[time_col])
    if not is_numeric_index:
        df_hist[time_col] = pd.to_datetime(df_hist[time_col])
        
    df_hist = df_hist.sort_values(by=time_col)
    df_hist.set_index(time_col, inplace=True)
    
    if is_numeric_index:
        full_range = range(int(df_hist.index.min()), int(df_hist.index.max()) + 1)
    else:
        full_range = pd.date_range(start=df_hist.index.min(), end=df_hist.index.max())
    
    df_filled = df_hist.reindex(full_range).ffill()
    df_filled.reset_index(inplace=True)
    df_filled.rename(columns={'index': time_col}, inplace=True)
    
    df_filled['Previous Balance'] = df_filled[balance_col].shift(1)
    df_filled['Derived Demand'] = np.where(
        df_filled['Previous Balance'] > df_filled[balance_col], 
        df_filled['Previous Balance'] - df_filled[balance_col], 
        0
    )
    df_filled['Derived Demand'] = df_filled['Derived Demand'].fillna(0)
    
    avg_demand_hist = df_filled['Derived Demand'].mean() if len(df_filled) > 0 else 0

    # ------------------------------------------------
    # Sidebar Inputs & Policy Configuration
    # ------------------------------------------------
    st.sidebar.header("Simulation Parameters")
    
    policy = st.sidebar.radio("Inventory Policy", ["Continuous Review", "Periodic Review"])
    lead_time = st.sidebar.number_input("Lead Time (Days)", value=3)

    p1_val, p2_val = 0, 0
    if policy == "Continuous Review":
        p1_val = st.sidebar.number_input("Reorder Point", value=200)
        p2_val = st.sidebar.number_input("Order Quantity", value=300)
        default_ob = int(1.25 * p1_val)
        ref_line, ref_label = p1_val, "Reorder Point"
    else:
        p1_val = st.sidebar.number_input("Review Period (Days)", value=7)
        default_S = int(round(avg_demand_hist * (p1_val + lead_time) * 1.5)) if avg_demand_hist > 0 else 500
        p2_val = st.sidebar.number_input("Order-Up-To Level (S)", min_value=1, value=max(1, default_S))
        default_ob = int(1.25 * p2_val)
        ref_line, ref_label = p2_val, "Target Level (S)"
    
    opening_balance = st.sidebar.number_input("Opening Balance", value=default_ob)
    max_wait_time = st.sidebar.number_input("Max Customer Wait Time (Days)", value=5, min_value=0)
    
    st.sidebar.divider()
    st.sidebar.header("Financial Inputs")
    unit_value = st.sidebar.number_input("Product Value per Unit ($)", value=100.0)
    unit_profit = st.sidebar.number_input("Profit per Unit Sold ($)", value=35.0)
    holding_cost_pct = st.sidebar.number_input("Annual Holding Cost (%)", value=20.0)
    ordering_cost = st.sidebar.number_input("Fixed Ordering Cost per Order ($)", value=500.0)

    include_pipeline = st.sidebar.checkbox("Include Pipeline Inventory in Net Chart", value=False)
    
    # ------------------------------------------------
    # Run Main Simulation
    # ------------------------------------------------
    sim_demand = df_filled['Derived Demand'].values
    res = run_simulation(
        sim_demand, policy, lead_time, p1_val, p2_val, opening_balance, 
        max_wait_time, unit_value, unit_profit, holding_cost_pct, ordering_cost
    )
    
    # Map simulation results back to DataFrame for charts
    df_filled['Physical Inventory'] = res['Physical Inventory']
    df_filled['Net Inventory'] = res['Net Inventory']
    df_filled['Active Backorders'] = res['Active Backorders']
    df_filled['Daily Lost Sales'] = res['Daily Lost Sales']
    df_filled['Closing Net Including Pipeline'] = res['Closing Net Including Pipeline']
    df_filled['New Order'] = res['New Order']

    # ------------------------------------------------
    # Output & Comparison KPIs
    # ------------------------------------------------
    st.subheader("Financial Profitability & Costs")
    
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    p_col1.metric("Gross Profit (From Sales)", f"${res['Gross Profit']:,.0f}")
    p_col2.metric("Total Holding Cost", f"${res['Total Holding Cost']:,.0f}")
    p_col3.metric("Total Ordering Cost", f"${res['Total Ordering Cost']:,.0f}")
    p_col4.metric("Net Overall Profit/Loss", f"${res['Net Profit']:,.0f}")

    st.markdown("**Operational Fulfillment**")
    o_col1, o_col2, o_col3, o_col4, o_col5 = st.columns(5)
    o_col1.metric("Total Demand", f"{res['Total Demand']:,.0f}")
    o_col2.metric("Total Sales Fulfilled", f"{res['Total Sales']:,.0f}")
    o_col3.metric("Missed Demand", f"{res['Missed Demand']:,.0f}")
    o_col4.metric("Fill Rate", f"{res['Fill Rate']:.1f}%")
    o_col5.metric("Stockout Days", res['Stockout Days'])

    st.markdown("**Working Capital & Inventory**")
    w_col1, w_col2, w_col3 = st.columns(3)
    w_col1.metric("Avg Physical Inventory", f"{res['Avg Physical Inventory']:,.0f} units")
    w_col2.metric("Average Working Capital", f"${res['Avg Working Capital']:,.0f}")
    w_col3.metric("Total Orders Placed", res['Orders Placed'])
    
    st.divider()

    # ------------------------------------------------
    # Data Visualizations
    # ------------------------------------------------
    st.subheader("Inventory Behaviour")

    # Graph 1: Physical Inventory
    st.markdown("##### Physical Inventory vs Historical")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df_filled[time_col], y=df_filled[balance_col], mode="lines", name="Historical Balance", line=dict(color="gray", width=2, dash="dash")))
    fig1.add_trace(go.Scatter(x=df_filled[time_col], y=df_filled["Physical Inventory"], name="Simulated Physical Inventory", line=dict(color='skyblue', width=2)))

    reorders = df_filled[df_filled["New Order"] > 0]
    fig1.add_trace(go.Scatter(x=reorders[time_col], y=reorders["Physical Inventory"], mode="markers", name="Reorder Trigger", marker=dict(color="green", symbol="triangle-up", size=10)))

    actual_stockouts = df_filled[df_filled["Daily Lost Sales"] > 0]
    fig1.add_trace(go.Scatter(x=actual_stockouts[time_col], y=actual_stockouts["Physical Inventory"], mode="markers", name="Lost Sale (Stockout)", marker=dict(color="red", symbol="triangle-up", size=10)))

    fig1.add_hline(y=ref_line, line_dash="dash", line_color="gray", annotation_text=ref_label, annotation_font_color="white")
    fig1 = style_plotly_fig(fig1)
    st.plotly_chart(fig1, use_container_width=True)

    # Graph 2: Net Inventory
    st.markdown("##### Net Inventory (Backorder Impact)")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df_filled[time_col], y=df_filled[balance_col], mode="lines", name="Historical Balance", line=dict(color="gray", width=2, dash="dash")))
    fig2.add_trace(go.Scatter(x=df_filled[time_col], y=df_filled["Net Inventory"], name="Net Inventory (Includes Backorders)", line=dict(color='orange', width=2)))

    if include_pipeline:
        fig2.add_trace(go.Scatter(x=df_filled[time_col], y=df_filled["Closing Net Including Pipeline"], name="Inventory Position", line=dict(color='#1f77b4', width=2)))
        
    fig2.add_hline(y=ref_line, line_dash="dash", line_color="gray", annotation_text=ref_label, annotation_font_color="white")
    fig2.add_hline(y=0, line_color="red", line_width=1) 
    fig2 = style_plotly_fig(fig2)
    fig2.update_yaxes(rangemode="normal") 
    st.plotly_chart(fig2, use_container_width=True)

    # ------------------------------------------------
    # Base Scenario Summary Table
    # ------------------------------------------------
    st.divider()
    st.subheader("📊 Base Scenario Summary Table")
    st.markdown("A consolidated tabular view of the profitability and operational metrics based on your current sidebar inputs.")
    
    base_summary_df = pd.DataFrame({
        "Category": [
            "Financial", "Financial", "Financial", "Financial", "Financial", 
            "Operational", "Operational", "Operational", "Operational", "Operational",
            "Capital", "Capital"
        ],
        "Metric": [
            "Gross Profit (From Sales)", 
            "Total Holding Cost", 
            "Total Ordering Cost", 
            "Total Inventory Cost", 
            "Net Profit / Loss",
            "Total Demand", 
            "Total Sales Fulfilled", 
            "Missed Demand", 
            "Fill Rate", 
            "Stockout Days",
            "Avg Physical Inventory", 
            "Avg Working Capital"
        ],
        "Value": [
            f"${res['Gross Profit']:,.0f}",
            f"${res['Total Holding Cost']:,.0f}",
            f"${res['Total Ordering Cost']:,.0f}",
            f"${res['Total Inventory Cost']:,.0f}",
            f"${res['Net Profit']:,.0f}",
            f"{res['Total Demand']:,.0f} units",
            f"{res['Total Sales']:,.0f} units",
            f"{res['Missed Demand']:,.0f} units",
            f"{res['Fill Rate']:.2f}%",
            f"{res['Stockout Days']} days",
            f"{res['Avg Physical Inventory']:,.0f} units",
            f"${res['Avg Working Capital']:,.0f}"
        ]
    })
    
    st.dataframe(base_summary_df, use_container_width=True, hide_index=True)

    st.divider()

    # ------------------------------------------------
    # Sensitivity Analysis Section
    # ------------------------------------------------
    st.subheader("🔍 Scenario & Sensitivity Analysis")
    st.markdown("Create multiple scenarios using the input boxes below to compare working capital, fulfillment, and profitability tradeoffs.")
    
    # Create 3 columns for side-by-side scenario inputs
    col1, col2, col3 = st.columns(3)
    scenarios = []

    if policy == "Continuous Review":
        with col1:
            st.markdown("#### Scenario 1")
            s1_name = st.text_input("Scenario Name", value="Base Policy", key="s1_n")
            s1_p1 = st.number_input("Reorder Point", value=int(p1_val), key="s1_p1")
            s1_p2 = st.number_input("Order Quantity", value=int(p2_val), key="s1_p2")
            scenarios.append({"Scenario Name": s1_name, "Reorder Point": s1_p1, "Order Quantity": s1_p2})
        with col2:
            st.markdown("#### Scenario 2")
            s2_name = st.text_input("Scenario Name", value="Aggressive (Low ROP)", key="s2_n")
            s2_p1 = st.number_input("Reorder Point", value=int(p1_val * 0.8), key="s2_p1")
            s2_p2 = st.number_input("Order Quantity", value=int(p2_val * 1.2), key="s2_p2")
            scenarios.append({"Scenario Name": s2_name, "Reorder Point": s2_p1, "Order Quantity": s2_p2})
        with col3:
            st.markdown("#### Scenario 3")
            s3_name = st.text_input("Scenario Name", value="Conservative (High ROP)", key="s3_n")
            s3_p1 = st.number_input("Reorder Point", value=int(p1_val * 1.2), key="s3_p1")
            s3_p2 = st.number_input("Order Quantity", value=int(p2_val * 0.8), key="s3_p2")
            scenarios.append({"Scenario Name": s3_name, "Reorder Point": s3_p1, "Order Quantity": s3_p2})
    else:
        with col1:
            st.markdown("#### Scenario 1")
            s1_name = st.text_input("Scenario Name", value="Base Policy", key="sp1_n")
            s1_p1 = st.number_input("Review Period (Days)", value=int(p1_val), key="sp1_p1")
            s1_p2 = st.number_input("Order-Up-To Level (S)", value=int(p2_val), key="sp1_p2")
            scenarios.append({"Scenario Name": s1_name, "Review Period (Days)": s1_p1, "Order-Up-To Level (S)": s1_p2})
        with col2:
            st.markdown("#### Scenario 2")
            s2_name = st.text_input("Scenario Name", value="Frequent Reviews", key="sp2_n")
            s2_p1 = st.number_input("Review Period (Days)", value=max(1, int(p1_val - 2)), key="sp2_p1")
            s2_p2 = st.number_input("Order-Up-To Level (S)", value=int(p2_val * 0.8), key="sp2_p2")
            scenarios.append({"Scenario Name": s2_name, "Review Period (Days)": s2_p1, "Order-Up-To Level (S)": s2_p2})
        with col3:
            st.markdown("#### Scenario 3")
            s3_name = st.text_input("Scenario Name", value="Infrequent Reviews", key="sp3_n")
            s3_p1 = st.number_input("Review Period (Days)", value=int(p1_val + 2), key="sp3_p1")
            s3_p2 = st.number_input("Order-Up-To Level (S)", value=int(p2_val * 1.2), key="sp3_p2")
            scenarios.append({"Scenario Name": s3_name, "Review Period (Days)": s3_p1, "Order-Up-To Level (S)": s3_p2})

    edited_sens_df = pd.DataFrame(scenarios)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Run Comparative Analysis", type="primary"):
        with st.spinner("Simulating scenarios..."):
            sens_results = []
            scenario_inventories = {}  # Dictionary to store data for the graph
            
            for _, row in edited_sens_df.iterrows():
                # Extract values safely depending on policy
                s_p1 = row["Reorder Point"] if policy == "Continuous Review" else row["Review Period (Days)"]
                s_p2 = row["Order Quantity"] if policy == "Continuous Review" else row["Order-Up-To Level (S)"]
                    
                s_res = run_simulation(
                    sim_demand, policy, lead_time, s_p1, s_p2, opening_balance, 
                    max_wait_time, unit_value, unit_profit, holding_cost_pct, ordering_cost
                )
                
                # Store the daily physical inventory for the graph
                scenario_inventories[row["Scenario Name"]] = s_res['Physical Inventory']
                
                sens_results.append({
                    "Scenario": row["Scenario Name"],
                    "Reorder Point / Review Period": s_p1,
                    "Order Qty / Target Level (S)": s_p2,
                    "Fill Rate (%)": f"{s_res['Fill Rate']:.2f}%",
                    "Missed Demand": f"{s_res['Missed Demand']:,.0f}",
                    "Stockout Days": s_res['Stockout Days'],
                    "Avg Working Capital": f"${s_res['Avg Working Capital']:,.0f}",
                    "Gross Profit": f"${s_res['Gross Profit']:,.0f}",
                    "Holding Cost": f"${s_res['Total Holding Cost']:,.0f}",
                    "Ordering Cost": f"${s_res['Total Ordering Cost']:,.0f}",
                    "Total Inv Cost": f"${s_res['Total Inventory Cost']:,.0f}",
                    "Net Profit": f"${s_res['Net Profit']:,.0f}"
                })
                
            # Convert to DataFrame, set Scenario as index, transpose, and reset index for display
            df_res = pd.DataFrame(sens_results).set_index("Scenario").T.reset_index()
            df_res.rename(columns={"index": "Metric"}, inplace=True)
            
            st.dataframe(df_res, use_container_width=True, hide_index=True)

            # ------------------------------------------------
            # Scenario Comparison Chart
            # ------------------------------------------------
            st.markdown("##### 📈 Scenario Comparison: Physical Inventory Balance")
            fig_comp = go.Figure()
            
            for sc_name, inv_data in scenario_inventories.items():
                fig_comp.add_trace(go.Scatter(
                    x=df_filled[time_col], 
                    y=inv_data, 
                    mode="lines", 
                    name=sc_name,
                    opacity=0.8
                ))
            
            fig_comp = style_plotly_fig(fig_comp)
            st.plotly_chart(fig_comp, use_container_width=True)
