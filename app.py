import streamlit as st
import pandas as pd
from pathlib import Path

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
# FILE PATHS
# ============================================================================
DATA_DIR = Path("Data")

PRICING_PATH = DATA_DIR / "pricing.csv"
GTN_PATH = DATA_DIR / "GTN.csv"
VOLUME_PATH = DATA_DIR / "volume.csv"

# ============================================================================
# DATA LOADING & CALCULATION ENGINE
# ============================================================================
@st.cache_data
def load_and_calculate():
    """Load CSV files and calculate P&L up to GP Std."""
    
    pricing = pd.read_csv(PRICING_PATH)
    gtn = pd.read_csv(GTN_PATH)
    volume = pd.read_csv(VOLUME_PATH)

    # Normalize months
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    gtn["month_num"] = gtn["month"].map(month_map)

    # Structural GTN
    gtn_structural = (
        gtn[(gtn["month"] == "Annual") & (gtn["category"] == "All")]
        .groupby(["client_code", "client_name"], as_index=False)
        .agg(structural_gtn_pct=("gtn_pct", "sum"))
    )

    # Tactical GTN
    gtn_tactical = (
        gtn[gtn["month"] != "Annual"]
        .groupby(["month_num", "client_code", "client_name", "category"], as_index=False)
        .agg(tactical_gtn_pct=("gtn_pct", "sum"))
    )

    # Merge volume with pricing
    pxq = volume.merge(
        pricing,
        on=["client_code", "client_name", "channel", "sku", "product_name", "category"],
        how="left"
    )

    # Calculate Gross Sales and COGS
    pxq["gross_sales"] = pxq["units_sold"] * pxq["price_to_client_gbp"]
    pxq["cogs"] = pxq["units_sold"] * pxq["cogs_per_unit_gbp"]

    # Merge Structural GTN
    pxq = pxq.merge(
        gtn_structural[["client_code", "structural_gtn_pct"]],
        on="client_code",
        how="left"
    )
    pxq["structural_gtn_pct"] = pxq["structural_gtn_pct"].fillna(0.0)

    # Merge Tactical GTN
    pxq = pxq.merge(
        gtn_tactical[["month_num", "client_code", "category", "tactical_gtn_pct"]],
        left_on=["month", "client_code", "category"],
        right_on=["month_num", "client_code", "category"],
        how="left"
    )
    pxq["tactical_gtn_pct"] = pxq["tactical_gtn_pct"].fillna(0.0)

    # P&L Calculations
    pxq["total_gtn_pct"] = pxq["structural_gtn_pct"] + pxq["tactical_gtn_pct"]
    pxq["returns"] = pxq["gross_sales"] * 0.02
    pxq["bonus"] = pxq["gross_sales"] * 0.015
    pxq["gtn_amount"] = pxq["gross_sales"] * pxq["total_gtn_pct"]
    pxq["nts"] = pxq["gross_sales"] - pxq["returns"] - pxq["bonus"] - pxq["gtn_amount"]
    pxq["gp_std"] = pxq["nts"] - pxq["cogs"]
    pxq["gp_std_pct"] = (pxq["gp_std"] / pxq["nts"] * 100).round(1)

    # Define column order
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

# Check files exist
if not PRICING_PATH.exists() or not GTN_PATH.exists() or not VOLUME_PATH.exists():
    st.error("❌ One or more CSV files not found in 'Data/' folder.")
    st.stop()

with st.spinner("Loading and calculating data..."):
    df = load_and_calculate()

st.success(f"✅ Data loaded: {len(df):,} rows")

# ============================================================================
# SIDEBAR FILTERS
# ============================================================================
with st.sidebar:
    st.header("🔍 Filters")
    st.divider()

    # Year
    year_options = sorted(df["year"].unique(), reverse=True)
    selected_year = st.selectbox("Year", year_options)

    # Client (multi-select)
    client_options = sorted(df[df["year"] == selected_year]["client_name"].unique())
    selected_clients = st.multiselect(
        "Clients",
        options=client_options,
        default=client_options
    )

    # Category (multi-select)
    cat_options = sorted(df[df["year"] == selected_year]["category"].unique())
    selected_cats = st.multiselect(
        "Categories",
        options=cat_options,
        default=cat_options
    )

    st.divider()
    st.caption("📈 Metrics update based on filters")

