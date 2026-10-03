import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide")

# Custom CSS to add padding to the main container
st.markdown(
    """
    <style>
    /* Target the main content area */
    .block-container {
        padding-left: 5rem;
        padding-right: 5rem;
        padding-top: 2rem;
    }
    
    /* Optional: Adjust the sidebar width if it also interferes */
    [data-testid="stSidebar"] {
        padding-left: 4rem;
        # padding-right: 5rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Inventory Policy Simulator")

# ------------------------------------------------
# Sidebar Inputs
# ------------------------------------------------

st.sidebar.header("Inventory Inputs")

opening_balance = st.sidebar.number_input("Opening Balance", value=500)

avg_demand = st.sidebar.number_input("Average Demand", value=25)

variation_limit = st.sidebar.number_input("Demand Variation (+/-)", value=5)

use_beta_only = st.sidebar.checkbox("Only Beta Distribution", value=False)

lead_time = st.sidebar.number_input("Lead Time (Days)", value=3)

reorder_point = st.sidebar.number_input("Reorder Point", value=200)

order_qty = st.sidebar.number_input("Order Quantity", value=300)

unit_value = st.sidebar.number_input("Value Per Unit", value=100)

holding_cost_percent = st.sidebar.number_input(
    "Holding Cost (% of Inventory Value)", value=20.0
)

ordering_cost = st.sidebar.number_input(
    "Ordering Cost Per Order", value=500
)

num_days = st.sidebar.slider("Simulation Days", 100, 2000, 365)

holding_cost_rate = holding_cost_percent / 100

# ------------------------------------------------
# Reset Demand Scenario
# ------------------------------------------------

if "demand_sequence" not in st.session_state:
    st.session_state.demand_sequence = None

if st.button("Reset Demand Scenario"):
    st.session_state.demand_sequence = None

# ------------------------------------------------
# Demand Generation (Conditional Routing)
# ------------------------------------------------
if st.session_state.demand_sequence is None:
    min_demand = avg_demand - variation_limit
    max_demand = avg_demand + variation_limit
    
    if use_beta_only or min_demand < 0:
        # Use Scaled Beta Distribution to handle zero-bound skew
        if max_demand <= avg_demand or avg_demand <= 0:
            st.session_state.demand_sequence = np.full(num_days, max(0, avg_demand)).round()
        else:
            target_ratio = avg_demand / max_demand
            if target_ratio <= 0.5:
                a = 2.0
                b = a * (1 - target_ratio) / target_ratio
            else:
                b = 2.0
                a = b * target_ratio / (1 - target_ratio)
                
            raw_beta = np.random.beta(a, b, num_days)
            st.session_state.demand_sequence = (raw_beta * max_demand).round()
    else:
        # Use standard Uniform Distribution when limits are safely above zero
        st.session_state.demand_sequence = np.random.uniform(min_demand, max_demand, num_days).round()

demand = st.session_state.demand_sequence
dates = pd.date_range(start="2024-01-01", periods=num_days)

# ------------------------------------------------
# Inventory Simulation
# ------------------------------------------------

inventory = opening_balance
pipeline_orders = []
data = []

for day in range(num_days):

    shipment_received = 0

    for order in pipeline_orders.copy():
        if order[0] == day:
            shipment_received += order[1]
            pipeline_orders.remove(order)

    opening = inventory
    inventory += shipment_received

    demand_today = demand[day]
    inventory -= demand_today

    if inventory < 0:
        inventory = 0

    pipeline_qty = sum(qty for arrival, qty in pipeline_orders)

    inventory_position = opening - demand_today + shipment_received + pipeline_qty

    new_order = 0

    if inventory_position < reorder_point:
        new_order = order_qty
        pipeline_orders.append((day + lead_time, order_qty))

    closing = inventory

    closing_with_pipeline = closing + sum(qty for arrival, qty in pipeline_orders)

    data.append([
        dates[day],
        opening,
        demand_today,
        shipment_received,
        pipeline_qty,
        inventory_position,
        new_order,
        closing,
        closing_with_pipeline
    ])

df = pd.DataFrame(data, columns=[
    "Date",
    "Opening Balance",
    "Demand",
    "Shipment Received",
    "Pipeline Order",
    "Inventory Position",
    "New Order",
    "Closing Balance",
    "Closing Balance Including Pipeline"
])

# ------------------------------------------------
# KPI Calculations
# ------------------------------------------------

stockout_days = (df["Closing Balance"] == 0).sum()

# Fill Rate Calculation
df["Sales"] = df["Opening Balance"] + df["Shipment Received"] - df["Closing Balance"]
total_demand = df["Demand"].sum()
total_sales = df["Sales"].sum()
fill_rate = (total_sales / total_demand * 100) if total_demand > 0 else 100.0

average_inventory = df["Closing Balance Including Pipeline"].mean()

average_age_inventory = average_inventory / df["Demand"].mean()

df["Blocked Working Capital"] = df["Inventory Position"] * unit_value

average_working_capital = df["Blocked Working Capital"].mean()

min_inventory = df["Closing Balance"].min()
max_inventory = df["Closing Balance"].max()

min_wc = df["Blocked Working Capital"].min()
max_wc = df["Blocked Working Capital"].max()

# Cost calculations
df["Inventory Value"] = df["Closing Balance Including Pipeline"] * unit_value

df["Holding Cost"] = df["Inventory Value"] * holding_cost_rate / 365

total_holding_cost = df["Holding Cost"].sum()

number_of_orders = (df["New Order"] > 0).sum()

total_ordering_cost = number_of_orders * ordering_cost

total_inventory_cost = total_holding_cost + total_ordering_cost

# ------------------------------------------------
# EOQ Calculation
# ------------------------------------------------

annual_demand = avg_demand * 365

holding_cost_per_unit = unit_value * holding_cost_rate

eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)

# ------------------------------------------------
# Cost Comparison Function
# ------------------------------------------------

def simulate_inventory_cost(order_quantity):

    inventory = opening_balance
    pipeline_orders = []

    holding_cost_total = 0
    orders_count = 0

    for day in range(num_days):

        shipment_received = 0

        for order in pipeline_orders.copy():
            if order[0] == day:
                shipment_received += order[1]
                pipeline_orders.remove(order)

        inventory += shipment_received

        demand_today = demand[day]

        inventory -= demand_today

        if inventory < 0:
            inventory = 0

        pipeline_qty = sum(qty for arrival, qty in pipeline_orders)

        inventory_position = inventory + pipeline_qty

        if inventory_position < reorder_point:
            pipeline_orders.append((day + lead_time, order_quantity))
            orders_count += 1

        closing_with_pipeline = inventory + sum(qty for arrival, qty in pipeline_orders)

        inventory_value = closing_with_pipeline * unit_value

        holding_cost_today = inventory_value * holding_cost_rate / 365

        holding_cost_total += holding_cost_today

    ordering_cost_total = orders_count * ordering_cost

    total_cost = holding_cost_total + ordering_cost_total

    return total_cost

cost_current_policy = simulate_inventory_cost(order_qty)
cost_eoq_policy = simulate_inventory_cost(int(eoq))

# ------------------------------------------------
# KPI Display
# ------------------------------------------------

st.subheader("Inventory KPIs")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Fill Rate", f"{fill_rate:.1f}%")
c2.metric("Stockout Days", stockout_days)
c3.metric("Avg Age of Inventory", round(average_age_inventory,1))
c4.metric("Avg Inventory", round(average_inventory,0))
c5.metric("Avg Working Capital", round(average_working_capital,0))

st.subheader("Inventory Range")

r1, r2, r3, r4 = st.columns(4)

r1.metric("Minimum Inventory", round(min_inventory,0))
r2.metric("Maximum Inventory", round(max_inventory,0))
r3.metric("Minimum Working Capital", round(min_wc,0))
r4.metric("Maximum Working Capital", round(max_wc,0))

st.subheader("Inventory Cost Metrics")

cc1, cc2, cc3 = st.columns(3)

cc1.metric("Total Holding Cost", round(total_holding_cost,0))
cc2.metric("Total Ordering Cost", round(total_ordering_cost,0))
cc3.metric("Total Inventory Cost", round(total_inventory_cost,0))

st.subheader("EOQ")

e1, e2 = st.columns(2)

e1.metric("Economic Order Quantity", round(eoq,0))
e2.metric("Selected Order Quantity", order_qty)

st.subheader("Cost Comparison")

k1, k2, k3 = st.columns(3)

k1.metric("Cost with Current Policy", round(cost_current_policy,0))
k2.metric("Cost with EOQ", round(cost_eoq_policy,0))
k3.metric("Savings Using EOQ", round(cost_current_policy-cost_eoq_policy,0))

st.divider()

# ------------------------------------------------
# Inventory Behaviour Chart
# ------------------------------------------------

st.subheader("Inventory Behaviour")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Date"],
    y=df["Closing Balance"],
    name="Closing Inventory"
))

fig.add_trace(go.Scatter(
    x=df["Date"],
    y=df["Closing Balance Including Pipeline"],
    name="Inventory Position"
))

fig.add_hline(y=reorder_point,line_dash="dash",annotation_text="Reorder Point")

stockouts = df[df["Closing Balance"] == 0]

fig.add_trace(go.Scatter(
    x=stockouts["Date"],
    y=stockouts["Closing Balance"],
    mode="markers",
    name="Stockout",
    marker=dict(color="red",size=9)
))

reorders = df[df["New Order"] > 0]

fig.add_trace(go.Scatter(
    x=reorders["Date"],
    y=reorders["Closing Balance"],
    mode="markers",
    name="Reorder Trigger",
    marker=dict(color="green",symbol="triangle-up",size=10)
))

fig.add_hrect(y0=0,y1=reorder_point*0.5,fillcolor="red",opacity=0.08)
fig.add_hrect(y0=reorder_point*0.5,y1=reorder_point,fillcolor="yellow",opacity=0.08)
fig.add_hrect(y0=reorder_point,
              y1=df["Closing Balance Including Pipeline"].max()*1.2,
              fillcolor="green",
              opacity=0.05)

fig.update_yaxes(rangemode="tozero")

st.plotly_chart(fig,use_container_width=True)

# ------------------------------------------------
# Data Table
# ------------------------------------------------

st.subheader("Simulation Data")

st.dataframe(df)


# ------------------------------------------------
# Pipeline Inventory Chart
# ------------------------------------------------

st.subheader("Pipeline Inventory")

fig_pipeline = px.line(df,x="Date",y="Pipeline Order")

st.plotly_chart(fig_pipeline,use_container_width=True)

# ------------------------------------------------
# Orders Chart
# ------------------------------------------------

st.subheader("Orders Placed")

orders = df[df["New Order"]>0]

fig_orders = px.scatter(orders,x="Date",y="New Order")

st.plotly_chart(fig_orders,use_container_width=True)

# ------------------------------------------------
# Demand Histogram
# ------------------------------------------------

st.subheader("Demand Distribution")

fig_hist = px.histogram(df,x="Demand",nbins=20)

st.plotly_chart(fig_hist,use_container_width=True)

# ------------------------------------------------
# Working Capital Chart
# ------------------------------------------------

st.subheader("Blocked Working Capital")

fig_wc = px.line(df,x="Date",y="Blocked Working Capital")

st.plotly_chart(fig_wc,use_container_width=True)

# ------------------------------------------------
# Inventory Waterfall
# ------------------------------------------------

st.subheader("Inventory Flow Waterfall")

selected_day = st.slider("Select Day",0,len(df)-1,0)

row = df.iloc[selected_day]

fig_waterfall = go.Figure(go.Waterfall(

    measure=["absolute","relative","relative","total"],

    x=["Opening Balance","Demand","Shipment Received","Closing Balance"],

    y=[
        row["Opening Balance"],
        -row["Demand"],
        row["Shipment Received"],
        row["Closing Balance"]
    ]

))

st.plotly_chart(fig_waterfall,use_container_width=True)

