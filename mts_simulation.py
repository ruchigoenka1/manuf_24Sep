import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# =========================================================================
# 1. AUTHENTICATION & SESSION STATE CHECK
# =========================================================================
if not st.session_state.get("authentication_status"):
    st.warning("Please log in from the main app page.")
    st.stop()

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
st.markdown("Define the parameters for each SKU. The factory receives replenishment orders from the warehouse, takes the specified **Touch Time** to produce, and then ships it via the **Transit Time**.")

num_skus = st.number_input("Number of SKUs to Simulate", min_value=1, max_value=20, value=2, step=1)

# Generate default configuration table dynamically based on number of SKUs
default_skus = []
for i in range(int(num_skus)):
    default_skus.append({
        "SKU": f"SKU_{i+1:02d}",
        "Dist Type": "Normal" if i % 2 == 0 else "Uniform",
        "Avg Demand": 50 + (i * 10),
        "Variation / Range": 15,
        "Order Qty (Q)": 500,
        "Factory Touch Time (Days)": 7,
        "Transit to WH (Days)": 3,
        "WH Reorder Point (ROP)": 300,
        "Initial WH Inventory": 400,
        "Initial Pipeline (WIP)": 0
    })

df_default = pd.DataFrame(default_skus)

st.subheader("📋 Step 1: SKU Parameter Matrix")
st.info("💡 **Tip:** If 'Dist Type' is Normal, 'Variation' is Standard Deviation. If Uniform, it represents the +/- range around the average.")

edited_df = st.data_editor(
    df_default, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Dist Type": st.column_config.SelectboxColumn(options=["Normal", "Uniform"])
    }
)

# =========================================================================
# 4. SIMULATION ENGINE
# =========================================================================
st.markdown("---")

