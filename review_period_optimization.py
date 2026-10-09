import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math
import scipy.stats as stats

# ------------------------------------------------
# Plotly Dark Theme Styling
# ------------------------------------------------
def style_plotly_fig(fig):
    fig.update_layout(
        plot_bgcolor='#0E1117', paper_bgcolor='#0E1117', font=dict(color='white'),
        title_font=dict(color='white'), legend=dict(font=dict(color='white'), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', gridcolor='#2b2b2b')
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', gridcolor='#2b2b2b', rangemode="tozero")
    return fig

st.title("Multi-SKU Joint Replenishment Optimization")
st.write("Determine the optimal synchronized review period for multiple SKUs sharing transport and ordering costs.")

# ------------------------------------------------
# Global Logistics Parameters
# ------------------------------------------------
st.sidebar.header("Global Logistics Parameters")
cost_per_shipment = st.sidebar.number_input("Cost per Shipment ($)", value=1000.0, step=100.0)
max_volume_per_shipment = st.sidebar.number_input("Max Volume per Shipment (CBM/Units)", value=2000.0, step=100.0)
lead_time = st.sidebar.number_input("Lead Time (Days)", min_value=1, value=5, step=1)
holding_cost_pct = st.sidebar.number_input("Annual Holding Cost (%)", min_value=1.0, value=20.0, step=1.0) / 100.0

# ------------------------------------------------
# SKU Data Entry (Editable Grid)
# ------------------------------------------------
st.subheader("SKU Portfolio Parameters")
st.markdown("Add, edit, or remove SKUs. Volume per Unit determines how much space a single unit occupies in a shipment.")

# Default starting data
default_skus = pd.DataFrame({
    "SKU": ["SKU-A (High Mover)", "SKU-B (Medium Mover)", "SKU-C (Slow Mover)"],
    "Avg Daily Demand": [150.0, 50.0, 10.0],
    "Std Dev Demand": [30.0, 15.0, 5.0],
    "Unit Cost ($)": [25.0, 80.0, 200.0],
    "Service Level (%)": [98.0, 95.0, 90.0],
    "Volume per Unit": [1.0, 2.5, 5.0]
})

# Use st.data_editor for dynamic multi-SKU input
sku_df = st.data_editor(
    default_skus, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Service Level (%)": st.column_config.NumberColumn(min_value=50.0, max_value=99.99),
        "Unit Cost ($)": st.column_config.NumberColumn(min_value=0.01),
        "Avg Daily Demand": st.column_config.NumberColumn(min_value=0.01),
        "Volume per Unit": st.column_config.NumberColumn(min_value=0.01)
    }
)

# ------------------------------------------------
# Joint Optimization Engine
# ------------------------------------------------
if st.button("Optimize Joint Review Period", type="primary"):
    with st.spinner("Calculating optimal synchronized review period..."):
        
        # Validate data
        if sku_df.empty or sku_df["Avg Daily Demand"].sum() == 0:
            st.error("Please add at least one valid SKU with demand.")
            st.stop()
            
        # Pre-calculate SKU specific constants
        sku_params = []
        for _, row in sku_df.iterrows():
            z_score = stats.norm.ppf(row["Service Level (%)"] / 100.0)
            sku_params.append({
                "sku": row["SKU"],
                "d": row["Avg Daily Demand"],
                "std": row["Std Dev Demand"],
                "c": row["Unit Cost ($)"],
                "z": z_score,
                "vol": row["Volume per Unit"]
            })
            
        # Iterate over possible Review Periods (T) from 1 to 90 days
        results = []
        for t in range(1, 91):
            total_holding_cost = 0
            total_cycle_volume = 0
            
            # Calculate metrics per SKU for this T
            for p in sku_params:
                # Standard Deviation over Lead Time + Review Period
                std_dev_lt = p["std"] * math.sqrt(t + lead_time)
                safety_stock = p["z"] * std_dev_lt
                
                # Average Inventory = Safety Stock + (Cycle Stock / 2)
                cycle_stock = p["d"] * t
                avg_inv = safety_stock + (cycle_stock / 2)
                
                total_holding_cost += avg_inv * p["c"] * holding_cost_pct
                total_cycle_volume += cycle_stock * p["vol"]
                
            # Calculate Logistics/Ordering Costs
            # How many shipments are needed to move the total cycle volume?
            shipments_per_cycle = math.ceil(total_cycle_volume / max_volume_per_shipment) if max_volume_per_shipment > 0 else 1
            cycles_per_year = 365 / t
            
            total_ordering_cost = cycles_per_year * shipments_per_cycle * cost_per_shipment
            total_cost = total_holding_cost + total_ordering_cost
            
            results.append({
                "Review Period (Days)": t,
                "Holding Cost ($)": total_holding_cost,
                "Ordering Cost ($)": total_ordering_cost,
                "Total Cost ($)": total_cost,
                "Shipments per Cycle": shipments_per_cycle,
                "Total Volume per Cycle": total_cycle_volume
            })
            
        df_results = pd.DataFrame(results)
        opt_t_row = df_results.loc[df_results["Total Cost ($)"].idxmin()]
        opt_t = int(opt_t_row["Review Period (Days)"])
        
        # ------------------------------------------------
        # Dashboard Results Rendering
        # ------------------------------------------------
        st.divider()
        st.subheader("Optimization Results")
        
        st.success(f"**Optimal Synchronized Review Period (T):** {opt_t} days")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Minimum Total Annual Cost", f"${opt_t_row['Total Cost ($)']:,.0f}")
        c2.metric("Annual Holding Cost", f"${opt_t_row['Holding Cost ($)']:,.0f}")
        c3.metric("Annual Ordering Cost", f"${opt_t_row['Ordering Cost ($)']:,.0f}")
        c4.metric("Avg Shipments per Order Cycle", f"{opt_t_row['Shipments per Cycle']:.0f}")

        # Cost Curves Plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_results["Review Period (Days)"], y=df_results["Holding Cost ($)"], mode="lines", name="Total Holding Cost", line=dict(color="orange")))
        
        # Ordering cost will be "step-like" due to shipment capacity boundaries
        fig.add_trace(go.Scatter(x=df_results["Review Period (Days)"], y=df_results["Ordering Cost ($)"], mode="lines", name="Total Ordering Cost", line=dict(color="cyan", shape='hv')))
        fig.add_trace(go.Scatter(x=df_results["Review Period (Days)"], y=df_results["Total Cost ($)"], mode="lines", name="Total Combined Cost", line=dict(color="lightgreen", width=3)))
        
        fig.add_vline(x=opt_t, line_dash="dash", line_color="white", annotation_text=f"Optimal T: {opt_t}", annotation_position="top right")
        fig.update_layout(title="Multi-SKU Joint Costs vs. Review Period", xaxis_title="Review Period (Days)", yaxis_title="Annual Cost ($)")
        st.plotly_chart(style_plotly_fig(fig), use_container_width=True)
        
        # ------------------------------------------------
        # SKU-Level Target Metrics at Optimal T
        # ------------------------------------------------
        st.markdown(f"#### SKU Policies at Optimal Review Period ({opt_t} Days)")
        
        optimal_sku_breakdown = []
        for p in sku_params:
            std_dev_lt = p["std"] * math.sqrt(opt_t + lead_time)
            safety_stock = p["z"] * std_dev_lt
            target_level = (p["d"] * (opt_t + lead_time)) + safety_stock
            avg_inv = safety_stock + ((p["d"] * opt_t) / 2)
            
            optimal_sku_breakdown.append({
                "SKU": p["sku"],
                "Target Level (Order-Up-To)": target_level,
                "Safety Stock": safety_stock,
                "Average Inventory": avg_inv,
                "Annual Holding Cost ($)": avg_inv * p["c"] * holding_cost_pct
            })
            
        df_breakdown = pd.DataFrame(optimal_sku_breakdown)
        st.dataframe(
            df_breakdown.style.format({
                "Target Level (Order-Up-To)": "{:,.0f}",
                "Safety Stock": "{:,.0f}",
                "Average Inventory": "{:,.0f}",
                "Annual Holding Cost ($)": "${:,.0f}"
            }), 
            use_container_width=True, 
            hide_index=True
        )
