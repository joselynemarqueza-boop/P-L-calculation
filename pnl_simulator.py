import streamlit as st
import pandas as pd

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="BeautyLab – P&L Visualizer",
    layout="wide",
    page_icon="📊"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
    <style>
    .stDataFrame { width: 100% !important; }
    .stMetric { 
        background-color: #f8f9fa; 
        border-radius: 10px; 
        padding: 15px; 
        border: 1px solid #e0e0e0; 
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #2C2C3E;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .footer {
        margin-top: 3rem;
        font-size: 0.8rem;
        color: #999;
        text-align: center;
        border-top: 1px solid #eee;
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA LOADING & CALCULATION ENGINE
# ============================================================================
@st.cache_data
def load_and_calculate():
    """Load CSV files and calculate P&L up to GP Std."""
    
    # 1. Load files
    pricing = pd.read_csv("pricing.csv")
    gtn = pd.read_csv("GTN.csv")
    volume = pd.read_csv("volume.csv")

    # 2. Normalize months in GTN
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    gtn["month_num"] = gtn["month"].map(month_map)

    # 3. Structural GTN (Annual, All categories)
    gtn_structural = (
        gtn[(gtn["month"] == "Annual") & (gtn["category"] == "All")]
        .groupby(["client_code", "client_name"], as_index=False)
        .agg(structural_gtn_pct=("gtn_pct", "sum"))
    )

    # 4. Tactical GTN (by month, client, category)
    gtn_tactical = (
        gtn[gtn["month"] != "Annual"]
        .groupby(["month_num", "client_code", "client_name", "category"], as_index=False)
        .agg(tactical_gtn_pct=("gtn_pct", "sum"))
    )

    # 5. Merge volume with pricing
    pxq = volume.merge(
        pricing,
        on=["client_code", "client_name", "channel", "sku", "product_name", "category"],
        how="left"
    )

    # 6. Calculate Gross Sales and COGS
    pxq["gross_sales"] = pxq["units_sold"] * pxq["price_to_client_gbp"]
    pxq["cogs"] = pxq["units_sold"] * pxq["cogs_per_unit_gbp"]

    # 7. Merge Structural GTN
    pxq = pxq.merge(
        gtn_structural[["client_code", "structural_gtn_pct"]],
        on="client_code",
        how="left"
    )
    pxq["structural_gtn_pct"] = pxq["structural_gtn_pct"].fillna(0.0)

    # 8. Merge Tactical GTN
    pxq = pxq.merge(
        gtn_tactical[["month_num", "client_code", "category", "tactical_gtn_pct"]],
        left_on=["month", "client_code", "category"],
        right_on=["month_num", "client_code", "category"],
        how="left"
    )
    pxq["tactical_gtn_pct"] = pxq["tactical_gtn_pct"].fillna(0.0)

    # 9. P&L Calculations
    pxq["total_gtn_pct"] = pxq["structural_gtn_pct"] + pxq["tactical_gtn_pct"]
    pxq["returns"] = pxq["gross_sales"] * 0.02
    pxq["bonus"] = pxq["gross_sales"] * 0.015
    pxq["gtn_amount"] = pxq["gross_sales"] * pxq["total_gtn_pct"]
    pxq["nts"] = pxq["gross_sales"] - pxq["returns"] - pxq["bonus"] - pxq["gtn_amount"]
    pxq["gp_std"] = pxq["nts"] - pxq["cogs"]
    pxq["gp_std_pct"] = (pxq["gp_std"] / pxq["nts"] * 100).round(1)

    # 10. Define column order
    column_order = [
        "year", "month", "client_code", "client_name", "channel",
        "sku", "product_name", "category", "units_sold",
        "gross_sales", "returns", "bonus",
        "structural_gtn_pct", "tactical_gtn_pct", "total_gtn_pct", "gtn_amount",
        "nts", "cogs", "gp_std", "gp_std_pct"
    ]

    return pxq[column_order].copy()

# ============================================================================
# LOAD DATA
# ============================================================================
st.markdown('<p class="main-header">📊 BeautyLab</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">P&L Visualizer — Gross Trade Sales to GP Std</p>', unsafe_allow_html=True)

with st.spinner("Loading and calculating data..."):
    df = load_and_calculate()

st.success(f"✅ Data loaded: {len(df):,} rows")

# ============================================================================
# SIDEBAR FILTERS
# ============================================================================
with st.sidebar:
    st.header("🔍 Filters")
    st.divider()

    # Year filter
    year_options = sorted(df["year"].unique(), reverse=True)
    selected_year = st.selectbox("Year", year_options)

    # Month filter (multi-select)
    month_options = sorted(df[df["year"] == selected_year]["month"].unique())
    selected_months = st.multiselect(
        "Months",
        options=month_options,
        default=month_options
    )

    # Client filter (multi-select)
    client_options = sorted(df[df["year"] == selected_year]["client_name"].unique())
    selected_clients = st.multiselect(
        "Clients",
        options=client_options,
        default=client_options
    )

    # Channel filter (multi-select)
    channel_options = sorted(df[df["year"] == selected_year]["channel"].unique())
    selected_channels = st.multiselect(
        "Channels",
        options=channel_options,
        default=channel_options
    )

    # Category filter (multi-select)
    cat_options = sorted(df[df["year"] == selected_year]["category"].unique())
    selected_cats = st.multiselect(
        "Categories",
        options=cat_options,
        default=cat_options
    )

    # SKU filter (multi-select)
    sku_options = sorted(df[df["year"] == selected_year]["sku"].unique())
    selected_skus = st.multiselect(
        "SKUs",
        options=sku_options,
        default=sku_options
    )

    st.divider()
    st.caption("📈 Summary metrics shown below for filtered data")

# ============================================================================
# APPLY FILTERS
# ============================================================================
df_filtered = df[
    (df["year"] == selected_year) &
    (df["month"].isin(selected_months)) &
    (df["client_name"].isin(selected_clients)) &
    (df["channel"].isin(selected_channels)) &
    (df["category"].isin(selected_cats)) &
    (df["sku"].isin(selected_skus))
]

# ============================================================================
# TOP METRICS
# ============================================================================
col1, col2, col3, col4, col5 = st.columns(5)

total_units = df_filtered["units_sold"].sum()
total_gts = df_filtered["gross_sales"].sum()
total_nts = df_filtered["nts"].sum()
total_gp = df_filtered["gp_std"].sum()
gp_pct = (total_gp / total_nts * 100) if total_nts > 0 else 0

col1.metric("📦 Units", f"{total_units:,.0f}")
col2.metric("💰 Gross Sales", f"£{total_gts:,.2f}")
col3.metric("📊 NTS", f"£{total_nts:,.2f}")
col4.metric("💎 GP Std", f"£{total_gp:,.2f}")
col5.metric("📈 GP %", f"{gp_pct:.1f}%")

st.divider()

# ============================================================================
# DATA TABLE
# ============================================================================
st.subheader("📋 P&L Detail")

# Display columns
display_cols = [
    "year", "month", "client_name", "channel", "category", 
    "sku", "product_name", "units_sold", 
    "gross_sales", "returns", "bonus",
    "structural_gtn_pct", "tactical_gtn_pct", "total_gtn_pct", "gtn_amount",
    "nts", "cogs", "gp_std", "gp_std_pct"
]

df_display = df_filtered[display_cols].copy()

# Rename columns for display
df_display.columns = [
    "Year", "Month", "Client", "Channel", "Category", 
    "SKU", "Product", "Units", 
    "Gross Sales", "Returns", "Bonus",
    "Structural GTN %", "Tactical GTN %", "Total GTN %", "GTN £",
    "NTS", "COGS", "GP Std", "GP %"
]

st.caption(f"Showing {len(df_display):,} rows")

# Format and display
st.dataframe(
    df_display.style.format({
        "Units": "{:,.0f}",
        "Gross Sales": "£{:,.2f}",
        "Returns": "£{:,.2f}",
        "Bonus": "£{:,.2f}",
        "Structural GTN %": "{:.1%}",
        "Tactical GTN %": "{:.1%}",
        "Total GTN %": "{:.1%}",
        "GTN £": "£{:,.2f}",
        "NTS": "£{:,.2f}",
        "COGS": "£{:,.2f}",
        "GP Std": "£{:,.2f}",
        "GP %": "{:.1f}%"
    }),
    use_container_width=True,
    hide_index=True,
    height=500
)

# ============================================================================
# DOWNLOAD BUTTONS
# ============================================================================
st.divider()

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])

with col_btn1:
    csv_filtered = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Filtered CSV",
        data=csv_filtered,
        file_name=f"beautylab_pl_{selected_year}_filtered.csv",
        mime="text/csv",
        use_container_width=True
    )

with col_btn2:
    csv_full = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Full CSV",
        data=csv_full,
        file_name="beautylab_pl_full.csv",
        mime="text/csv",
        use_container_width=True
    )

# ============================================================================
# FOOTER
# ============================================================================
st.divider()
st.markdown(
    """
    <div class="footer">
        BeautyLab — P&L Visualizer &bull; Data up to GP Std &bull; 
        Built with Streamlit
    </div>
    """,
    unsafe_allow_html=True
)