if st.button("🚀 Run MTS Simulation", type="primary"):
    np.random.seed(int(seed_val))
    
    # Dictionaries to store results for each SKU
    kpi_results = []
    wh_inv_history = {}
    factory_wip_history = {}
    demand_history = {}
    
    with st.spinner("Simulating supply chain physics..."):
        for index, row in edited_df.iterrows():
            sku = str(row["SKU"])
            dist_type = str(row["Dist Type"])
            avg_d = float(row["Avg Demand"])
            var_d = float(row["Variation / Range"])
            order_q = int(row["Order Qty (Q)"])
            touch_time = int(row["Factory Touch Time (Days)"])
            transit_time = int(row["Transit to WH (Days)"])
            rop = int(row["WH Reorder Point (ROP)"])
            init_inv = int(row["Initial WH Inventory"])
            init_pipe = int(row["Initial Pipeline (WIP)"])
            
            # 1. Generate Demand Array
            if dist_type == "Normal":
                demands = np.maximum(0, np.random.normal(avg_d, var_d, sim_days)).round()
            else:
                demands = np.random.uniform(max(0, avg_d - var_d), avg_d + var_d, sim_days).round()
                
            # 2. Tracking Arrays
            inv_levels = np.zeros(sim_days)
            factory_wip = np.zeros(sim_days) # Order Book volume actively being produced
            sales = np.zeros(sim_days)
            
            # Initial states
            current_inv = init_inv
            
            # Pipeline tracks future arrivals: list of dicts {'qty': x, 'ready_day': factory_finish, 'arrive_day': wh_receive}
            pipeline = []
            if init_pipe > 0:
                # Assume initial pipeline is already halfway through transit for simplicity
                pipeline.append({'qty': init_pipe, 'ready_day': 0, 'arrive_day': int(transit_time / 2)})
            
            active_factory_orders = [] # Tracks orders currently on the factory floor
            
            for day in range(sim_days):
                # A. Receive incoming shipments to WH
                arriving_today = sum(p['qty'] for p in pipeline if p['arrive_day'] == day)
                current_inv += arriving_today
                
                # Clean up arrived orders from pipeline
                pipeline = [p for p in pipeline if p['arrive_day'] > day]
                
                # B. Fulfill Demand
                today_demand = demands[day]
                sold = min(current_inv, today_demand)
                current_inv -= sold
                sales[day] = sold
                inv_levels[day] = current_inv
                
                # C. Check Inventory Position & Reorder
                on_order_qty = sum(p['qty'] for p in pipeline)
                inv_position = current_inv + on_order_qty
                
                if inv_position <= rop:
                    # Place order to factory
                    ready_at = day + touch_time
                    arrive_at = ready_at + transit_time
                    pipeline.append({'qty': order_q, 'ready_day': ready_at, 'arrive_day': arrive_at})
                    active_factory_orders.append({'qty': order_q, 'ready_day': ready_at})
                
                # D. Calculate active Factory Order Book (WIP)
                # Remove completed factory orders
                active_factory_orders = [f for f in active_factory_orders if f['ready_day'] > day]
                factory_wip[day] = sum(f['qty'] for f in active_factory_orders)
            
            # 3. Calculate KPIs
            total_dem = demands.sum()
            total_sales = sales.sum()
            fill_rate = (total_sales / total_dem) * 100 if total_dem > 0 else 0
            stockout_days = np.count_nonzero(demands > sales)
            
            kpi_results.append({
                "SKU": sku,
                "Fill Rate (%)": fill_rate,
                "Stockout Days": stockout_days,
                "Min Inventory": inv_levels.min(),
                "Max Inventory": inv_levels.max(),
                "Avg Inventory": inv_levels.mean()
            })
            
            wh_inv_history[sku] = inv_levels
            factory_wip_history[sku] = factory_wip
            demand_history[sku] = demands
            
    # =========================================================================
    # 5. DASHBOARD & VISUALIZATIONS
    # =========================================================================
    st.success(f"Simulation completed for {int(sim_days)} days across {len(edited_df)} SKUs.")
    
    st.subheader("📊 Warehouse KPI Scorecard")
    df_kpi = pd.DataFrame(kpi_results)
    
    # Format the KPI table
    st.dataframe(
        df_kpi.style.format({
            "Fill Rate (%)": "{:.2f}%",
            "Stockout Days": "{:.0f}",
            "Min Inventory": "{:.0f}",
            "Max Inventory": "{:.0f}",
            "Avg Inventory": "{:.1f}"
        }).background_gradient(subset=['Fill Rate (%)'], cmap='RdYlGn', vmin=80, vmax=100)
          .background_gradient(subset=['Stockout Days'], cmap='Reds', vmin=0, vmax=sim_days*0.1),
        use_container_width=True, hide_index=True
    )
    
    st.markdown("---")
    
    # Dual-chart layout
    st.subheader("📈 Multi-Echelon Trajectory Analysis")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown("#### Warehouse: Closing Inventory Level")
        fig_wh = go.Figure()
        for sku, data in wh_inv_history.items():
            fig_wh.add_trace(go.Scatter(
                x=np.arange(1, sim_days + 1), 
                y=data, 
                mode='lines', 
                name=sku,
                opacity=0.8
            ))
        fig_wh.add_hline(y=0, line_width=1, line_color="black")
        fig_wh.update_layout(
            xaxis_title="Simulation Day", 
            yaxis_title="Units on Hand",
            template="plotly_white",
            height=400,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_wh, use_container_width=True)
        
    with chart_col2:
        st.markdown("#### Factory: Active Order Book (WIP)")
        st.caption("Volume of stock currently in the 'Touch Time' production phase.")
        fig_fac = go.Figure()
        for sku, data in factory_wip_history.items():
            # Use step-line formatting to clearly show batch orders entering and leaving the factory
            fig_fac.add_trace(go.Scatter(
                x=np.arange(1, sim_days + 1), 
                y=data, 
                mode='lines', 
                line_shape='step',
                name=sku,
                opacity=0.8
            ))
        fig_fac.update_layout(
            xaxis_title="Simulation Day", 
            yaxis_title="Units in Production",
            template="plotly_white",
            height=400,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_fac, use_container_width=True)
        
    st.markdown("---")
    
    with st.expander("🔍 Deep Dive: SKU Demand vs Fulfillment Overlay"):
        selected_sku = st.selectbox("Select SKU to inspect daily demand variance:", df_default["SKU"].tolist())
        
        if selected_sku:
            fig_drill = go.Figure()
            # Plot Inventory
            fig_drill.add_trace(go.Scatter(
                x=np.arange(1, sim_days + 1), y=wh_inv_history[selected_sku], 
                mode='lines', name="WH Inventory", line=dict(color="#1f77b4", width=2),
                fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'
            ))
            # Plot Demand as red bars
            fig_drill.add_trace(go.Bar(
                x=np.arange(1, sim_days + 1), y=demand_history[selected_sku], 
                name="Daily Demand", marker_color="#d62728", opacity=0.4
            ))
            
            fig_drill.update_layout(
                title=f"{selected_sku}: Day-by-Day Volatility",
                xaxis_title="Day", 
                yaxis_title="Units",
                template="plotly_white",
                height=400,
                barmode='overlay',
                hovermode="x unified"
            )
            st.plotly_chart(fig_drill, use_container_width=True)