# ============================================================================
# APPLY BASE FILTERS (Year, Client, Category)
# ============================================================================
df_filtered = df[
    (df["year"] == selected_year) &
    (df["client_name"].isin(selected_clients)) &
    (df["category"].isin(selected_cats))
]

# ============================================================================
# TABS
# ============================================================================
tab_summary, tab_monthly, tab_raw = st.tabs([
    "📊 P&L Summary (Annual)",
    "📈 Monthly P&L",
    "📋 Raw Data"
])

# ============================================================================
# TAB 1: P&L SUMMARY (ANNUAL)
# ============================================================================
with tab_summary:
    st.subheader(f"Annual P&L Summary – {selected_year}")

    # Aggregate by year (annual)
    df_annual = df_filtered.groupby("year").agg({
        "gross_sales": "sum",
        "returns": "sum",
        "bonus": "sum",
        "gtn_amount": "sum",
        "nts": "sum",
        "cogs": "sum",
        "gp_std": "sum"
    }).reset_index()

    # Calculate percentages
    df_annual["gross_sales_pct"] = (df_annual["gross_sales"] / df_annual["gross_sales"] * 100).round(1)
    df_annual["returns_pct"] = (df_annual["returns"] / df_annual["gross_sales"] * 100).round(1)
    df_annual["bonus_pct"] = (df_annual["bonus"] / df_annual["gross_sales"] * 100).round(1)
    df_annual["gtn_pct"] = (df_annual["gtn_amount"] / df_annual["gross_sales"] * 100).round(1)
    df_annual["nts_pct"] = (df_annual["nts"] / df_annual["gross_sales"] * 100).round(1)
    df_annual["cogs_pct"] = (df_annual["cogs"] / df_annual["nts"] * 100).round(1)
    df_annual["gp_std_pct"] = (df_annual["gp_std"] / df_annual["nts"] * 100).round(1)

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    total_gts = df_annual["gross_sales"].iloc[0] if not df_annual.empty else 0
    total_nts = df_annual["nts"].iloc[0] if not df_annual.empty else 0
    total_gp = df_annual["gp_std"].iloc[0] if not df_annual.empty else 0
    gp_pct = df_annual["gp_std_pct"].iloc[0] if not df_annual.empty else 0

    col1.metric("💰 Gross Sales", f"£{total_gts:,.0f}")
    col2.metric("📊 NTS", f"£{total_nts:,.0f}")
    col3.metric("💎 GP Std", f"£{total_gp:,.0f}")
    col4.metric("📈 GP %", f"{gp_pct:.1f}%")

    st.divider()

    # P&L Table by Account
    st.subheader("P&L by Account")

    # Build P&L rows
    pl_data = []

    if not df_annual.empty:
        row = df_annual.iloc[0]
        pl_data.append({"Account": "Gross Trade Sales (GTS)", "Value": row["gross_sales"], "% of GTS": 100.0})
        pl_data.append({"Account": "Returns (2%)", "Value": -row["returns"], "% of GTS": -row["returns_pct"]})
        pl_data.append({"Account": "Bonuses (1.5%)", "Value": -row["bonus"], "% of GTS": -row["bonus_pct"]})
        pl_data.append({"Account": "GTN (Structural + Tactical)", "Value": -row["gtn_amount"], "% of GTS": -row["gtn_pct"]})
        pl_data.append({"Account": "Net Trade Sales (NTS)", "Value": row["nts"], "% of GTS": row["nts_pct"]})
        pl_data.append({"Account": "COGS", "Value": -row["cogs"], "% of NTS": -row["cogs_pct"]})
        pl_data.append({"Account": "Gross Profit (GP Std)", "Value": row["gp_std"], "% of NTS": row["gp_std_pct"]})

    df_pl = pd.DataFrame(pl_data)

    st.dataframe(
        df_pl.style.format({
            "Value": "£{:,.0f}",
            "% of GTS": "{:.1f}%"
        }).applymap(
            lambda x: "font-weight: bold" if isinstance(x, str) and "GTS" in x or "NTS" in x or "GP" in x else "",
            subset=["Account"]
        ),
        use_container_width=True,
        hide_index=True
    )

    # Also show by Client
    st.subheader("P&L by Client")

    df_client = df_filtered.groupby("client_name").agg({
        "gross_sales": "sum",
        "nts": "sum",
        "gp_std": "sum"
    }).reset_index()

    df_client["gp_pct"] = (df_client["gp_std"] / df_client["nts"] * 100).round(1)
    df_client = df_client.sort_values("gp_std", ascending=False)

    st.dataframe(
        df_client.style.format({
            "gross_sales": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "gp_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    # Download summary
    csv_summary = df_pl.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download P&L Summary",
        data=csv_summary,
        file_name=f"pl_summary_{selected_year}.csv",
        mime="text/csv"
    )

# ============================================================================
# TAB 2: MONTHLY P&L
# ============================================================================
with tab_monthly:
    st.subheader(f"Monthly P&L Evolution – {selected_year}")

    # Aggregate by month
    df_monthly = df_filtered.groupby("month").agg({
        "gross_sales": "sum",
        "nts": "sum",
        "gp_std": "sum"
    }).reset_index().sort_values("month")

    # Add month names
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    df_monthly["month_name"] = df_monthly["month"].map(month_names)

    df_monthly["gp_pct"] = (df_monthly["gp_std"] / df_monthly["nts"] * 100).round(1)

    # Display metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Avg Monthly NTS", f"£{df_monthly['nts'].mean():,.0f}")
    col2.metric("💎 Avg Monthly GP", f"£{df_monthly['gp_std'].mean():,.0f}")
    col3.metric("📈 Avg Monthly GP %", f"{df_monthly['gp_pct'].mean():.1f}%")

    st.divider()

    # Monthly table
    st.dataframe(
        df_monthly[[
            "month_name", "gross_sales", "nts", "gp_std", "gp_pct"
        ]].style.format({
            "gross_sales": "£{:,.0f}",
            "nts": "£{:,.0f}",
            "gp_std": "£{:,.0f}",
            "gp_pct": "{:.1f}%"
        }).applymap(
            lambda x: "background-color: #e6f3e6" if isinstance(x, (int, float)) and x > 0 else "",
            subset=["gp_pct"]
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "month_name": "Month",
            "gross_sales": "Gross Sales",
            "nts": "NTS",
            "gp_std": "GP Std",
            "gp_pct": "GP %"
        }
    )

    # Download monthly data
    csv_monthly = df_monthly.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Monthly P&L",
        data=csv_monthly,
        file_name=f"pl_monthly_{selected_year}.csv",
        mime="text/csv"
    )

# ============================================================================
# TAB 3: RAW DATA
# ============================================================================
with tab_raw:
    st.subheader(f"Raw Data – {selected_year}")

    # Month filter (multi-select) for raw data only
    month_options = sorted(df_filtered["month"].unique())
    selected_months_raw = st.multiselect(
        "Select Months",
        options=month_options,
        default=month_options,
        key="raw_months"
    )

    # Apply month filter
    df_raw = df_filtered[df_filtered["month"].isin(selected_months_raw)]

    # Display columns for raw data
    raw_cols = [
        "year", "month", "client_name", "channel", "category",
        "sku", "product_name", "units_sold",
        "gross_sales", "returns", "bonus",
        "structural_gtn_pct", "tactical_gtn_pct", "total_gtn_pct", "gtn_amount",
        "nts", "cogs", "gp_std", "gp_std_pct"
    ]

    df_raw_display = df_raw[raw_cols].copy()

    # Rename columns for display
    df_raw_display.columns = [
        "Year", "Month", "Client", "Channel", "Category",
        "SKU", "Product", "Units",
        "Gross Sales", "Returns", "Bonus",
        "Struct GTN %", "Tact GTN %", "Total GTN %", "GTN £",
        "NTS", "COGS", "GP Std", "GP %"
    ]

    st.caption(f"Showing {len(df_raw_display):,} rows")

    st.dataframe(
        df_raw_display.style.format({
            "Units": "{:,.0f}",
            "Gross Sales": "£{:,.2f}",
            "Returns": "£{:,.2f}",
            "Bonus": "£{:,.2f}",
            "Struct GTN %": "{:.1%}",
            "Tact GTN %": "{:.1%}",
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

    # Download buttons
    st.divider()
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        csv_raw_filtered = df_raw.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Filtered Raw Data",
            data=csv_raw_filtered,
            file_name=f"pl_raw_data_{selected_year}_filtered.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_btn2:
        csv_raw_full = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full Raw Data",
            data=csv_raw_full,
            file_name="pl_raw_data_full.csv",
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