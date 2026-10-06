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
    try:
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
